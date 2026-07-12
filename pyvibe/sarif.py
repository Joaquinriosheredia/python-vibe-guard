"""SARIF 2.1.0 output for GitHub Code Scanning (`pyvibe <path> --sarif`)."""
import json
from pathlib import Path
from typing import Dict, List

from pyvibe import __version__
from pyvibe.analyzer import ALL_RULES
from pyvibe.rule_docs import parse_rule_docstring
from pyvibe.rules.base import Violation

SARIF_SCHEMA_URI = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/Schemata/"
    "sarif-schema-2.1.0.json"
)
REPO_URL = "https://github.com/Joaquinriosheredia/python-vibe-guard"

_SEVERITY_TO_LEVEL = {"CRITICAL": "error", "WARNING": "warning"}


def _level_for(severity: str) -> str:
    return _SEVERITY_TO_LEVEL.get(severity, "warning")


def _rule_descriptor(cls) -> dict:
    doc = parse_rule_docstring(cls)
    return {
        "id": cls.RULE_ID,
        "name": cls.__name__,
        "shortDescription": {"text": doc.title},
        "fullDescription": {"text": doc.why or doc.title},
        "help": {"text": doc.fix},
        "helpUri": f"{REPO_URL}/blob/master/research/accepted/{cls.RULE_ID}.md",
        "defaultConfiguration": {"level": _level_for(cls.SEVERITY)},
    }


def _artifact_uri(path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            p = p.relative_to(Path.cwd())
        except ValueError:
            pass
    return p.as_posix()


def _result(path, v: Violation) -> dict:
    return {
        "ruleId": v.rule_id,
        "level": _level_for(v.severity),
        "message": {"text": f"{v.message} — Fix: {v.evidence}"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": _artifact_uri(path)},
                    "region": {"startLine": v.line},
                }
            }
        ],
        "properties": {"function": v.function_name},
    }


def build_sarif(file_results: Dict) -> dict:
    """file_results: {path: [Violation, ...]} as produced by analyze_file /
    analyze_directory. Every rule is listed in the tool's rule catalog
    regardless of whether it fired, per SARIF/Code Scanning convention.
    """
    rules = [_rule_descriptor(cls) for cls in ALL_RULES]
    results: List[dict] = [
        _result(path, v) for path, violations in file_results.items() for v in violations
    ]

    return {
        "$schema": SARIF_SCHEMA_URI,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "python-vibe-guard",
                        "informationUri": REPO_URL,
                        "version": __version__,
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }


def write_sarif(file_results: Dict, output_path) -> None:
    sarif = build_sarif(file_results)
    Path(output_path).write_text(json.dumps(sarif, indent=2), encoding="utf-8")
