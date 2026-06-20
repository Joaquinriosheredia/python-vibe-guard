#!/usr/bin/env python3
"""
Massive validation scan for python-vibe-guard.

Searches GitHub for async Python repos (>100 stars, updated in the last year),
clones them, runs pyvibe, and aggregates results into validation/aggregate.json.

Usage:
    python validation/run_massive_scan.py [--target N] [--skip-clone]

Options:
    --target N     Number of repos to scan (default: 50)
    --skip-clone   Re-use existing clones in validation/repos/ (no re-download)
"""

import argparse
import collections
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
VALIDATION = ROOT / "validation"
REPOS_DIR = VALIDATION / "repos"
RAW_DIR = VALIDATION / "raw"
AGGREGATE_OUT = VALIDATION / "aggregate.json"
PYVIBE = [sys.executable, "-m", "pyvibe"]

# Already scanned in reference set — keep them but don't re-clone
REFERENCE_REPOS = {
    "tiangolo/fastapi",
    "celery/celery",
    "aio-libs/aiohttp",
    "encode/httpx",
}

# ── Search queries ─────────────────────────────────────────────────────────────

ONE_YEAR_AGO = (date.today() - timedelta(days=365)).isoformat()

SEARCH_QUERIES = [
    f"language:python topic:fastapi stars:>100 pushed:>{ONE_YEAR_AGO}",
    f"language:python topic:aiohttp stars:>100 pushed:>{ONE_YEAR_AGO}",
    f"language:python topic:asyncio stars:>100 pushed:>{ONE_YEAR_AGO}",
    f"language:python topic:celery stars:>100 pushed:>{ONE_YEAR_AGO}",
    f"language:python topic:django stars:>500 pushed:>{ONE_YEAR_AGO}",
    f"language:python fastapi in:description stars:>200 pushed:>{ONE_YEAR_AGO}",
    f"language:python asyncio in:description stars:>300 pushed:>{ONE_YEAR_AGO}",
    f"language:python aiohttp in:description stars:>200 pushed:>{ONE_YEAR_AGO}",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(msg, flush=True)


def gh_search(query: str, per_page: int = 100) -> list[dict]:
    """Call GitHub search/repositories via gh CLI. Returns list of repo dicts."""
    import urllib.parse
    encoded = urllib.parse.quote(query, safe="+:")
    url = f"search/repositories?q={encoded}&sort=stars&order=desc&per_page={per_page}"
    try:
        result = subprocess.run(
            ["gh", "api", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log(f"  [warn] gh api failed for query '{query[:60]}': {result.stderr.strip()[:100]}")
            return []
        data = json.loads(result.stdout)
        return data.get("items", [])
    except Exception as e:
        log(f"  [warn] search error: {e}")
        return []


def collect_repos(target: int) -> list[dict]:
    """Run all search queries, deduplicate, exclude reference set, cap at target."""
    seen: dict[str, dict] = {}

    for i, query in enumerate(SEARCH_QUERIES):
        if len(seen) >= target * 3:  # fetch 3× to have headroom after dedup
            break
        log(f"  query {i+1}/{len(SEARCH_QUERIES)}: {query[:70]}...")
        items = gh_search(query)
        for item in items:
            full_name = item["full_name"]
            if full_name not in seen:
                seen[full_name] = item
        log(f"    → {len(items)} results, {len(seen)} unique so far")
        if i < len(SEARCH_QUERIES) - 1:
            time.sleep(2)  # stay within 30 req/min search rate limit

    # Sort by stars desc, exclude reference repos, cap at target
    candidates = [r for r in seen.values() if r["full_name"] not in REFERENCE_REPOS]
    candidates.sort(key=lambda r: r["stargazers_count"], reverse=True)
    return candidates[:target]


def clone_repo(full_name: str, dest: Path) -> bool:
    """Shallow-clone a repo into dest. Returns True on success."""
    clone_url = f"https://github.com/{full_name}.git"
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", clone_url, str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            log(f"    [error] clone failed: {result.stderr.strip()[:120]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        log("    [error] clone timed out (>120s)")
        return False
    except Exception as e:
        log(f"    [error] clone exception: {e}")
        return False


def run_pyvibe(repo_path: Path) -> list[dict]:
    """Run pyvibe --json on repo_path. Returns list of violation dicts."""
    try:
        result = subprocess.run(
            PYVIBE + [str(repo_path), "--json", "--exclude", "venv",
                      "--exclude", ".venv", "--exclude", "node_modules"],
            capture_output=True, text=True, timeout=300,
        )
        # Exit code 0 = clean, 1 = violations found, 2 = path error
        if result.returncode == 2:
            log(f"    [error] pyvibe path error: {result.stderr.strip()[:100]}")
            return []
        if not result.stdout.strip():
            return []
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        log("    [warn] pyvibe timed out (>300s) — partial results discarded")
        return []
    except json.JSONDecodeError as e:
        log(f"    [warn] could not parse pyvibe JSON: {e}")
        return []
    except Exception as e:
        log(f"    [error] pyvibe error: {e}")
        return []


def count_py_files(repo_path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(repo_path):
        # Prune the same dirs pyvibe skips
        dirs[:] = [d for d in dirs if d not in {
            "venv", ".venv", "__pycache__", "node_modules",
            ".git", "dist", "build", ".eggs",
        }]
        total += sum(1 for f in files if f.endswith(".py"))
    return total


# ── Aggregation ────────────────────────────────────────────────────────────────

ALL_RULES = [f"PYVIBE-{str(i).zfill(3)}" for i in range(1, 21)]


def build_aggregate(scan_results: list[dict]) -> dict:
    """
    scan_results: list of {repo, stars, files, violations: [...]}
    Returns the aggregate.json structure.
    """
    total_files = sum(r["files"] for r in scan_results)
    total_violations = sum(len(r["violations"]) for r in scan_results)

    by_rule: dict[str, dict] = {}
    for rule in ALL_RULES:
        hits = [(r["repo"], len([v for v in r["violations"] if v["rule"] == rule]))
                for r in scan_results]
        total_hits = sum(h for _, h in hits)
        repos_with_hits = sum(1 for _, h in hits if h > 0)
        top_repos = sorted(
            [(name, cnt) for name, cnt in hits if cnt > 0],
            key=lambda x: x[1], reverse=True,
        )[:5]
        by_rule[rule] = {
            "total_hits": total_hits,
            "repos_with_hits": repos_with_hits,
            "top_repos": [{"repo": n, "hits": c} for n, c in top_repos],
        }

    scanned_repos = [
        {"repo": r["repo"], "stars": r["stars"], "files": r["files"],
         "violations": len(r["violations"])}
        for r in scan_results
    ]

    return {
        "version": "0.7.0",
        "scan_date": date.today().isoformat(),
        "total_repos": len(scan_results),
        "total_files": total_files,
        "total_violations": total_violations,
        "by_rule": by_rule,
        "repos": scanned_repos,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=int, default=50,
                        help="Number of repos to scan (default: 50)")
    parser.add_argument("--skip-clone", action="store_true",
                        help="Re-use existing clones, skip download")
    args = parser.parse_args()

    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Discover repos ──────────────────────────────────────────────────────
    # Phase 1: always load existing clones
    existing_dirs = [d for d in sorted(REPOS_DIR.iterdir()) if d.is_dir()]
    existing_names = {d.name.replace("__", "/"): d for d in existing_dirs}
    log(f"[1/4] Found {len(existing_names)} existing clones in {REPOS_DIR}")

    if args.skip_clone:
        # Scan only what's already cloned — no GitHub search, no new downloads
        repos_to_scan = [{"full_name": name, "stargazers_count": 0}
                         for name in sorted(existing_names)]
        log(f"      [skip-clone] using {len(repos_to_scan)} existing repos only")
    else:
        # Phase 2: search GitHub for additional repos to reach target
        needed = args.target - len(existing_names)
        if needed > 0:
            log(f"      need {needed} more — searching GitHub...")
            candidates = collect_repos(args.target * 3)
            new_repos = [r for r in candidates if r["full_name"] not in existing_names][:needed]
            log(f"      → {len(new_repos)} new repos selected")
        else:
            new_repos = []
            log(f"      already have {len(existing_names)} repos — no search needed")

        repos_to_scan = (
            [{"full_name": n, "stargazers_count": 0} for n in sorted(existing_names)]
            + new_repos
        )
        log(f"      → {len(repos_to_scan)} total repos to scan\n")

    # ── 2. Clone + scan ────────────────────────────────────────────────────────
    log(f"[2/4] Cloning and scanning {len(repos_to_scan)} repos...")
    scan_results: list[dict] = []
    failed_clones = 0
    failed_scans = 0

    for idx, repo_info in enumerate(repos_to_scan, 1):
        full_name = repo_info["full_name"]
        stars = repo_info.get("stargazers_count", 0)
        # Sanitise name for filesystem: owner__repo
        safe_name = full_name.replace("/", "__")
        repo_path = REPOS_DIR / safe_name
        raw_path = RAW_DIR / f"{safe_name}.json"

        log(f"  [{idx:02d}/{len(repos_to_scan)}] {full_name} ({stars:,} ★)")

        # Clone if needed
        if not repo_path.exists():
            if args.skip_clone:
                log(f"    [skip] not cloned, skipping")
                continue
            log(f"    cloning...")
            ok = clone_repo(full_name, repo_path)
            if not ok:
                failed_clones += 1
                continue
        else:
            log(f"    already cloned")

        # Run pyvibe
        log(f"    scanning...")
        violations = run_pyvibe(repo_path)
        py_files = count_py_files(repo_path)
        log(f"    → {py_files} .py files, {len(violations)} violations")

        # Save raw JSON
        raw_path.write_text(json.dumps(violations, indent=2))

        scan_results.append({
            "repo": full_name,
            "stars": stars,
            "files": py_files,
            "violations": violations,
        })

    # ── 3. Aggregate ───────────────────────────────────────────────────────────
    log(f"\n[3/4] Aggregating results...")
    aggregate = build_aggregate(scan_results)
    AGGREGATE_OUT.write_text(json.dumps(aggregate, indent=2))
    log(f"      → written to {AGGREGATE_OUT}")

    # ── 4. Summary ─────────────────────────────────────────────────────────────
    log(f"\n[4/4] Summary")
    log(f"  repos scanned:    {aggregate['total_repos']}")
    log(f"  .py files:        {aggregate['total_files']:,}")
    log(f"  total violations: {aggregate['total_violations']:,}")
    log(f"  failed clones:    {failed_clones}")
    log(f"  failed scans:     {failed_scans}")
    log(f"\n  Rule breakdown (hits > 0):")
    for rule, data in aggregate["by_rule"].items():
        if data["total_hits"] > 0:
            pct = data["repos_with_hits"] / max(aggregate["total_repos"], 1) * 100
            log(f"    {rule}: {data['total_hits']:4d} hits  "
                f"{data['repos_with_hits']:2d}/{aggregate['total_repos']} repos "
                f"({pct:.0f}%)")

    log(f"\nDone. Push validation/aggregate.json when ready.")


if __name__ == "__main__":
    main()
