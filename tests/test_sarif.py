"""Tests for SARIF 2.1.0 output (pyvibe/sarif.py + --sarif CLI flag)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import sys as _sys
import os

_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyvibe.analyzer import ALL_RULE_IDS, analyze_source
from pyvibe.sarif import build_sarif

REPO_ROOT = Path(__file__).resolve().parent.parent

VIOLATION_SRC = """\
import time

async def handler():
    time.sleep(5)
"""

CLEAN_SRC = """\
def handler():
    pass
"""


# ─── build_sarif() unit tests ──────────────────────────────────────────────

def test_sarif_schema_version():
    sarif = build_sarif({})
    assert sarif["version"] == "2.1.0"
    assert sarif["$schema"].endswith("sarif-schema-2.1.0.json")


def test_sarif_rule_catalog_lists_all_rules_even_with_no_hits():
    sarif = build_sarif({})
    rule_ids = {r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert rule_ids == set(ALL_RULE_IDS)
    assert sarif["runs"][0]["results"] == []


def test_sarif_rule_descriptor_has_help_uri_pointing_to_research_doc():
    sarif = build_sarif({})
    rules_by_id = {r["id"]: r for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    rule = rules_by_id["PYVIBE-001"]
    assert rule["helpUri"].endswith("research/accepted/PYVIBE-001.md")
    assert rule["shortDescription"]["text"]
    assert rule["fullDescription"]["text"]


def test_sarif_result_has_ruleid_message_and_location():
    violations = analyze_source(VIOLATION_SRC, filepath="handler.py")
    sarif = build_sarif({Path("handler.py"): violations})
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    result = results[0]
    assert result["ruleId"] == "PYVIBE-001"
    assert result["level"] == "error"
    assert "message" in result and result["message"]["text"]
    loc = result["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "handler.py"
    assert loc["region"]["startLine"] == 4


def test_sarif_level_reflects_downgraded_severity():
    # PYVIBE-001 is downgraded to WARNING inside test files by default.
    violations = analyze_source(VIOLATION_SRC, filepath="tests/test_handler.py")
    sarif = build_sarif({Path("tests/test_handler.py"): violations})
    result = sarif["runs"][0]["results"][0]
    assert result["level"] == "warning"


# ─── --sarif CLI flag (subprocess, end-to-end) ─────────────────────────────

def _run_cli(args, cwd=REPO_ROOT):
    return subprocess.run(
        [sys.executable, "-m", "pyvibe", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_cli_sarif_flag_writes_file_with_same_exit_code_as_json():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "bad.py"
        src.write_text(VIOLATION_SRC)
        out = Path(tmp) / "out.sarif"

        result = _run_cli([str(src), "--sarif", "--sarif-output", str(out)])
        json_result = _run_cli([str(src), "--json"])

        assert result.returncode == json_result.returncode == 1
        assert out.exists()
        sarif = json.loads(out.read_text())
        assert sarif["version"] == "2.1.0"
        assert len(sarif["runs"][0]["results"]) == 1
        assert sarif["runs"][0]["results"][0]["ruleId"] == "PYVIBE-001"


def test_cli_sarif_flag_clean_scan_exits_zero():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "clean.py"
        src.write_text(CLEAN_SRC)
        out = Path(tmp) / "out.sarif"

        result = _run_cli([str(src), "--sarif", "--sarif-output", str(out)])

        assert result.returncode == 0
        sarif = json.loads(out.read_text())
        assert sarif["runs"][0]["results"] == []
        assert len(sarif["runs"][0]["tool"]["driver"]["rules"]) == 20
