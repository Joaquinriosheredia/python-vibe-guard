"""Tests for PR review mode (pyvibe/diff.py + `pyvibe review` CLI subcommand)."""
import json
import subprocess
import sys
from pathlib import Path

import sys as _sys
import os

_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from pyvibe.analyzer import analyze_file
from pyvibe.diff import GitDiffError, get_changed_python_files, parse_diff

REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── parse_diff() unit tests ───────────────────────────────────────────────

def test_parse_diff_tracks_only_added_lines():
    diff_text = """\
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 import time

 async def handler():
+    time.sleep(1)
"""
    result = parse_diff(diff_text)
    assert result == {"app.py": frozenset({4})}


def test_parse_diff_ignores_removed_lines():
    diff_text = """\
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,4 +1,3 @@
 import time

 async def handler():
-    time.sleep(1)
"""
    result = parse_diff(diff_text)
    assert result == {}


def test_parse_diff_advances_line_numbers_through_context():
    diff_text = """\
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,5 @@
 line one
 line two
+added at three
 line four
+added at five
"""
    result = parse_diff(diff_text)
    assert result == {"app.py": frozenset({3, 5})}


def test_parse_diff_ignores_non_python_files():
    diff_text = """\
diff --git a/README.md b/README.md
index 1111111..2222222 100644
--- a/README.md
+++ b/README.md
@@ -1,1 +1,2 @@
 hello
+world
"""
    result = parse_diff(diff_text)
    assert result == {}


def test_parse_diff_handles_multiple_files():
    diff_text = """\
diff --git a/a.py b/a.py
index 1111111..2222222 100644
--- a/a.py
+++ b/a.py
@@ -1,1 +1,2 @@
 x = 1
+y = 2
diff --git a/b.py b/b.py
index 3333333..4444444 100644
--- a/b.py
+++ b/b.py
@@ -1,1 +1,2 @@
 z = 1
+w = 2
"""
    result = parse_diff(diff_text)
    assert result == {"a.py": frozenset({2}), "b.py": frozenset({2})}


def test_parse_diff_new_file_reports_all_added_lines():
    diff_text = """\
diff --git a/new.py b/new.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+import os
+print(os.getcwd())
"""
    result = parse_diff(diff_text)
    assert result == {"new.py": frozenset({1, 2})}


def test_parse_diff_deleted_file_reports_nothing():
    diff_text = """\
diff --git a/gone.py b/gone.py
deleted file mode 100644
index 1111111..0000000
--- a/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-import os
-print(os.getcwd())
"""
    result = parse_diff(diff_text)
    assert result == {}


def test_get_changed_python_files_rejects_flag_like_base():
    with pytest.raises(GitDiffError, match="Invalid base ref"):
        get_changed_python_files("--upload-pack=evil")


# ─── analyze_file(line_filter=...) unit tests ──────────────────────────────

VIOLATION_SRC = """\
import time

async def handler():
    time.sleep(5)
"""


def test_analyze_file_line_filter_keeps_matching_line(tmp_path):
    src = tmp_path / "bad.py"
    src.write_text(VIOLATION_SRC)

    violations = analyze_file(src, line_filter=frozenset({4}))
    assert len(violations) == 1
    assert violations[0].line == 4


def test_analyze_file_line_filter_excludes_non_matching_line(tmp_path):
    src = tmp_path / "bad.py"
    src.write_text(VIOLATION_SRC)

    violations = analyze_file(src, line_filter=frozenset({99}))
    assert violations == []


def test_analyze_file_without_line_filter_returns_everything(tmp_path):
    src = tmp_path / "bad.py"
    src.write_text(VIOLATION_SRC)

    violations = analyze_file(src)
    assert len(violations) == 1


# ─── `pyvibe review` CLI (subprocess, end-to-end against a real git repo) ──

def _run_cli(args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "pyvibe", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(cwd):
    _git(["init", "-q"], cwd)
    _git(["config", "user.email", "test@test.com"], cwd)
    _git(["config", "user.name", "Test"], cwd)


def test_cli_review_reports_only_added_violation(tmp_path):
    _init_repo(tmp_path)
    app = tmp_path / "app.py"
    app.write_text("import time\n\ndef handler():\n    print('ok')\n")
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "initial"], tmp_path)

    app.write_text(
        "import time\n\ndef handler():\n    print('ok')\n\n"
        "async def process_order():\n    time.sleep(2)\n"
    )

    result = _run_cli(["review", "--base", "HEAD"], cwd=tmp_path)

    assert result.returncode == 1
    assert "PYVIBE-001" in result.stdout
    assert "line 7" in result.stdout


def test_cli_review_ignores_preexisting_violation_outside_diff(tmp_path):
    _init_repo(tmp_path)
    app = tmp_path / "app.py"
    app.write_text(
        "import time\n\nasync def handler():\n"
        "    time.sleep(1)\n    print('existing violation, untouched')\n"
    )
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "baseline with pre-existing violation"], tmp_path)

    with app.open("a") as f:
        f.write("\ndef other():\n    print('unrelated new function')\n")

    full_scan = _run_cli(["app.py", "--json"], cwd=tmp_path)
    assert len(json.loads(full_scan.stdout)) == 1

    review = _run_cli(["review", "--base", "HEAD"], cwd=tmp_path)
    assert review.returncode == 0
    assert "No violations found" in review.stdout


def test_cli_review_clean_diff_exits_zero(tmp_path):
    _init_repo(tmp_path)
    app = tmp_path / "app.py"
    app.write_text("def handler():\n    pass\n")
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "initial"], tmp_path)

    app.write_text("def handler():\n    pass\n\n\ndef other():\n    pass\n")

    result = _run_cli(["review", "--base", "HEAD"], cwd=tmp_path)
    assert result.returncode == 0
    assert "No violations found" in result.stdout


def test_cli_review_json_output(tmp_path):
    _init_repo(tmp_path)
    app = tmp_path / "app.py"
    app.write_text("def handler():\n    pass\n")
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "initial"], tmp_path)

    app.write_text(
        "def handler():\n    pass\n\nasync def process_order():\n    import time\n    time.sleep(2)\n"
    )

    result = _run_cli(["review", "--base", "HEAD", "--json"], cwd=tmp_path)
    output = json.loads(result.stdout)
    assert len(output) == 1
    assert output[0]["rule"] == "PYVIBE-001"
    assert output[0]["file"] == "app.py"


def test_cli_review_sarif_output(tmp_path):
    _init_repo(tmp_path)
    app = tmp_path / "app.py"
    app.write_text("def handler():\n    pass\n")
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "initial"], tmp_path)

    app.write_text(
        "def handler():\n    pass\n\nasync def process_order():\n    import time\n    time.sleep(2)\n"
    )

    out = tmp_path / "out.sarif"
    result = _run_cli(
        ["review", "--base", "HEAD", "--sarif", "--sarif-output", str(out)], cwd=tmp_path
    )
    assert result.returncode == 1
    assert out.exists()
    sarif = json.loads(out.read_text())
    assert sarif["runs"][0]["results"][0]["ruleId"] == "PYVIBE-001"


def test_cli_review_invalid_base_exits_2(tmp_path):
    _init_repo(tmp_path)
    app = tmp_path / "app.py"
    app.write_text("def handler():\n    pass\n")
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "initial"], tmp_path)

    result = _run_cli(["review", "--base", "not-a-real-ref"], cwd=tmp_path)
    assert result.returncode == 2
    assert "Error" in result.stderr
