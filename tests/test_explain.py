"""Tests for `pyvibe explain PYVIBE-XXX` (pyvibe/explain.py + CLI subcommand)."""
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from pyvibe.analyzer import ALL_RULE_IDS
from pyvibe.explain import EvidenceNotFoundError, explain_rule, normalize_rule_id

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SECTIONS = [
    "Problema",
    "Por qué ocurre",
    "Visto en",
    "Nivel de evidencia",
    "Precisión auditada",
    "Falsos positivos conocidos",
    "Fix sugerido",
]


# ─── normalize_rule_id ──────────────────────────────────────────────────────

def test_normalize_rule_id_passthrough():
    assert normalize_rule_id("PYVIBE-002") == "PYVIBE-002"


def test_normalize_rule_id_lowercase():
    assert normalize_rule_id("pyvibe-002") == "PYVIBE-002"


def test_normalize_rule_id_numeric_shorthand():
    assert normalize_rule_id("2") == "PYVIBE-002"
    assert normalize_rule_id("20") == "PYVIBE-020"


# ─── explain_rule() unit tests ──────────────────────────────────────────────

def test_explain_rule_missing_file_raises_clear_error():
    with pytest.raises(EvidenceNotFoundError, match="No evidence file found for PYVIBE-999"):
        explain_rule("PYVIBE-999")


def test_explain_rule_rejects_path_traversal():
    """rule_id is a raw CLI arg — must never escape research/accepted/."""
    with pytest.raises(EvidenceNotFoundError):
        explain_rule("../../../../etc/passwd")
    with pytest.raises(EvidenceNotFoundError):
        explain_rule("../../README")


@pytest.mark.parametrize("rule_id", sorted(ALL_RULE_IDS))
def test_explain_rule_covers_every_accepted_rule(rule_id):
    """Every shipped rule has a research doc and produces all 7 sections."""
    text = explain_rule(rule_id)
    for section in REQUIRED_SECTIONS:
        assert section in text, f"{rule_id}: missing section {section!r}"


def test_explain_rule_fix_is_not_generic_placeholder():
    text = explain_rule("PYVIBE-002")
    assert "httpx.AsyncClient" in text or "aiohttp" in text


def test_explain_rule_005_fix_extracted_despite_shared_paragraph():
    # Regression: PYVIBE-005's "Fix:" line shares a paragraph with the
    # preceding sentence in the docstring (no blank line separator).
    text = explain_rule("PYVIBE-005")
    assert "soft_time_limit=30" in text
    assert "See rule source for fix guidance." not in text


def test_explain_rule_reports_repo_percentage():
    text = explain_rule("PYVIBE-002")
    assert "%" in text
    assert "250" in text


# ─── CLI subcommand (subprocess, end-to-end) ────────────────────────────────

def _run_cli(args, cwd=REPO_ROOT):
    return subprocess.run(
        [sys.executable, "-m", "pyvibe", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_cli_explain_known_rule_exits_zero():
    result = _run_cli(["explain", "PYVIBE-002"])
    assert result.returncode == 0
    assert "PYVIBE-002" in result.stdout
    for section in REQUIRED_SECTIONS:
        assert section in result.stdout


def test_cli_explain_unknown_rule_prints_clear_message_and_exits_nonzero():
    result = _run_cli(["explain", "PYVIBE-999"])
    assert result.returncode == 1
    assert "No evidence file found for PYVIBE-999" in result.stdout


def test_cli_explain_normalizes_numeric_shorthand():
    result = _run_cli(["explain", "2"])
    assert result.returncode == 0
    assert "PYVIBE-002" in result.stdout
