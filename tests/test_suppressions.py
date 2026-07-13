"""Tests for inline suppression comments (pyvibe/suppressions.py +
analyze_source_full's inline-suppression handling in pyvibe/analyzer.py)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyvibe.analyzer import analyze_source, analyze_source_full
from pyvibe.suppressions import parse_inline_suppressions


# ─── parse_inline_suppressions() unit tests ────────────────────────────────

def test_trailing_comment_targets_its_own_line():
    src = 'conn = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-008\n'
    assert parse_inline_suppressions(src) == {1: frozenset({"PYVIBE-008"})}


def test_standalone_comment_targets_next_line():
    src = "# pyvibe: ignore PYVIBE-008\nconn = sqlite3.connect(\"x\")\n"
    assert parse_inline_suppressions(src) == {2: frozenset({"PYVIBE-008"})}


def test_ignore_next_line_targets_next_line():
    src = "# pyvibe: ignore-next-line PYVIBE-008\nconn = sqlite3.connect(\"x\")\n"
    assert parse_inline_suppressions(src) == {2: frozenset({"PYVIBE-008"})}


def test_ignore_next_line_still_targets_next_line_when_trailing():
    # explicit directive name always means "next line", even if written as
    # a trailing comment on a code line (edge case, but unambiguous).
    src = "x = 1  # pyvibe: ignore-next-line PYVIBE-008\nconn = sqlite3.connect(\"x\")\n"
    assert parse_inline_suppressions(src) == {2: frozenset({"PYVIBE-008"})}


def test_multiple_rule_ids_comma_separated():
    src = 'time.sleep(1)  # pyvibe: ignore PYVIBE-001, PYVIBE-003\n'
    assert parse_inline_suppressions(src) == {1: frozenset({"PYVIBE-001", "PYVIBE-003"})}


def test_case_insensitive_pyvibe_prefix():
    src = 'conn = sqlite3.connect("x")  # PyVibe: IGNORE PYVIBE-008\n'
    assert parse_inline_suppressions(src) == {1: frozenset({"PYVIBE-008"})}


def test_case_insensitive_rule_id():
    src = 'conn = sqlite3.connect("x")  # pyvibe: ignore pyvibe-008\n'
    assert parse_inline_suppressions(src) == {1: frozenset({"PYVIBE-008"})}


def test_directive_without_rule_id_is_noop():
    src = "# pyvibe: ignore\nconn = sqlite3.connect(\"x\")\n"
    assert parse_inline_suppressions(src) == {}


def test_line_without_directive_is_ignored():
    src = "x = 1  # just a regular comment\n"
    assert parse_inline_suppressions(src) == {}


def test_multiple_directives_across_file_accumulate():
    src = (
        'a = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-008\n'
        "\n"
        "# pyvibe: ignore-next-line PYVIBE-001\n"
        "time.sleep(1)\n"
    )
    assert parse_inline_suppressions(src) == {
        1: frozenset({"PYVIBE-008"}),
        4: frozenset({"PYVIBE-001"}),
    }


# ─── analyze_source_full() / analyze_source() integration ─────────────────

TRAILING_SRC = """\
import sqlite3

async def handler():
    conn = sqlite3.connect("db.sqlite")  # pyvibe: ignore PYVIBE-008
"""

STANDALONE_SRC = """\
import sqlite3

async def handler():
    # pyvibe: ignore PYVIBE-008
    conn = sqlite3.connect("db.sqlite")
"""

IGNORE_NEXT_LINE_SRC = """\
import sqlite3

async def handler():
    # pyvibe: ignore-next-line PYVIBE-008
    conn = sqlite3.connect("db.sqlite")
"""

MULTI_RULE_SRC = """\
import time

async def handler():
    time.sleep(1)  # pyvibe: ignore PYVIBE-001, PYVIBE-003
"""


def test_inline_trailing_suppresses_violation():
    reported, suppressed = analyze_source_full(TRAILING_SRC, filepath="app.py")
    assert reported == []
    assert [(v.rule_id, v.line, reason) for v, reason in suppressed] == [
        ("PYVIBE-008", 4, "inline")
    ]


def test_inline_standalone_suppresses_next_line():
    reported, suppressed = analyze_source_full(STANDALONE_SRC, filepath="app.py")
    assert reported == []
    assert [(v.rule_id, v.line, reason) for v, reason in suppressed] == [
        ("PYVIBE-008", 5, "inline")
    ]


def test_inline_ignore_next_line_suppresses_next_line():
    reported, suppressed = analyze_source_full(IGNORE_NEXT_LINE_SRC, filepath="app.py")
    assert reported == []
    assert [(v.rule_id, v.line, reason) for v, reason in suppressed] == [
        ("PYVIBE-008", 5, "inline")
    ]


def test_inline_multiple_rule_ids_both_suppressed():
    reported, suppressed = analyze_source_full(MULTI_RULE_SRC, filepath="app.py")
    assert reported == []
    assert [(v.rule_id, v.line, reason) for v, reason in suppressed] == [
        ("PYVIBE-001", 4, "inline")
    ]


def test_inline_suppression_is_specific_to_rule_id():
    # suppressing PYVIBE-999 (nonexistent / unrelated) must NOT touch the
    # real PYVIBE-008 violation on the same line.
    src = (
        "import sqlite3\n\n"
        "async def handler():\n"
        '    conn = sqlite3.connect("x")  # pyvibe: ignore PYVIBE-999\n'
    )
    reported, suppressed = analyze_source_full(src, filepath="app.py")
    assert len(reported) == 1
    assert reported[0].rule_id == "PYVIBE-008"
    assert suppressed == []


def test_analyze_source_public_api_returns_only_reported():
    # analyze_source() (used pervasively elsewhere) must keep returning
    # ONLY the reported violations, exactly like before this feature existed.
    violations = analyze_source(TRAILING_SRC, filepath="app.py")
    assert violations == []
