"""Diff parsing for `pyvibe review` — extracts changed .py files and the
new-file line numbers touched by a `git diff`, so review only reports
violations on lines that are actually part of the diff (deleted lines and
untouched context are never reported).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, FrozenSet, Optional

_PLUS_PLUS_RE = re.compile(r"^\+\+\+ (?:b/(?P<path>.+)|(?P<devnull>/dev/null))$")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<new_start>\d+)(?:,\d+)? @@")


class GitDiffError(Exception):
    """Raised when `git diff`/`git rev-parse` can't be run or the base ref is invalid."""


def get_repo_root(cwd: Optional[Path] = None) -> Path:
    """Resolve the top-level directory of the current git repository.

    Needed because `git diff` always reports paths relative to the repo
    root, not the caller's cwd — file paths from the diff must be resolved
    against this root, not against Path.cwd().
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitDiffError("Not inside a git repository")
    return Path(result.stdout.strip())


def get_git_diff(base: str, cwd: Optional[Path] = None) -> str:
    """Run `git diff <base> -- '*.py'` and return its raw text output.

    Only ever invoked with a list-form subprocess call (no shell=True), so
    `base` can't break out into arbitrary shell commands. It's still
    rejected up front if it looks like a flag, since git itself would
    otherwise interpret e.g. "--upload-pack=..." as an option rather than
    a ref.
    """
    if base.startswith("-"):
        raise GitDiffError(f"Invalid base ref: {base!r}")

    try:
        result = subprocess.run(
            ["git", "diff", base, "--", "*.py"],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        raise GitDiffError("git executable not found") from e

    if result.returncode != 0:
        raise GitDiffError(result.stderr.strip() or f"git diff failed for base {base!r}")

    return result.stdout


def parse_diff(diff_text: str) -> Dict[str, FrozenSet[int]]:
    """Parse unified `git diff` output into {file_path: {added_line_numbers}}.

    Only .py files are kept. Deleted lines (prefix "-") and unchanged
    context lines never appear in the result — only lines that are actually
    added/modified in the new version of the file.
    """
    files: Dict[str, set] = {}
    current_file: Optional[str] = None
    current_line: Optional[int] = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_file = None
            current_line = None
            continue

        if line.startswith("+++ "):
            m = _PLUS_PLUS_RE.match(line)
            current_file = m.group("path") if (m and m.group("path")) else None
            current_line = None
            continue

        if current_file is None or not current_file.endswith(".py"):
            continue

        hunk_match = _HUNK_RE.match(line)
        if hunk_match:
            current_line = int(hunk_match.group("new_start"))
            continue

        if current_line is None:
            continue

        if line.startswith("\\"):
            continue  # "\ No newline at end of file"
        elif line.startswith("+"):
            files.setdefault(current_file, set()).add(current_line)
            current_line += 1
        elif line.startswith("-"):
            continue  # removed line — doesn't exist in the new file
        else:
            current_line += 1  # unchanged context line

    return {path: frozenset(lines) for path, lines in files.items()}


def get_changed_python_files(base: str, cwd: Optional[Path] = None) -> Dict[str, FrozenSet[int]]:
    """High-level entry point used by `pyvibe review`.

    Returns {repo-relative path: {added line numbers}} for every .py file
    touched in `git diff <base>`.
    """
    diff_text = get_git_diff(base, cwd=cwd)
    return parse_diff(diff_text)
