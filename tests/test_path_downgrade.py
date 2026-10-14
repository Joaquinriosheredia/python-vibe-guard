"""Point (c) of FASE1-DISENO.md (decision 2026-10-14): a CRITICAL finding whose
path has a non-production directory segment (tests/, test/, scripts/, wip/,
spike/, examples/ — full-segment match) is downgraded to WARNING, never silenced.
`com/example/` (segment `example`, not `examples`) and a filename that merely
contains `tests` are NOT downgraded.

Regression fixtures cite vibe-guard-evaluation dev-labels.json; the matcher unit
tests are mechanism tests (including the two mandatory negatives).
"""
import pytest

from pyvibe.analyzer import analyze_source

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
