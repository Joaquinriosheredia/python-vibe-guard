"""Tests for pyvibe.toml project configuration (pyvibe/config.py) and its
integration into analyzer.py / the CLI (--verbose, `pyvibe scan`, etc.)."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from pyvibe.analyzer import analyze_source_full
from pyvibe.config import ConfigError, find_config_file, is_excluded, load_config

REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── find_config_file() / load_config() unit tests ─────────────────────────

def test_find_config_file_in_current_dir(tmp_path):
    (tmp_path / "pyvibe.toml").write_text("[tool.pyvibe]\n")
    assert find_config_file(tmp_path) == tmp_path / "pyvibe.toml"


def test_find_config_file_walks_up_parents(tmp_path):
    (tmp_path / "pyvibe.toml").write_text("[tool.pyvibe]\n")
    nested = tmp_path / "src" / "app"
    nested.mkdir(parents=True)
    assert find_config_file(nested) == tmp_path / "pyvibe.toml"


def test_find_config_file_accepts_a_file_path(tmp_path):
    (tmp_path / "pyvibe.toml").write_text("[tool.pyvibe]\n")
    target_file = tmp_path / "app.py"
    target_file.write_text("x = 1\n")
    assert find_config_file(target_file) == tmp_path / "pyvibe.toml"


def test_find_config_file_returns_none_when_absent(tmp_path):
    assert find_config_file(tmp_path) is None


def test_load_config_returns_none_when_absent(tmp_path):
    assert load_config(tmp_path) is None


def test_load_config_parses_ignore_exclude_severity(tmp_path):
    (tmp_path / "pyvibe.toml").write_text(
        """
[tool.pyvibe]
ignore = ["PYVIBE-019"]
exclude = ["tests/**", "examples/**"]

[tool.pyvibe.severity]
PYVIBE-008 = "warning"
"""
    )
    config = load_config(tmp_path)
    assert config.ignore == frozenset({"PYVIBE-019"})
    assert config.exclude == ("tests/**", "examples/**")
    assert config.severity == {"PYVIBE-008": "WARNING"}
    assert config.root == tmp_path


def test_load_config_defaults_when_sections_missing(tmp_path):
    (tmp_path / "pyvibe.toml").write_text("[tool.pyvibe]\n")
    config = load_config(tmp_path)
    assert config.ignore == frozenset()
    assert config.exclude == ()
    assert config.severity == {}


def test_load_config_invalid_toml_raises_config_error(tmp_path):
    (tmp_path / "pyvibe.toml").write_text("[tool.pyvibe\nignore = [\n")
    with pytest.raises(ConfigError, match="Failed to parse"):
        load_config(tmp_path)


def test_load_config_invalid_severity_raises_config_error(tmp_path):
    (tmp_path / "pyvibe.toml").write_text(
        '[tool.pyvibe.severity]\nPYVIBE-008 = "banana"\n'
    )
    with pytest.raises(ConfigError, match="invalid severity"):
        load_config(tmp_path)


def test_load_config_severity_accepts_critical_and_warning(tmp_path):
    (tmp_path / "pyvibe.toml").write_text(
        '[tool.pyvibe.severity]\nPYVIBE-001 = "critical"\nPYVIBE-008 = "WARNING"\n'
    )
    config = load_config(tmp_path)
    assert config.severity == {"PYVIBE-001": "CRITICAL", "PYVIBE-008": "WARNING"}


# ─── is_excluded() unit tests ──────────────────────────────────────────────

def test_is_excluded_matches_glob(tmp_path):
    (tmp_path / "pyvibe.toml").write_text('[tool.pyvibe]\nexclude = ["tests/**"]\n')
    config = load_config(tmp_path)
    assert is_excluded(tmp_path / "tests" / "test_app.py", config) is True
    assert is_excluded(tmp_path / "src" / "app.py", config) is False


def test_is_excluded_false_when_no_patterns(tmp_path):
    (tmp_path / "pyvibe.toml").write_text("[tool.pyvibe]\n")
    config = load_config(tmp_path)
    assert is_excluded(tmp_path / "anything.py", config) is False


# ─── analyze_source_full() + config integration ────────────────────────────

RETRY_NO_BACKOFF_SRC = """\
async def call_api():
    for attempt in range(3):
        try:
            return await client.post(url)
        except Exception:
            continue
"""

SQLITE_SRC = """\
import sqlite3

async def handler():
    conn = sqlite3.connect("db.sqlite")
