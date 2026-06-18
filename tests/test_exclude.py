"""Tests for --exclude / directory exclusion in analyze_directory."""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyvibe.analyzer import analyze_directory, DEFAULT_EXCLUDES


# ─── helpers ─────────────────────────────────────────────────────────────────

VIOLATION_SRC = """\
import time

async def handler():
    time.sleep(5)
"""

CLEAN_SRC = """\
def handler():
    pass
"""


def _make_tree(root: Path, layout: dict):
    """Recursively create files/dirs from a nested dict."""
    for name, content in layout.items():
        path = root / name
        if isinstance(content, dict):
            path.mkdir(parents=True, exist_ok=True)
            _make_tree(path, content)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)


# ─── default excludes ─────────────────────────────────────────────────────────

def test_default_excludes_venv():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "src": {"app.py": CLEAN_SRC},
            "venv": {"site-packages": {"bad.py": VIOLATION_SRC}},
        })
        results = analyze_directory(root)
        # venv/ must be skipped — zero violations
        assert results == {}


def test_default_excludes_dot_venv():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "src": {"app.py": CLEAN_SRC},
            ".venv": {"lib": {"bad.py": VIOLATION_SRC}},
        })
        results = analyze_directory(root)
        assert results == {}


def test_default_excludes_pycache():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "src": {
                "app.py": CLEAN_SRC,
                "__pycache__": {"app.cpython-311.pyc.py": VIOLATION_SRC},
            },
        })
        results = analyze_directory(root)
        assert results == {}


def test_default_excludes_multiple_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "mypackage": {"real.py": CLEAN_SRC},
            "venv":         {"a.py": VIOLATION_SRC},
            ".venv":        {"b.py": VIOLATION_SRC},
            "__pycache__":  {"c.py": VIOLATION_SRC},
            ".tox":         {"d.py": VIOLATION_SRC},
            "dist":         {"e.py": VIOLATION_SRC},
            "build":        {"f.py": VIOLATION_SRC},
            ".eggs":        {"g.py": VIOLATION_SRC},
            "node_modules": {"h.py": VIOLATION_SRC},
            ".git":         {"i.py": VIOLATION_SRC},
            "env":          {"j.py": VIOLATION_SRC},
        })
        results = analyze_directory(root)
        assert results == {}


def test_source_files_still_scanned_with_defaults():
    """Verify that the walker does reach project source files."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "src": {"bad.py": VIOLATION_SRC},
            "venv": {"ok.py": CLEAN_SRC},
        })
        results = analyze_directory(root)
        assert len(results) == 1
        assert any("bad.py" in str(k) for k in results)


# ─── custom --exclude ─────────────────────────────────────────────────────────

def test_custom_exclude_additional_dir():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "src": {"app.py": CLEAN_SRC},
            "third_party": {"vendor.py": VIOLATION_SRC},
        })
        custom = DEFAULT_EXCLUDES | frozenset({"third_party"})
        results = analyze_directory(root, exclude=custom)
        assert results == {}


def test_custom_exclude_does_not_remove_defaults():
    """Adding a custom exclude keeps all defaults active."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "src": {"app.py": CLEAN_SRC},
            "venv": {"bad.py": VIOLATION_SRC},
            "custom_dir": {"also_bad.py": VIOLATION_SRC},
        })
        custom = DEFAULT_EXCLUDES | frozenset({"custom_dir"})
        results = analyze_directory(root, exclude=custom)
        assert results == {}


def test_exclude_only_by_directory_name():
    """Exclusion matches directory *name*, not file names."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "src": {
                "venv.py": VIOLATION_SRC,  # file named venv.py — must NOT be excluded
            },
        })
        results = analyze_directory(root)
        # venv.py is a *file*, not a directory — it should be scanned
        assert len(results) == 1
        assert any("venv.py" in str(k) for k in results)


def test_nested_excluded_dir_skipped():
    """Excluded directories anywhere in the tree are skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root, {
            "src": {
                "module": {
                    "ok.py": CLEAN_SRC,
                    "venv": {"deep.py": VIOLATION_SRC},  # nested venv
                },
            },
        })
        results = analyze_directory(root)
        assert results == {}


# ─── DEFAULT_EXCLUDES contents ────────────────────────────────────────────────

def test_default_excludes_set_contains_expected():
    expected = {"venv", ".venv", "env", "__pycache__", ".git",
                "node_modules", ".tox", "dist", "build", ".eggs"}
    assert expected <= DEFAULT_EXCLUDES
