"""Point (c) of FASE1-DISENO.md (decision 2026-10-14): a CRITICAL finding whose
path has a non-production directory segment (tests/, test/, scripts/, wip/,
spike/, examples/ — full-segment match) is downgraded to WARNING, never silenced.
`com/example/` (segment `example`, not `examples`) and a filename that merely
contains `tests` are NOT downgraded.

Regression fixtures cite vibe-guard-evaluation dev-labels.json; the matcher unit
tests are mechanism tests (including the two mandatory negatives).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pyvibe.analyzer import analyze_directory, analyze_source

# A gather() with unresolved awaitables → PYVIBE-013 CRITICAL in production.
GATHER = "import asyncio\nasync def handler():\n    await asyncio.gather(a(), b())\n"


def _013(src, path):
    return [v for v in analyze_source(src, path) if v.rule_id == "PYVIBE-013"]


# ── regression fixtures (cite dev-labels.json) ───────────────────────────────

def test_c_dl003_tests_dir_downgraded_to_warning():
    # dev-labels DL-003 (ARES tests/unit/test_scope_firewall.py:194, PYVIBE-013):
    # a finding under a tests/ directory is reported as WARNING, not CRITICAL.
    v = _013(GATHER, "tests/unit/test_scope_firewall.py")
    assert len(v) == 1 and v[0].severity == "WARNING"


def test_c_dl022_scripts_dir_downgraded_to_warning():
    # dev-labels DL-022 (MimirQ scripts/deepdoc_quality_gate.py:542, PYVIBE-013):
    # a finding under a scripts/ directory is reported as WARNING, not CRITICAL.
    v = _013(GATHER, "scripts/deepdoc_quality_gate.py")
    assert len(v) == 1 and v[0].severity == "WARNING"


# ── matcher mechanism tests ──────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "tests/helpers.py",
    "pkg/test/util.py",
    "scripts/run.py",
    "wip/spike.py",
    "research/spike/try_it.py",
    "examples/demo.py",
])
def test_c_nonprod_segment_downgrades(path):
    v = _013(GATHER, path)
    assert len(v) == 1 and v[0].severity == "WARNING", f"{path} should downgrade"


@pytest.mark.parametrize("path", [
    "com/example/service.py",     # segment is 'example', not 'examples'
    "app/my_tests_utils.py",      # filename contains 'tests'; no such segment
    "src/app/handlers.py",        # ordinary production
])
def test_c_production_paths_stay_critical(path):
    v = _013(GATHER, path)
    assert len(v) == 1 and v[0].severity == "CRITICAL", f"{path} must NOT downgrade"


def test_c_never_silences():
    # The finding is kept in every case — only its severity changes.
    assert len(_013(GATHER, "tests/x.py")) == 1
    assert len(_013(GATHER, "app/x.py")) == 1


# ── CLI and library behave the same (decision 2026-10-14) ────────────────────

# PYVIBE-004 is outside the old short TEST_FILE_DOWNGRADE list: before the fix
# the CLI kept it CRITICAL in tests/ while the library downgraded it.
LOCK = "import threading\nasync def handler():\n    lock = threading.Lock()\n    with lock:\n        pass\n"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _cli_json(args, cwd):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    r = subprocess.run([sys.executable, "-m", "pyvibe", *args, "--json"],
                       cwd=cwd, capture_output=True, text=True, env=env)
    return json.loads(r.stdout)


@pytest.mark.parametrize("extra", [[], ["--downgrade-in-tests"]])
def test_cli_critical_in_tests_dir_is_warning_like_library(tmp_path, extra):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_lock.py").write_text(LOCK)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "lock.py").write_text(LOCK)

    cli = {(f["file"].replace(str(tmp_path) + "/", ""), f["rule"], f["line"], f["severity"])
           for f in _cli_json([str(tmp_path), *extra], cwd=tmp_path)}
    lib = {(str(p.relative_to(tmp_path)), v.rule_id, v.line, v.severity)
           for p, vs in analyze_directory(tmp_path).items() for v in vs}

    assert ("tests/test_lock.py", "PYVIBE-004", 3, "WARNING") in cli
    assert ("app/lock.py", "PYVIBE-004", 3, "CRITICAL") in cli
    assert cli == lib


def test_cli_single_test_file_critical_is_warning(tmp_path):
    (tmp_path / "tests").mkdir()
    f = tmp_path / "tests" / "test_lock.py"
    f.write_text(LOCK)
    out = _cli_json([str(f)], cwd=tmp_path)
    assert [(x["rule"], x["severity"]) for x in out] == [("PYVIBE-004", "WARNING")]


# ── only segments INSIDE the scan root count (2026-10-14) ────────────────────
# A repository cloned under `.../scripts/x` (or `.../tests/x`) is not a
# non-production directory: segments above the scanned root must not downgrade.


def _repo_under_scripts(tmp_path):
    repo = tmp_path / "scripts" / "myrepo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "lock.py").write_text(LOCK)
    (repo / "tests").mkdir()
    (repo / "tests" / "helper.py").write_text(LOCK)  # positive control, inside the root
    return repo


def _sev(findings):
    return {f["file"].replace("\\", "/").split("myrepo/")[-1]: f["severity"] for f in findings}


def test_root_above_segment_ignored_cli_absolute_path(tmp_path):
    repo = _repo_under_scripts(tmp_path)
    out = _sev(_cli_json([str(repo)], cwd=tmp_path))
    assert out == {"app/lock.py": "CRITICAL", "tests/helper.py": "WARNING"}


def test_root_above_segment_ignored_cli_relative_path(tmp_path):
    _repo_under_scripts(tmp_path)
    out = _sev(_cli_json(["scripts/myrepo"], cwd=tmp_path))
    assert out == {"app/lock.py": "CRITICAL", "tests/helper.py": "WARNING"}


def test_root_above_segment_ignored_library(tmp_path):
    repo = _repo_under_scripts(tmp_path)
    for root in (repo, Path(os.path.relpath(repo))):
        got = {str(p.relative_to(root)).replace("\\", "/"): vs[0].severity
               for p, vs in analyze_directory(root).items()}
        assert got == {"app/lock.py": "CRITICAL", "tests/helper.py": "WARNING"}


def test_root_above_segment_ignored_single_file(tmp_path):
    # A single file: its own directory is the root, only the filename counts.
    repo = _repo_under_scripts(tmp_path)
    out = _cli_json([str(repo / "app" / "lock.py")], cwd=tmp_path)
    assert [(x["rule"], x["severity"]) for x in out] == [("PYVIBE-004", "CRITICAL")]


def test_root_above_segment_not_skipped_by_no_test_files(tmp_path):
    repo = tmp_path / "tests" / "myrepo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "lock.py").write_text(LOCK)
    out = _sev(_cli_json([str(repo), "--no-test-files"], cwd=tmp_path))
    assert out == {"app/lock.py": "CRITICAL"}


def test_review_uses_repo_root(tmp_path):
    repo = tmp_path / "scripts" / "myrepo"
    (repo / "app").mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    git("init", "-q"); git("config", "user.email", "t@t.com"); git("config", "user.name", "T")
    (repo / "app" / "base.py").write_text("x = 1\n")
    git("add", "."); git("commit", "-q", "-m", "init")
    (repo / "app" / "lock.py").write_text(LOCK)
    git("add", ".")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    r = subprocess.run([sys.executable, "-m", "pyvibe", "review", "--base", "HEAD", "--json"],
                       cwd=repo, capture_output=True, text=True, env=env)
    assert [(x["rule"], x["severity"]) for x in json.loads(r.stdout)] == [("PYVIBE-004", "CRITICAL")]


# ── the scanned root's own name counts, never the directories above ──────────
# Decision 2026-10-14 (PR #13): the name of the scanned root and, for a single
# file, of its immediate directory as passed, count; directories above never do.


def test_case_scan_scripts_dir_is_downgraded(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "gate.py").write_text(LOCK)
    out = _cli_json(["scripts/"], cwd=tmp_path)
    assert [(x["rule"], x["severity"]) for x in out] == [("PYVIBE-004", "WARNING")]
    lib = analyze_directory(tmp_path / "scripts")
    assert [v.severity for vs in lib.values() for v in vs] == ["WARNING"]


def test_case_single_file_in_tests_dir_is_downgraded(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "foo.py").write_text(LOCK)  # not a test_*.py name
    out = _cli_json(["tests/foo.py"], cwd=tmp_path)
    assert [(x["rule"], x["severity"]) for x in out] == [("PYVIBE-004", "WARNING")]


def test_case_repo_under_scripts_absolute_path_not_downgraded(tmp_path):
    repo = tmp_path / "scripts" / "mi-repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "lock.py").write_text(LOCK)
    out = _cli_json([str(repo)], cwd=tmp_path)
    assert [(x["rule"], x["severity"]) for x in out] == [("PYVIBE-004", "CRITICAL")]
    lib = analyze_directory(repo)
    assert [v.severity for vs in lib.values() for v in vs] == ["CRITICAL"]


def test_case_repo_under_scripts_dot_not_downgraded(tmp_path):
    repo = tmp_path / "scripts" / "mi-repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "lock.py").write_text(LOCK)
    out = _cli_json(["."], cwd=repo)
    assert [(x["rule"], x["severity"]) for x in out] == [("PYVIBE-004", "CRITICAL")]
