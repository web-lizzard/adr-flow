"""Aggregates remain data containers without lifecycle behavior in F-02."""

import ast
import inspect
from pathlib import Path

from domain.adr.aggregate import ADR
from domain.user.aggregate import User

DOMAIN_AGGREGATE_FILES = (
    Path(__file__).resolve().parents[2] / "domain" / "user" / "aggregate.py",
    Path(__file__).resolve().parents[2] / "domain" / "adr" / "aggregate.py",
)

LIFECYCLE_METHOD_HINTS = frozenset(
    {
        "submit",
        "publish",
        "delete",
        "register",
        "review",
        "transition",
        "validate",
        "apply",
    }
)


def _public_methods_from_dataclass(cls: type[object]) -> set[str]:
    return {
        name
        for name, member in inspect.getmembers(cls)
        if callable(member)
        and not name.startswith("_")
        and name not in {"__init__", "__replace__", "__repr__", "__eq__"}
    }


def test_aggregate_dataclasses_expose_no_lifecycle_methods() -> None:
    for cls in (User, ADR):
        methods = _public_methods_from_dataclass(cls)
        lifecycle = {
            name
            for name in methods
            if any(hint in name for hint in LIFECYCLE_METHOD_HINTS)
        }
        assert lifecycle == set(), (
            f"{cls.__name__} exposes lifecycle-like methods: {lifecycle}"
        )


def test_aggregate_modules_define_no_behavior_functions() -> None:
    for path in DOMAIN_AGGREGATE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        function_defs = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        assert function_defs == []
