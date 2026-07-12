"""Shared helpers for building concrete "Suggested fix" snippets from real source context.

Rules that support autofix suggestions receive the original source text and use
`ast.get_source_segment` to pull the exact expressions the developer wrote
(variable names, literals, kwargs) into the suggested replacement, instead of
a synthetic placeholder like `...`.
"""
import ast
from typing import Optional


def render_node(source: str, node: ast.AST) -> Optional[str]:
    """Return the literal source text of an AST node, or None if unavailable."""
    return ast.get_source_segment(source, node)


def render_call_args(source: str, node: ast.Call) -> str:
    """Reconstruct the literal argument-list text of a Call node from source."""
    parts = []
    for arg in node.args:
        if isinstance(arg, ast.Starred):
            seg = render_node(source, arg.value)
            parts.append(f"*{seg}" if seg else "*args")
        else:
            seg = render_node(source, arg)
            parts.append(seg if seg is not None else "...")
    for kw in node.keywords:
        seg = render_node(source, kw.value)
        seg = seg if seg is not None else "..."
        parts.append(f"**{seg}" if kw.arg is None else f"{kw.arg}={seg}")
    return ", ".join(parts)
