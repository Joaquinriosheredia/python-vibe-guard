"""Tests for v0.12b: suppression justifications + `pyvibe audit`
(pyvibe/suppressions.py's justification parsing, pyvibe/audit.py, and the
`pyvibe audit` CLI subcommand)."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyvibe.audit import audit_directory, audit_file, summarize
from pyvibe.suppressions import parse_inline_suppression_directives, parse_inline_suppressions

REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── justification parsing (parse_inline_suppression_directives) ───────────

def test_trailing_directive_with_justification():
    src = 'conn = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-008 -- legacy sqlite wrapper\n'
    directives = parse_inline_suppression_directives(src)
    assert len(directives) == 1
    d = directives[0]
    assert d.rule_ids == frozenset({"PYVIBE-008"})
    assert d.justification == "legacy sqlite wrapper"
    assert d.comment_line == 1
    assert d.target_line == 1
    assert d.directive == "ignore"


def test_ignore_next_line_with_justification():
    src = "# pyvibe: ignore-next-line PYVIBE-008 -- startup only\nconn = sqlite3.connect(\"x\")\n"
    directives = parse_inline_suppression_directives(src)
    assert len(directives) == 1
    d = directives[0]
    assert d.justification == "startup only"
    assert d.comment_line == 1
    assert d.target_line == 2
    assert d.directive == "ignore-next-line"


def test_directive_without_justification_is_none():
    src = 'conn = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-008\n'
    d = parse_inline_suppression_directives(src)[0]
    assert d.justification is None


def test_justification_is_stripped_of_whitespace():
    src = 'conn = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-008 --   padded reason   \n'
    d = parse_inline_suppression_directives(src)[0]
    assert d.justification == "padded reason"


def test_empty_justification_after_dashes_is_none():
    src = 'conn = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-008 --\n'
    d = parse_inline_suppression_directives(src)[0]
    assert d.justification is None


def test_multiple_rule_ids_share_one_justification():
    src = 'time.sleep(1)  # pyvibe: ignore PYVIBE-001, PYVIBE-003 -- benchmarked delay\n'
    d = parse_inline_suppression_directives(src)[0]
    assert d.rule_ids == frozenset({"PYVIBE-001", "PYVIBE-003"})
    assert d.justification == "benchmarked delay"


def test_parse_inline_suppressions_still_ignores_justification_text():
    # backward-compat: the simpler dict API used by analyzer.py doesn't
    # expose justifications, only {line: {rule_ids}}.
    src = 'conn = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-008 -- legacy\n'
    assert parse_inline_suppressions(src) == {1: frozenset({"PYVIBE-008"})}


# ─── orphan / unused suppression detection (pyvibe/audit.py) ───────────────

USED_AND_ORPHAN_SRC = """\
import sqlite3
import time

async def handler():
    conn = sqlite3.connect("db.sqlite")  # pyvibe: ignore PYVIBE-008 -- legacy sqlite wrapper
    return conn

def unrelated():
    x = 1  # pyvibe: ignore PYVIBE-019
    return x
