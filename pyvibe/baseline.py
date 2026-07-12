"""Baseline support — `pyvibe baseline create/update` and `pyvibe scan --baseline`.

A baseline is a snapshot of existing findings ({filepath: [{rule_id, line,
message}, ...]}) that a team can choose to commit or gitignore (see README).
Once created, `pyvibe scan --baseline` only reports genuinely NEW
violations — anything already in the baseline is suppressed — so a
codebase can adopt python-vibe-guard incrementally instead of having to
fix every existing hit before CI goes green.
"""
import json
from pathlib import Path
from typing import Dict, Set, Tuple

DEFAULT_BASELINE_PATH = ".pyvibe-baseline.json"


class BaselineNotFoundError(Exception):
    """Raised when `pyvibe scan --baseline` can't find/parse the baseline file."""


def build_baseline(file_results: Dict) -> dict:
    """file_results: {path: [Violation, ...]} as produced by analyze_file /
    analyze_directory. Returns the JSON-serializable baseline:
    {filepath: [{rule_id, line, message}, ...]}.
    """
    return {
        str(path): [
            {"rule_id": v.rule_id, "line": v.line, "message": v.message}
            for v in violations
        ]
        for path, violations in file_results.items()
    }


def write_baseline(file_results: Dict, output_path=DEFAULT_BASELINE_PATH) -> None:
    baseline = build_baseline(file_results)
    Path(output_path).write_text(json.dumps(baseline, indent=2), encoding="utf-8")


def load_baseline(path=DEFAULT_BASELINE_PATH) -> dict:
    baseline_path = Path(path)
    if not baseline_path.exists():
        raise BaselineNotFoundError(
            f"No baseline found at {path}. Run `pyvibe baseline create` first."
        )
    try:
        return json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BaselineNotFoundError(f"Baseline at {path} is not valid JSON: {e}") from e


def _baseline_keys(baseline: dict) -> Set[Tuple[str, str, int]]:
    """Flatten the baseline into (filepath, rule_id, line) triples for exact,
    O(1) membership checks.
    """
    return {
        (filepath, entry["rule_id"], entry["line"])
        for filepath, entries in baseline.items()
        for entry in entries
    }


def filter_new_violations(file_results: Dict, baseline: dict) -> Dict:
    """Return only the violations in file_results NOT present in baseline,
    matched exactly on (filepath, rule_id, line).
    """
    known = _baseline_keys(baseline)
    new_results = {}
    for path, violations in file_results.items():
        new = [v for v in violations if (str(path), v.rule_id, v.line) not in known]
        if new:
            new_results[path] = new
    return new_results
