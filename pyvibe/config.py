"""pyvibe.toml project configuration.

Discovered by walking up from the scan target to the nearest ancestor
directory containing a pyvibe.toml — same convention as pyproject.toml,
.flake8, etc. Loading is always explicit (callers pass the resulting
PyvibeConfig into analyzer functions); nothing here runs automatically as
a side effect of importing this module.

    [tool.pyvibe]
    ignore = ["PYVIBE-019"]
    exclude = ["tests/**", "examples/**", "docs/**"]

    [tool.pyvibe.severity]
    PYVIBE-008 = "warning"
"""
import fnmatch
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, Optional, Tuple

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

DEFAULT_CONFIG_FILENAME = "pyvibe.toml"
_VALID_SEVERITIES = frozenset({"critical", "warning"})


class ConfigError(Exception):
    """Raised when pyvibe.toml exists but can't be parsed or is malformed."""


@dataclass(frozen=True)
class PyvibeConfig:
    root: Path  # directory containing pyvibe.toml — exclude patterns are relative to this
    ignore: FrozenSet[str] = frozenset()
    exclude: Tuple[str, ...] = ()
    severity: Dict[str, str] = field(default_factory=dict)  # rule_id -> "CRITICAL"/"WARNING"


def find_config_file(start: Path) -> Optional[Path]:
    """Walk `start` (file or directory) and its parents looking for pyvibe.toml."""
    start = start.resolve()
    current = start if start.is_dir() else start.parent
    for directory in (current, *current.parents):
        candidate = directory / DEFAULT_CONFIG_FILENAME
        if candidate.exists():
            return candidate
    return None


def _validate_severity(severity: Dict[str, str], config_path: Path) -> None:
    for rule_id, value in severity.items():
        if value.lower() not in _VALID_SEVERITIES:
            raise ConfigError(
                f"{config_path}: invalid severity {value!r} for {rule_id} "
                f"(expected one of {sorted(_VALID_SEVERITIES)})"
            )


def load_config(start: Path) -> Optional[PyvibeConfig]:
    """Find and parse pyvibe.toml starting from `start` (file or directory).

    Returns None if no pyvibe.toml exists anywhere up the tree — callers
    should treat that as "no project config, use built-in defaults only".
    """
    config_path = find_config_file(start)
    if config_path is None:
        return None

    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Failed to parse {config_path}: {e}") from e

    tool_section = data.get("tool", {}).get("pyvibe", {})
    ignore = frozenset(tool_section.get("ignore", []))
    exclude = tuple(tool_section.get("exclude", []))
    raw_severity = dict(tool_section.get("severity", {}))

    _validate_severity(raw_severity, config_path)
    severity = {rule_id: value.upper() for rule_id, value in raw_severity.items()}

    return PyvibeConfig(root=config_path.parent, ignore=ignore, exclude=exclude, severity=severity)


def is_excluded(path: Path, config: PyvibeConfig) -> bool:
    """True if `path` matches any of config.exclude glob patterns, relative
    to the directory containing pyvibe.toml.
    """
    if not config.exclude:
        return False
    try:
        rel = path.resolve().relative_to(config.root).as_posix()
    except ValueError:
        return False
    return any(fnmatch.fnmatch(rel, pattern) for pattern in config.exclude)
