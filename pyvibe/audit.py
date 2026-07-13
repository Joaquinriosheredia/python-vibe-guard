"""Suppressions audit — `pyvibe audit`.

Cross-references every `# pyvibe: ignore ...` directive found in a file
against that file's actual violations to answer three questions per
suppression: does it carry a justification, is it actually suppressing a
real violation (or is it "orphaned" — no violation of that rule ever
occurs on the target line), and how do these break down project-wide.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from pyvibe.analyzer import DEFAULT_EXCLUDES, _walk, analyze_source_full
from pyvibe.config import PyvibeConfig, is_excluded
from pyvibe.suppressions import parse_inline_suppression_directives


@dataclass(frozen=True)
class SuppressionRecord:
    """One inline suppression, exploded per rule_id (a directive naming
    multiple rule IDs — `# pyvibe: ignore PYVIBE-008, PYVIBE-019` — yields
    one record per rule ID, all sharing the same lines/justification).
    """

    filepath: str
    comment_line: int
    target_line: int
    directive: str
    rule_id: str
    justification: Optional[str]
    used: bool  # False == orphaned: no violation of rule_id found on target_line


def audit_file(path: Path, config: Optional[PyvibeConfig] = None) -> List[SuppressionRecord]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    _, suppressed = analyze_source_full(source, filepath=str(path), config=config)
    used_keys = {(v.line, v.rule_id) for v, reason in suppressed if reason == "inline"}

    records = []
    for directive in parse_inline_suppression_directives(source):
        for rule_id in sorted(directive.rule_ids):
            records.append(
                SuppressionRecord(
                    filepath=str(path),
                    comment_line=directive.comment_line,
                    target_line=directive.target_line,
                    directive=directive.directive,
                    rule_id=rule_id,
                    justification=directive.justification,
                    used=(directive.target_line, rule_id) in used_keys,
                )
            )
    return records


def audit_directory(
    root: Path,
    exclude: frozenset = DEFAULT_EXCLUDES,
    *,
    config: Optional[PyvibeConfig] = None,
) -> List[SuppressionRecord]:
    records: List[SuppressionRecord] = []
    for py_file in _walk(root, exclude):
        if config and is_excluded(py_file, config):
            continue
        records.extend(audit_file(py_file, config=config))
    return records


def audit_path(
    target: Path,
    exclude: frozenset = DEFAULT_EXCLUDES,
    *,
    config: Optional[PyvibeConfig] = None,
) -> List[SuppressionRecord]:
    """audit_file()/audit_directory(), dispatching on whether target is a
    file or a directory — same convention as analyzer.analyze_file/_directory.
    """
    if target.is_file():
        if target.suffix != ".py":
            return []
        if config and is_excluded(target, config):
            return []
        return audit_file(target, config=config)
    return audit_directory(target, exclude=exclude, config=config)


@dataclass(frozen=True)
class AuditSummary:
    total: int
    with_justification: int
    without_justification: int
    unused: int
    by_rule: Dict[str, int]
    unused_records: List[SuppressionRecord]
    unjustified_records: List[SuppressionRecord]


def summarize(records: List[SuppressionRecord]) -> AuditSummary:
    total = len(records)
    with_justification = sum(1 for r in records if r.justification)
    unjustified_records = [r for r in records if not r.justification]
    unused_records = [r for r in records if not r.used]

    by_rule: Dict[str, int] = {}
    for r in records:
        by_rule[r.rule_id] = by_rule.get(r.rule_id, 0) + 1
    # Most-suppressed rule first; rule_id ascending breaks ties.
    by_rule = dict(sorted(by_rule.items(), key=lambda kv: (-kv[1], kv[0])))

    return AuditSummary(
        total=total,
        with_justification=with_justification,
        without_justification=len(unjustified_records),
        unused=len(unused_records),
        by_rule=by_rule,
        unused_records=unused_records,
        unjustified_records=unjustified_records,
    )