"""


def test_audit_file_marks_used_suppression(tmp_path):
    f = tmp_path / "app.py"
    f.write_text(USED_AND_ORPHAN_SRC)

    records = audit_file(f)
    used = [r for r in records if r.rule_id == "PYVIBE-008"]
    assert len(used) == 1
    assert used[0].used is True
    assert used[0].justification == "legacy sqlite wrapper"


def test_audit_file_marks_orphan_suppression(tmp_path):
    f = tmp_path / "app.py"
    f.write_text(USED_AND_ORPHAN_SRC)

    records = audit_file(f)
    orphan = [r for r in records if r.rule_id == "PYVIBE-019"]
    assert len(orphan) == 1
    assert orphan[0].used is False
    assert orphan[0].justification is None
    assert orphan[0].comment_line == 9


def test_audit_directory_aggregates_across_files(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)
    (tmp_path / "clean.py").write_text("x = 1\n")

    records = audit_directory(tmp_path)
    assert len(records) == 2
    assert {r.rule_id for r in records} == {"PYVIBE-008", "PYVIBE-019"}


# ─── summarize() ────────────────────────────────────────────────────────────

def test_summarize_counts_and_by_rule(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)
    records = audit_directory(tmp_path)

    summary = summarize(records)

    assert summary.total == 2
    assert summary.with_justification == 1
    assert summary.without_justification == 1
    assert summary.unused == 1
    assert summary.by_rule == {"PYVIBE-008": 1, "PYVIBE-019": 1}
    assert [r.rule_id for r in summary.unused_records] == ["PYVIBE-019"]
    assert [r.rule_id for r in summary.unjustified_records] == ["PYVIBE-019"]


def test_summarize_empty_records():
    summary = summarize([])
    assert summary.total == 0
    assert summary.with_justification == 0
    assert summary.without_justification == 0
    assert summary.unused == 0
    assert summary.by_rule == {}
    assert summary.unused_records == []
    assert summary.unjustified_records == []


def test_summarize_by_rule_sorted_by_count_desc():
    from pyvibe.audit import SuppressionRecord

    records = [
        SuppressionRecord("f.py", 1, 1, "ignore", "PYVIBE-008", None, True),
        SuppressionRecord("f.py", 1, 1, "ignore", "PYVIBE-008", None, True),
        SuppressionRecord("f.py", 2, 2, "ignore", "PYVIBE-019", None, True),
        SuppressionRecord("f.py", 2, 2, "ignore", "PYVIBE-019", None, True),
        SuppressionRecord("f.py", 3, 3, "ignore", "PYVIBE-019", None, True),
        SuppressionRecord("f.py", 4, 4, "ignore", "PYVIBE-003", None, True),
    ]
    summary = summarize(records)
    assert list(summary.by_rule.items()) == [
        ("PYVIBE-019", 3),
        ("PYVIBE-008", 2),
        ("PYVIBE-003", 1),
    ]


# ─── `pyvibe audit` CLI (subprocess, human + --json + exit codes) ─────────

def _run_cli(args, cwd):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "pyvibe", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_audit_human_output(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)

    result = _run_cli(["audit", "."], cwd=tmp_path)

    assert result.returncode == 0
    assert "Suppressions audit" in result.stdout
    assert "Total suppressions: 2" in result.stdout
    assert "With justification: 1 (50%)" in result.stdout
    assert "Without justification: 1" in result.stdout
    assert "Unused (no violation found): 1" in result.stdout
    assert "By rule:" in result.stdout
    assert "PYVIBE-008" in result.stdout
    assert "Unused suppressions:" in result.stdout
    assert "app.py:9" in result.stdout
    assert "Without justification:" in result.stdout


def test_cli_audit_no_suppressions(tmp_path):
    (tmp_path / "clean.py").write_text("x = 1\n")

    result = _run_cli(["audit", "."], cwd=tmp_path)

    assert result.returncode == 0
    assert "No suppressions found." in result.stdout


def test_cli_audit_json_output(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)

    result = _run_cli(["audit", ".", "--json"], cwd=tmp_path)

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["total"] == 2
    assert data["with_justification"] == 1
    assert data["without_justification"] == 1
    assert data["unused"] == 1
    assert data["by_rule"] == {"PYVIBE-008": 1, "PYVIBE-019": 1}
    assert len(data["unused_suppressions"]) == 1
    assert data["unused_suppressions"][0]["rule_id"] == "PYVIBE-019"
    assert data["unused_suppressions"][0]["line"] == 9
    assert len(data["without_justification_suppressions"]) == 1


def test_cli_audit_fail_on_unused_exits_1(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)

    result = _run_cli(["audit", ".", "--fail-on-unused"], cwd=tmp_path)

    assert result.returncode == 1


def test_cli_audit_fail_on_unjustified_exits_1(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)

    result = _run_cli(["audit", ".", "--fail-on-unjustified"], cwd=tmp_path)

    assert result.returncode == 1


def test_cli_audit_max_unused_triggers_failure(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)

    result = _run_cli(["audit", ".", "--max-unused", "0"], cwd=tmp_path)
    assert result.returncode == 1

    result = _run_cli(["audit", ".", "--max-unused", "5"], cwd=tmp_path)
    assert result.returncode == 0


def test_cli_audit_no_flags_exits_0_even_with_unused(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)

    result = _run_cli(["audit", "."], cwd=tmp_path)

    assert result.returncode == 0


def test_cli_audit_defaults_to_current_directory(tmp_path):
    (tmp_path / "app.py").write_text(USED_AND_ORPHAN_SRC)

    result = _run_cli(["audit"], cwd=tmp_path)

    assert result.returncode == 0
    assert "Total suppressions: 2" in result.stdout


def test_cli_audit_missing_path_errors(tmp_path):
    result = _run_cli(["audit", "does-not-exist"], cwd=tmp_path)
    assert result.returncode == 2
    assert "does not exist" in result.stderr