"""


def test_config_ignore_suppresses_matching_rule(tmp_path):
    config = load_config(tmp_path)  # None, but build one directly instead:
    from pyvibe.config import PyvibeConfig

    config = PyvibeConfig(root=tmp_path, ignore=frozenset({"PYVIBE-019"}))
    reported, suppressed = analyze_source_full(RETRY_NO_BACKOFF_SRC, filepath="app.py", config=config)
    assert reported == []
    assert [(v.rule_id, reason) for v, reason in suppressed] == [("PYVIBE-019", "config")]


def test_config_severity_override_changes_severity(tmp_path):
    from pyvibe.config import PyvibeConfig

    config = PyvibeConfig(root=tmp_path, severity={"PYVIBE-008": "WARNING"})
    reported, suppressed = analyze_source_full(SQLITE_SRC, filepath="app.py", config=config)
    assert len(reported) == 1
    assert reported[0].severity == "WARNING"
    assert suppressed == []


def test_no_config_leaves_default_behavior_unchanged():
    reported, suppressed = analyze_source_full(SQLITE_SRC, filepath="app.py", config=None)
    assert len(reported) == 1
    assert reported[0].severity == "CRITICAL"


# ─── `pyvibe.toml` CLI integration (subprocess, end-to-end) ────────────────

def _run_cli(args, cwd):
    # cwd is a throwaway tmp_path, not REPO_ROOT, so `-m pyvibe` needs
    # PYTHONPATH set explicitly to find the package in a test environment
    # where it isn't pip-installed (see the `pyvibe review` CI fix).
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "pyvibe", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_config_ignore_removes_finding_from_json(tmp_path):
    (tmp_path / "pyvibe.toml").write_text('[tool.pyvibe]\nignore = ["PYVIBE-019"]\n')
    (tmp_path / "app.py").write_text(RETRY_NO_BACKOFF_SRC)

    result = _run_cli([".", "--json"], cwd=tmp_path)
    assert json.loads(result.stdout) == []
    assert result.returncode == 0


def test_cli_config_exclude_skips_matching_files(tmp_path):
    (tmp_path / "pyvibe.toml").write_text('[tool.pyvibe]\nexclude = ["tests/**"]\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(SQLITE_SRC)
    (tmp_path / "app.py").write_text("x = 1\n")

    result = _run_cli([".", "--json"], cwd=tmp_path)
    assert json.loads(result.stdout) == []
    assert result.returncode == 0


def test_cli_config_severity_override_reflected_in_json(tmp_path):
    (tmp_path / "pyvibe.toml").write_text(
        '[tool.pyvibe.severity]\nPYVIBE-008 = "warning"\n'
    )
    (tmp_path / "app.py").write_text(SQLITE_SRC)

    result = _run_cli([".", "--json"], cwd=tmp_path)
    output = json.loads(result.stdout)
    assert len(output) == 1
    assert output[0]["severity"] == "WARNING"
    assert result.returncode == 1


def test_cli_config_invalid_severity_exits_2(tmp_path):
    (tmp_path / "pyvibe.toml").write_text(
        '[tool.pyvibe.severity]\nPYVIBE-008 = "banana"\n'
    )
    (tmp_path / "app.py").write_text("x = 1\n")

    result = _run_cli(["."], cwd=tmp_path)
    assert result.returncode == 2
    assert "invalid severity" in result.stderr


def test_cli_config_malformed_toml_exits_2(tmp_path):
    (tmp_path / "pyvibe.toml").write_text("not [ valid toml\n")
    (tmp_path / "app.py").write_text("x = 1\n")

    result = _run_cli(["."], cwd=tmp_path)
    assert result.returncode == 2
    assert "Failed to parse" in result.stderr


def test_cli_summary_shows_reported_and_suppressed_counts(tmp_path):
    (tmp_path / "pyvibe.toml").write_text('[tool.pyvibe]\nignore = ["PYVIBE-019"]\n')
    (tmp_path / "app.py").write_text(RETRY_NO_BACKOFF_SRC + "\n" + SQLITE_SRC)

    result = _run_cli(["."], cwd=tmp_path)
    assert "1 reported · 1 suppressed" in result.stdout


def test_cli_verbose_lists_suppressed_findings_with_reason(tmp_path):
    (tmp_path / "pyvibe.toml").write_text('[tool.pyvibe]\nignore = ["PYVIBE-019"]\n')
    (tmp_path / "app.py").write_text(RETRY_NO_BACKOFF_SRC)

    result = _run_cli([".", "--verbose"], cwd=tmp_path)
    assert "Suppressed:" in result.stdout
    assert "PYVIBE-019 app.py:5 (config)" in result.stdout


def test_cli_verbose_lists_inline_suppressed_findings(tmp_path):
    (tmp_path / "app.py").write_text(
        'import sqlite3\n\nasync def handler():\n'
        '    conn = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-008\n'
    )

    result = _run_cli([".", "--verbose"], cwd=tmp_path)
    assert "PYVIBE-008 app.py:4 (inline)" in result.stdout
    assert "0 reported · 1 suppressed" in result.stdout


def test_cli_without_verbose_does_not_list_suppressed_details(tmp_path):
    (tmp_path / "pyvibe.toml").write_text('[tool.pyvibe]\nignore = ["PYVIBE-019"]\n')
    (tmp_path / "app.py").write_text(RETRY_NO_BACKOFF_SRC)

    result = _run_cli(["."], cwd=tmp_path)
    assert "Suppressed:" not in result.stdout
    assert "0 reported · 1 suppressed" in result.stdout


def test_cli_scan_subcommand_respects_config_and_verbose(tmp_path):
    (tmp_path / "pyvibe.toml").write_text('[tool.pyvibe]\nignore = ["PYVIBE-019"]\n')
    (tmp_path / "app.py").write_text(RETRY_NO_BACKOFF_SRC)

    result = _run_cli(["scan", ".", "--verbose"], cwd=tmp_path)
    assert "PYVIBE-019 app.py:5 (config)" in result.stdout
    assert result.returncode == 0
