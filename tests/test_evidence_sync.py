"""The evidence `pyvibe explain` reads ships inside the package
(pyvibe/_evidence/, mirrored from research/ by scripts/sync_evidence.py), so
explain works from a PyPI install and not only from a source checkout."""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyvibe
from pyvibe import explain
from pyvibe.analyzer import ALL_RULES

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_sync_script():
    spec = importlib.util.spec_from_file_location(
        "sync_evidence", REPO_ROOT / "scripts" / "sync_evidence.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(
    not (REPO_ROOT / "research").is_dir() or not (REPO_ROOT / "scripts").is_dir(),
    reason="needs a git checkout: research/ and scripts/ are not shipped in the sdist",
)
def test_packaged_evidence_matches_research():
    stale = _load_sync_script().stale_files()
    assert stale == [], (
        "pyvibe/_evidence/ diverges from research/ — run "
        "`python scripts/sync_evidence.py`:\n" + "\n".join(stale)
    )


def test_every_rule_has_packaged_evidence():
    for cls in ALL_RULES:
        assert explain._accepted_path(cls.RULE_ID).is_file(), cls.RULE_ID
    assert explain._precision_audit_path().is_file()


def test_explain_reads_from_inside_the_package():
    # A wheel only contains pyvibe/ — any path outside it would break a PyPI install.
    package_dir = Path(pyvibe.__file__).resolve().parent
    assert package_dir in explain._accepted_path("PYVIBE-001").parents
    assert package_dir in explain._precision_audit_path().parents


def test_explain_full_report_points_to_a_url_not_a_local_path():
    text = explain.explain_rule("PYVIBE-005")
    assert "Full report: https://github.com/" in text
    assert "Full report: research/" not in text
