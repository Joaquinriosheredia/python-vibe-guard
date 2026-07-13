"""Inline suppression comments — `# pyvibe: ignore PYVIBE-XXX[, PYVIBE-YYY]`
and `# pyvibe: ignore-next-line PYVIBE-XXX`.

Parsed directly from the source text being analyzed (no filesystem I/O),
so — unlike pyvibe.toml (see pyvibe/config.py) — this is always active with
no opt-in required.
"""
import re
from typing import Dict, FrozenSet, Set

_DIRECTIVE_RE = re.compile(
    r"#\s*pyvibe\s*:\s*(?P<directive>ignore-next-line|ignore)\b(?P<rule_ids>[^\n]*)",
    re.IGNORECASE,
)
_RULE_ID_RE = re.compile(r"PYVIBE-\d{3}", re.IGNORECASE)


def parse_inline_suppressions(source: str) -> Dict[int, FrozenSet[str]]:
    """Returns {line_number: {rule_id, ...}} — 1-indexed line numbers whose
    violations should be suppressed.

    A directive comment is "standalone" if nothing but whitespace precedes
    the `#` on its physical line; otherwise it's "trailing" on a code line.

    - `ignore-next-line` always targets the line right after the comment.
    - `ignore` targets its OWN line when trailing on code (the common case:
      `conn = sqlite3.connect(...)  # pyvibe: ignore PYVIBE-008`), or the
      FOLLOWING line when standalone — so a bare `# pyvibe: ignore X` on its
      own line directly above the flagged code also works, same as
      `ignore-next-line`.
    """
    suppressions: Dict[int, Set[str]] = {}

    for lineno, line in enumerate(source.splitlines(), start=1):
        match = _DIRECTIVE_RE.search(line)
        if not match:
            continue

        rule_ids = {rid.upper() for rid in _RULE_ID_RE.findall(match.group("rule_ids"))}
        if not rule_ids:
            continue  # directive with no recognizable rule ID — not our comment

        directive = match.group("directive").lower()
        is_standalone = line[: match.start()].strip() == ""

        if directive == "ignore-next-line" or is_standalone:
            target_line = lineno + 1
        else:
            target_line = lineno

        suppressions.setdefault(target_line, set()).update(rule_ids)

    return {line: frozenset(ids) for line, ids in suppressions.items()}
