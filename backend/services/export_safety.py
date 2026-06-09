from __future__ import annotations

from typing import Any, Iterable


FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def safe_cell(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith("'"):
        return value
    if value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


def safe_row(row: Iterable[Any]) -> list[Any]:
    return [safe_cell(value) for value in row]


def safe_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {key: safe_cell(value) for key, value in row.items()}
