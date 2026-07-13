"""Inline suppression comments — `# pyvibe: ignore PYVIBE-XXX[, PYVIBE-YYY]`
and `# pyvibe: ignore-next-line PYVIBE-XXX`, optionally followed by
`-- justification text`:

    # pyvibe: ignore PYVIBE-008 -- legacy sqlite wrapper
    # pyvibe: ignore-next-line PYVIBE-008 -- startup only

Parsed directly from the source text being analyzed (no filesystem I/O),
so — unlike pyvibe.toml (see pyvibe/config.py) — this is always active with
no opt-in required.
"""
import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set

_DIRECTIVE_RE = re.compile(
    r"#\s*pyvibe\s*:\s*(?P<directive>ignore-next-line|ignore)\b(?P<rest>[^\n]*)",
    re.IGNORECASE,
)
_RULE_ID_RE = re.compile(r"PYVIBE-\d{3}", re.IGNORECASE)


@dataclass(frozen=True)
class SuppressionDirective:
    """A single parsed `# pyvibe: ignore ...` comment.

    comment_line: the physical line the comment itself is written on.
    target_line: the line whose violations it suppresses (see module-level
    ignore/ignore-next-line semantics below).
    directive: "ignore" or "ignore-next-line", as written.
    rule_ids: the rule IDs named in the directive (never empty).
    justification: free text after `--`, or None if not given.
    """

    comment_line: int
    target_line: int
    directive: str
    rule_ids: FrozenSet[str]
    justification: Optional[str]


def parse_inline_suppression_directives(source: str) -> List[SuppressionDirective]:
    """Returns every `# pyvibe: ignore[-next-line] ...` directive found in
    `source`, in file order.

    A directive comment is "standalone" if nothing but whitespace precedes
    the `#` on its physical line; otherwise it's "trailing" on a code line.

    - `ignore-next-line` always targets the line right after the comment.
    - `ignore` targets its OWN line when trailing on code (the common case:
      `conn = sqlite3.connect(...)  # pyvibe: ignore PYVIBE-008`), or the
      FOLLOWING line when standalone — so a bare `# pyvibe: ignore X` on its
      own line directly above the flagged code also works, same as
      `ignore-next-line`.
    """
    directives: List[SuppressionDirective] = []

    for lineno, line in enumerate(source.splitlines(), start=1):
        match = _DIRECTIVE_RE.search(line)
        if not match:
            continue

        rest = match.group("rest")
        if "--" in rest:
            rule_part, justification_part = rest.split("--", 1)
            justification = justification_part.strip() or None
        else:
            rule_part, justification = rest, None

        rule_ids = frozenset(rid.upper() for rid in _RULE_ID_RE.findall(rule_part))
        if not rule_ids:
            continue  # directive with no recognizable rule ID — not our comment

        directive = match.group("directive").lower()
        is_standalone = line[: match.start()].strip() == ""

        target_line = lineno + 1 if (directive == "ignore-next-line" or is_standalone) else lineno

        directives.append(
            SuppressionDirective(
                comment_line=lineno,
                target_line=target_line,
                directive=directive,
                rule_ids=rule_ids,
                justification=justification,
            )
        )

    return directives


def parse_inline_suppressions(source: str) -> Dict[int, FrozenSet[str]]:
    """Returns {line_number: {rule_id, ...}} — 1-indexed line numbers whose
    violations should be suppressed. See parse_inline_suppression_directives()
    for the full per-directive detail (justification, comment line, etc.).
    """
    suppressions: Dict[int, Set[str]] = {}

    for directive in parse_inline_suppression_directives(source):
        suppressions.setdefault(directive.target_line, set()).update(directive.rule_ids)

    return {line: frozenset(ids) for line, ids in suppressions.items()}
