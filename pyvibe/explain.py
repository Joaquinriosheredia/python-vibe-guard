"""`pyvibe explain PYVIBE-XXX` — surfaces the research evidence behind a rule
in the terminal, so the CLI's "trust us" claims are one command away from
the actual data (research/accepted/PYVIBE-XXX.md, research/precision-audit.md).
"""
import re
from pathlib import Path
from typing import List, Optional

from pyvibe.analyzer import ALL_RULES
from pyvibe.rule_docs import parse_rule_docstring

RULES_BY_ID = {cls.RULE_ID: cls for cls in ALL_RULES}

_PCT_RE = re.compile(r"(\d+)/(\d+)\s*\(([\d.]+)%\)")
_EVIDENCE_RE = re.compile(r"Evidence Level:?\s*\*{0,2}\s*([A-D]\+?)\b")
_FP_SECTION_RE = re.compile(
    r"### Patrones de FP identificados\s*\n(.*?)(?=\n##|\Z)", re.DOTALL
)
_FP_PATTERN_NAME_RE = re.compile(r"\*\*([^*]+)\*\*\s*—")
_VALID_RULE_ID_RE = re.compile(r"^PYVIBE-\d{3}$")


class EvidenceNotFoundError(Exception):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _accepted_path(rule_id: str) -> Path:
    return _repo_root() / "research" / "accepted" / f"{rule_id}.md"


def _precision_audit_path() -> Path:
    return _repo_root() / "research" / "precision-audit.md"


def normalize_rule_id(raw: str) -> str:
    raw = raw.strip().upper()
    if raw.startswith("PYVIBE-"):
        return raw
    if raw.isdigit():
        return f"PYVIBE-{int(raw):03d}"
    return raw


def _extract_repo_percentage(doc_text: str) -> str:
    for line in doc_text.splitlines():
        if "Repos afectados" not in line:
            continue
        matches = _PCT_RE.findall(line)
        if not matches:
            return "not reported"
        count, sample, pct = max(matches, key=lambda m: int(m[1]))
        return f"{pct}% ({count}/{sample} repos, sweep-250 dataset)"
    return "not reported"


def _extract_evidence_level(doc_text: str) -> str:
    for line in doc_text.splitlines():
        if "Evidence Level" not in line:
            continue
        m = _EVIDENCE_RE.search(line)
        if m:
            return m.group(1)
    return "not documented"


def _extract_audit_row(rule_id: str) -> Optional[List[str]]:
    path = _precision_audit_path()
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(f"| {rule_id} "):
            return [c.strip() for c in stripped.strip("|").split("|")]
    return None


def _extract_precision(rule_id: str) -> str:
    row = _extract_audit_row(rule_id)
    if row and len(row) >= 8:
        return row[7]
    return "not audited"


def _extract_known_fps(doc_text: str, rule_id: str) -> str:
    m = _FP_SECTION_RE.search(doc_text)
    if m:
        names = _FP_PATTERN_NAME_RE.findall(m.group(1))
        if names:
            return "; ".join(n.strip() for n in names)

    row = _extract_audit_row(rule_id)
    if row and len(row) >= 6:
        fp, hits, audited = row[5], row[2], row[3]
        return (
            f"{fp} false positive(s) found in {audited} manually audited hits "
            f"(of {hits} total) — see research/precision-audit.md for the "
            f"hit-by-hit classification."
        )
    return "No documented false-positive patterns — see research/precision-audit.md."


def explain_rule(raw_rule_id: str) -> str:
    rule_id = normalize_rule_id(raw_rule_id)
    if not _VALID_RULE_ID_RE.match(rule_id):
        # Reject anything that isn't a bare "PYVIBE-###" *before* it touches
        # a filesystem path — raw_rule_id is attacker-controllable (CLI arg)
        # and would otherwise let e.g. "../../../etc/passwd" traverse out of
        # research/accepted/.
        raise EvidenceNotFoundError(f"No evidence file found for {rule_id}")

    doc_path = _accepted_path(rule_id)
    if not doc_path.exists():
        raise EvidenceNotFoundError(f"No evidence file found for {rule_id}")

    doc_text = doc_path.read_text(encoding="utf-8")

    cls = RULES_BY_ID.get(rule_id)
    if cls is not None:
        parsed = parse_rule_docstring(cls)
        title, why, fix = parsed.title, parsed.why, parsed.fix
    else:
        first_line = doc_text.splitlines()[0].lstrip("# ").strip()
        title, why, fix = first_line, "not available", "not available"

    repo_pct = _extract_repo_percentage(doc_text)
    evidence_level = _extract_evidence_level(doc_text)
    precision = _extract_precision(rule_id)
    known_fps = _extract_known_fps(doc_text, rule_id)

    lines = [
        f"  {rule_id} — {title}",
        "  " + "─" * 47,
        "",
        "  Problema:",
        f"    {title}",
        "",
        "  Por qué ocurre:",
    ]
    for para in why.split("\n\n"):
        lines.append(f"    {para}")
    lines += [
        "",
        f"  Visto en: {repo_pct}",
        f"  Nivel de evidencia: {evidence_level}",
        f"  Precisión auditada: {precision}",
        f"  Falsos positivos conocidos: {known_fps}",
        "",
        "  Fix sugerido:",
        f"    {fix}",
        "",
        f"  Full report: research/accepted/{rule_id}.md",
    ]
    return "\n".join(lines)
