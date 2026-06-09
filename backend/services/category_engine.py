from __future__ import annotations

from collections.abc import Mapping
from typing import Any


ALLOWED_CATEGORY_VALUES = (
    "Discontinue",
    "OOS",
    "Winter",
    "Dog styles",
    "NOOS",
    "NOOS(Green)",
    "NOOS(Yellow)",
    "NOOS(Red)",
    "NOOS(OOS)",
    "NOOS(Potential)",
    "Green",
    "Yellow",
    "Red",
    "Dead",
    "Unknown",
    "Watchlist",
    "RED(Repeat)",
    "New Launch",
    "Potential NOOS",
    "Winter NOOS",
    "AW Styles",
    "Core Winter",
)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(value != value)
    except Exception:
        return False


def _to_float(value: Any) -> float:
    if _is_missing(value):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if _is_missing(value):
        return False
    if isinstance(value, str):
        return value.strip().upper() in {"1", "TRUE", "YES", "Y"}
    return bool(value)


def _row_get(row: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(row, Mapping) and key in row:
            return row[key]
        if hasattr(row, "get"):
            try:
                value = row.get(key, None)
            except TypeError:
                value = None
            if value is not None:
                return value
    return default


def normalize_grade(value: Any) -> str:
    if _is_missing(value):
        return ""
    normalized = str(value).strip().upper()
    if not normalized:
        return ""
    return normalized


def is_discontinued_grade(value: Any) -> bool:
    grade = normalize_grade(value)
    return "DISCONTINUE" in grade or "DISCONTINUED" in grade


def is_old_noos_grade(value: Any) -> bool:
    grade = normalize_grade(value)
    return "NOOS" in grade or "HOT SELLER" in grade or grade == "WINTER NOOS"


def is_approved_noos_grade(value: Any) -> bool:
    grade = normalize_grade(value)
    return grade == "NOOS" or grade.startswith("NOOS(") or grade == "WINTER NOOS" or "HOT SELLER" in grade


def is_winter_grade(value: Any) -> bool:
    grade = normalize_grade(value)
    return "CORE WINTER" in grade or "WINTER" in grade or "AW STYLES" in grade


def normalize_new_category(value: Any) -> str:
    category = normalize_grade(value)
    if category == "NOOS":
        return "NOOS"
    if category == "GREEN":
        return "Green"
    if category == "YELLOW":
        return "Yellow"
    if category == "RED":
        return "Red"
    if category == "DEAD":
        return "Red"
    return "Unknown"


def get_style_from_sku(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value).split("-")[0]


def assign_category(ros: Any) -> str:
    ros_value = _to_float(ros)
    if ros_value > 4:
        return "NOOS"
    if 1.5 <= ros_value <= 4:
        return "Green"
    if 0.75 <= ros_value < 1.5:
        return "Yellow"
    if 0.5 <= ros_value < 0.75:
        return "Red"
    return "Dead"


def _old_noos_category(new_category: str) -> str:
    if new_category == "NOOS":
        return "NOOS"
    if new_category == "Green":
        return "NOOS(Green)"
    if new_category == "Yellow":
        return "NOOS(Yellow)"
    if new_category == "Red":
        return "NOOS(Red)"
    return "Unknown"


def _resolve_style_key_column(df: Any) -> str:
    for column in ("style_color", "internal_sku", "SKU", "sku", "Sku", "style", "Style"):
        if column in df.columns:
            return column
    raise KeyError("Expected a style/SKU key column such as style_color, internal_sku, or SKU")


def add_dog_style_flag(df: Any) -> Any:
    result = df.copy()
    if result.empty:
        result["_is_dog_style"] = False
        return result

    style_key_column = _resolve_style_key_column(result)
    result["_dog_style"] = result[style_key_column].apply(get_style_from_sku)
    result["_dog_ros_value"] = result["ros"].apply(_to_float) if "ros" in result.columns else 0.0
    if "total_inventory" in result.columns:
        result["_dog_inventory_value"] = result["total_inventory"].apply(_to_float)
    else:
        result["_dog_inventory_value"] = 0.0

    status = result["inventory_status"].apply(normalize_grade) if "inventory_status" in result.columns else ""
    eligible_status = status.isin(["BROKEN", "INSTOCK"]) if hasattr(status, "isin") else False
    eligible = result[eligible_status]

    if eligible.empty:
        result["_is_dog_style"] = False
    else:
        style_totals = eligible.groupby("_dog_style", dropna=False).agg(
            _dog_ros_value=("_dog_ros_value", "sum"),
            _dog_inventory_value=("_dog_inventory_value", "sum"),
        )
        dog_styles = set(
            style_totals[
                (style_totals["_dog_ros_value"] == 0)
                & (style_totals["_dog_inventory_value"] > 175)
            ].index
        )
        result["_is_dog_style"] = result["_dog_style"].isin(dog_styles) & eligible_status

    return result.drop(columns=["_dog_style", "_dog_ros_value", "_dog_inventory_value"])


def finalize_category_new(row: Any) -> str:
    sale_grade_old = _row_get(row, "sale_grade_old", "category_old", default="")
    inventory_status = normalize_grade(_row_get(row, "inventory_status", default=""))
    ros = _to_float(_row_get(row, "ros", default=0))
    raw_new_category = _row_get(row, "new_category", "category_new", default=assign_category(ros))
    new_category = normalize_new_category(raw_new_category)

    if is_discontinued_grade(sale_grade_old):
        return "Discontinue"
    normalized_sale_grade = normalize_grade(sale_grade_old)
    if normalized_sale_grade in {"NOOS", "WINTER NOOS"} and ros > 1.5:
        return "NOOS"
    if normalized_sale_grade == "WINTER NOOS":
        return _old_noos_category(new_category)
    if normalized_sale_grade == "WATCHLIST":
        return "Watchlist"
    if normalized_sale_grade == "RED(REPEAT)":
        return "RED(Repeat)"
    if normalized_sale_grade == "NEW LAUNCH":
        return "New Launch"
    if normalized_sale_grade == "POTENTIAL NOOS":
        return "Potential NOOS"
    if inventory_status == "OOS":
        return "OOS"
    if is_winter_grade(sale_grade_old) and ros < 0.5:
        return "Winter"
    if _to_bool(_row_get(row, "_is_dog_style", default=False)) and inventory_status in {
        "BROKEN",
        "INSTOCK",
    }:
        return "Dog styles"
    if is_old_noos_grade(sale_grade_old):
        return _old_noos_category(new_category)
    if new_category == "NOOS":
        return "NOOS(Potential)"
    return new_category


def compute_cross_category(category_old: Any, category_new: Any, inventory_status: Any = "") -> str:
    row = {
        "sale_grade_old": category_old,
        "new_category": category_new,
        "inventory_status": inventory_status,
    }
    return finalize_category_new(row)


def flag_potential_noos(
    style_color: str,
    ros_7d: float,
    ros_30d: float,
    category_old: str,
) -> bool:
    del style_color
    del ros_7d
    return not is_approved_noos_grade(category_old) and ros_30d > 4


def compute_doi(total_inventory: Any, ros_30d: Any) -> float:
    ros_value = _to_float(ros_30d)
    if ros_value <= 0:
        return 9999.0
    return _to_float(total_inventory) / ros_value


def get_replenishment_priority(doi: Any, inventory_status: Any) -> str:
    doi_value = _to_float(doi)
    status = normalize_grade(inventory_status)
    if status == "OOS" or doi_value == 0:
        return "P0 - Critical OOS"
    if doi_value < 15:
        return "P1 - Urgent Replenishment"
    if doi_value < 45:
        return "P2 - High Risk"
    if doi_value < 90:
        return "Monitor"
    return "Do Not Replenish"
