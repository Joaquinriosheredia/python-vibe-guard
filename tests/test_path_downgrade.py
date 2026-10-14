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
