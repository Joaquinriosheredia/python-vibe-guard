#!/usr/bin/env python3
"""Copy the research evidence that `pyvibe explain` reads into the package.

research/ is the source of truth (it is what the SARIF helpUri links point to
on GitHub), but it lives outside the `pyvibe` package, so a wheel installed
from PyPI does not contain it. This script mirrors the files `explain` needs
into pyvibe/_evidence/, which is shipped as package data.

    python scripts/sync_evidence.py          # update pyvibe/_evidence/
    python scripts/sync_evidence.py --check  # exit 1 if the copy is stale

tests/test_evidence_sync.py runs the --check logic, so CI fails whenever
research/ changes without re-running this script.
"""
import argparse
import shutil
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "research"
TARGET = REPO_ROOT / "pyvibe" / "_evidence"


def expected_files() -> List[Path]:
    """Relative paths (under research/ and pyvibe/_evidence/) that must match."""
    accepted = sorted(p.relative_to(SOURCE) for p in (SOURCE / "accepted").glob("PYVIBE-*.md"))
    return accepted + [Path("precision-audit.md")]


def stale_files() -> List[str]:
    """Problems found comparing research/ with pyvibe/_evidence/ (empty = in sync)."""
    problems = []
    expected = set(expected_files())
    for rel in sorted(expected):
        src, dst = SOURCE / rel, TARGET / rel
        if not dst.exists():
            problems.append(f"missing: pyvibe/_evidence/{rel.as_posix()}")
        elif src.read_bytes() != dst.read_bytes():
            problems.append(f"differs: pyvibe/_evidence/{rel.as_posix()}")
    if TARGET.exists():
        for dst in sorted(TARGET.rglob("*.md")):
            rel = dst.relative_to(TARGET)
            if rel not in expected:
                problems.append(f"orphan: pyvibe/_evidence/{rel.as_posix()}")
    return problems


def sync() -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    for rel in expected_files():
        dst = TARGET / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / rel, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only report differences")
    args = parser.parse_args()

    if args.check:
        problems = stale_files()
        for p in problems:
            print(p)
        if problems:
            print("Run: python scripts/sync_evidence.py", file=sys.stderr)
            return 1
        return 0

    sync()
    print(f"Synced {len(expected_files())} files into {TARGET.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
