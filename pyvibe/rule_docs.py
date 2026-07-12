"""Parses the English docstring every rule class already carries into
structured (title, mechanism, fix) fields.

Used by both `pyvibe explain` and SARIF rule-catalog generation so the
two surfaces never drift out of sync with each other.
"""
import inspect
import re
from typing import NamedTuple

_TITLE_PREFIX_RE = re.compile(r"^PYVIBE-\d+\s*—\s*")
_WHITESPACE_RE = re.compile(r"\s+")


class RuleDoc(NamedTuple):
    title: str
    why: str
    fix: str


def parse_rule_docstring(cls) -> RuleDoc:
    """Split a rule class's docstring into title / mechanism / fix.

    Docstring convention (see any file under pyvibe/rules/): the first
    paragraph is "PYVIBE-XXX — <title>", the closing paragraph starting
    with "Fix:" is the suggested fix, and everything in between explains
    the mechanism/runtime effect.
    """
    doc = inspect.getdoc(cls) or ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", doc) if p.strip()]
    if not paragraphs:
        rule_id = getattr(cls, "RULE_ID", "")
        return RuleDoc(title=rule_id, why="", fix="")

    title = _TITLE_PREFIX_RE.sub("", paragraphs[0].splitlines()[0]).strip()

    # The "Fix:" sentence is usually its own paragraph, but a couple of
    # rules (e.g. PYVIBE-005) tack it onto the end of the preceding
    # sentence with no blank line in between — so scan line-by-line
    # within each paragraph rather than requiring "Fix:" at paragraph start.
    fix = ""
    why_parts = []
    for para in paragraphs[1:]:
        plines = para.splitlines()
        fix_idx = next(
            (i for i, line in enumerate(plines) if line.strip().startswith("Fix:")),
            None,
        )
        if fix_idx is None or fix:
            why_parts.append(_WHITESPACE_RE.sub(" ", para))
            continue

        before_lines = plines[:fix_idx]
        fix_lines = list(plines[fix_idx:])
        fix_lines[0] = fix_lines[0].strip()[len("Fix:"):].strip()
        fix = _WHITESPACE_RE.sub(" ", " ".join(fix_lines)).strip()
        if before_lines:
            why_parts.append(_WHITESPACE_RE.sub(" ", " ".join(before_lines)).strip())

    return RuleDoc(
        title=title,
        why="\n\n".join(why_parts),
        fix=fix or "See rule source for fix guidance.",
    )
