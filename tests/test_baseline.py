"""Tests for baseline support (pyvibe/baseline.py + `pyvibe baseline` /
`pyvibe scan --baseline` CLI subcommands)."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from pyvibe.analyzer import analyze_source
from pyvibe.baseline import (
    BaselineNotFoundError,
    build_baseline,
    filter_new_violations,
    load_baseline,
    write_baseline,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

VIOLATION_SRC = """\
import time

async def handler():
    time.sleep(5)

async def other():
    time.sleep(9)
"""


# ─── build_baseline() / write_baseline() / load_baseline() unit tests ──────

def test_build_baseline_shapes_output():
    violations = analyze_source(VIOLATION_SRC, filepath="app.py")
    baseline = build_baseline({Path("app.py"): violations})

    assert baseline == {
        "app.py": [
            {"rule_id": "PYVIBE-001", "line": 4, "message": violations[0].message},
            {"rule_id": "PYVIBE-001", "line": 7, "message": violations[1].message},
        ]
    }


def test_write_and_load_baseline_roundtrip(tmp_path):
    violations = analyze_source(VIOLATION_SRC, filepath="app.py")
    out = tmp_path / "baseline.json"

    write_baseline({Path("app.py"): violations}, out)
    loaded = load_baseline(out)

    assert loaded == build_baseline({Path("app.py"): violations})


def test_load_baseline_missing_file_raises(tmp_path):
    with pytest.raises(BaselineNotFoundError, match="No baseline found"):
        load_baseline(tmp_path / "nope.json")


def test_load_baseline_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json{{{")
    with pytest.raises(BaselineNotFoundError, match="not valid JSON"):
        load_baseline(bad)


# ─── filter_new_violations() unit tests ────────────────────────────────────

def test_filter_new_violations_excludes_exact_match():
    violations = analyze_source(VIOLATION_SRC, filepath="app.py")
    baseline = build_baseline({Path("app.py"): violations})

    result = filter_new_violations({Path("app.py"): violations}, baseline)

    assert result == {}


def test_filter_new_violations_reports_new_line():
    violations = analyze_source(VIOLATION_SRC, filepath="app.py")
    baseline = build_baseline({Path("app.py"): [violations[0]]})  # only line 4 known

    result = filter_new_violations({Path("app.py"): violations}, baseline)

    assert list(result.keys()) == [Path("app.py")]
    assert [v.line for v in result[Path("app.py")]] == [7]


def test_filter_new_violations_reports_new_rule_on_same_line():
    violations = analyze_source(VIOLATION_SRC, filepath="app.py")
    baseline = {"app.py": [{"rule_id": "PYVIBE-999", "line": 4, "message": "unrelated"}]}

    result = filter_new_violations({Path("app.py"): violations}, baseline)

    assert {v.line for v in result[Path("app.py")]} == {4, 7}


def test_filter_new_violations_empty_baseline_returns_everything():
    violations = analyze_source(VIOLATION_SRC, filepath="app.py")

    result = filter_new_violations({Path("app.py"): violations}, {})

    assert result == {Path("app.py"): violations}


def test_filter_new_violations_drops_file_with_no_remaining_new_violations():
    violations = analyze_source(VIOLATION_SRC, filepath="app.py")
    baseline = build_baseline({Path("app.py"): violations})

    clean_file_results = {Path("app.py"): violations, Path("clean.py"): []}
    result = filter_new_violations(clean_file_results, baseline)

    assert result == {}


# ─── `pyvibe baseline` / `pyvibe scan --baseline` CLI (subprocess) ─────────

def _run_cli(args, cwd):
    # cwd is a throwaway tmp_path, not REPO_ROOT, so `-m pyvibe` needs
    # PYTHONPATH set explicitly to find the package in a test environment
    # where it isn't pip-installed (see the review-subcommand CI fix).
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "pyvibe", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_baseline_create_writes_file_and_message(tmp_path):
    (tmp_path / "app.py").write_text(VIOLATION_SRC)

    result = _run_cli(["baseline", "create", "."], cwd=tmp_path)

    assert result.returncode == 0
    assert "Baseline created: 2 findings saved to .pyvibe-baseline.json" in result.stdout
    baseline_file = tmp_path / ".pyvibe-baseline.json"
    assert baseline_file.exists()
    assert len(json.loads(baseline_file.read_text())["app.py"]) == 2


def test_cli_baseline_create_refuses_to_overwrite_existing(tmp_path):
    (tmp_path / "app.py").write_text(VIOLATION_SRC)
    _run_cli(["baseline", "create", "."], cwd=tmp_path)

    result = _run_cli(["baseline", "create", "."], cwd=tmp_path)

    assert result.returncode == 2
    assert "already exists" in result.stderr


def test_cli_baseline_update_overwrites_existing(tmp_path):
    (tmp_path / "app.py").write_text(VIOLATION_SRC)
    _run_cli(["baseline", "create", "."], cwd=tmp_path)

    (tmp_path / "app.py").write_text(VIOLATION_SRC + "\nasync def third():\n    time.sleep(1)\n")
    result = _run_cli(["baseline", "update", "."], cwd=tmp_path)

    assert result.returncode == 0
    assert "Baseline updated: 3 findings saved to .pyvibe-baseline.json" in result.stdout


def test_cli_scan_baseline_reports_only_new_finding(tmp_path):
    (tmp_path / "app.py").write_text(VIOLATION_SRC)
    _run_cli(["baseline", "create", "."], cwd=tmp_path)

    (tmp_path / "app.py").write_text(
        VIOLATION_SRC + "\nasync def third():\n    time.sleep(1)\n"
    )

    result = _run_cli(["scan", ".", "--baseline", "--json"], cwd=tmp_path)
    output = json.loads(result.stdout)

    assert result.returncode == 1
    assert len(output) == 1
    assert output[0]["line"] == 10


def test_cli_scan_baseline_clean_when_no_new_findings(tmp_path):
    (tmp_path / "app.py").write_text(VIOLATION_SRC)
    _run_cli(["baseline", "create", "."], cwd=tmp_path)

    result = _run_cli(["scan", ".", "--baseline"], cwd=tmp_path)

    assert result.returncode == 0
    assert "No violations found" in result.stdout


def test_cli_scan_baseline_missing_file_exits_2(tmp_path):
    (tmp_path / "app.py").write_text("print('clean')\n")

    result = _run_cli(["scan", ".", "--baseline"], cwd=tmp_path)

    assert result.returncode == 2
    assert "No baseline found" in result.stderr


def test_cli_scan_without_baseline_flag_matches_bare_invocation(tmp_path):
    (tmp_path / "app.py").write_text(VIOLATION_SRC)

    scan_result = _run_cli(["scan", ".", "--json"], cwd=tmp_path)
    bare_result = _run_cli([".", "--json"], cwd=tmp_path)

    assert json.loads(scan_result.stdout) == json.loads(bare_result.stdout)


def test_cli_bare_command_supports_baseline_flag(tmp_path):
    (tmp_path / "app.py").write_text(VIOLATION_SRC)
    _run_cli(["baseline", "create", "."], cwd=tmp_path)

    (tmp_path / "app.py").write_text(
        VIOLATION_SRC + "\nasync def third():\n    time.sleep(1)\n"
    )

    result = _run_cli([".", "--baseline", "--json"], cwd=tmp_path)
    output = json.loads(result.stdout)

    assert result.returncode == 1
    assert len(output) == 1
    assert output[0]["line"] == 10


def test_cli_bare_command_baseline_missing_file_exits_2(tmp_path):
    (tmp_path / "app.py").write_text("print('clean')\n")

    result = _run_cli([".", "--baseline"], cwd=tmp_path)

    assert result.returncode == 2
    assert "No baseline found" in result.stderr
