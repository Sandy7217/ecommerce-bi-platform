from __future__ import annotations

import re
from typing import Any

import pandas as pd


INDIA_STATE_MAP = {
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CG": "Chhattisgarh",
    "CH": "Chandigarh",
    "DD": "Daman & Diu",
    "DL": "Delhi",
    "DN": "Dadra & Nagar Haveli",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HP": "Himachal Pradesh",
    "HR": "Haryana",
    "JH": "Jharkhand",
    "JK": "Jammu & Kashmir",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MH": "Maharashtra",
    "ML": "Meghalaya",
    "MN": "Manipur",
    "MP": "Madhya Pradesh",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "OR": "Odisha",
    "PB": "Punjab",
    "PY": "Puducherry",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TG": "Telangana",
    "TN": "Tamil Nadu",
    "TR": "Tripura",
    "TS": "Telangana",
    "UK": "Uttarakhand",
    "UP": "Uttar Pradesh",
    "UT": "Uttarakhand",
    "WB": "West Bengal",
    "AN": "Andaman & Nicobar",
}

CHANNEL_DISPLAY = {
    "MYNTRAPPMP": "Myntra",
    "MYNTRASJIT": "Myntra SJIT",
    "NYKAA_FASHION": "Nykaa",
    "AJIO_DROPSHIP": "Ajio",
    "FLIPKART": "Flipkart",
    "AMAZON_IN_API": "Amazon",
    "TATACLIQ": "TataCliq",
    "LIMEROAD": "LimeRoad",
}

MYNTRA_CHANNELS = {"MYNTRA", "MYNTRA SJIT", "MYNTRAPPMP", "MYNTRASJIT", "SJIT"}
SIZE_PATTERN = re.compile(r"[-_](xxl|xl|1xl|2xl|3xl|4xl|1x|2x|3x|4x|xs|s|m|l)$", re.IGNORECASE)
SALE_GRADE_COLUMNS = {
    "grade",
    "oldgrade",
    "salegrade",
    "salesgrade",
    "salegradeold",
    "salesgradeold",
    "oldsalegrade",
    "oldsalesgrade",
    "categoryold",
}


def _column_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    by_key = {_column_key(column): column for column in df.columns}
    for candidate in candidates:
        column = by_key.get(_column_key(candidate))
        if column is not None:
            return column
    return None


def find_sale_grade_column(df: pd.DataFrame) -> str | None:
    for column in df.columns:
        if _column_key(column) in SALE_GRADE_COLUMNS:
            return column
    for column in df.columns:
        key = _column_key(column)
        if "grade" in key and ("sale" in key or "old" in key):
            return column
    return None


def normalize_sku(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    normalized = re.sub(r"\s+", "", str(value)).lower().strip()
    return normalized or None


def extract_style_color(sku: Any) -> str | None:
    normalized = normalize_sku(sku)
    if not normalized:
        return None
    return SIZE_PATTERN.sub("", normalized)


def normalize_state(state: Any) -> str:
    if state is None or pd.isna(state):
        return "Unknown"
    raw = str(state).strip()
    if not raw:
        return "Unknown"
    upper = raw.upper()
    if upper in INDIA_STATE_MAP:
        return INDIA_STATE_MAP[upper]
    for full_name in INDIA_STATE_MAP.values():
        if upper == full_name.upper():
            return full_name
    return raw.title()


def normalize_channel(channel: Any) -> str:
    if channel is None or pd.isna(channel):
        return "Unknown"
    raw = str(channel).strip()
    return CHANNEL_DISPLAY.get(raw.upper(), raw)


def channel_code(channel: Any) -> str:
    if channel is None or pd.isna(channel):
        return "UNKNOWN"
    return str(channel).strip().upper()


def is_myntra_channel(channel: Any) -> bool:
    return channel_code(channel) in MYNTRA_CHANNELS


def normalize_date(value: Any, fmt: str | None = None, dayfirst: bool = True) -> str | None:
    try:
        if fmt:
            parsed = pd.to_datetime(value, format=fmt, errors="coerce")
        else:
            parsed = pd.to_datetime(value, dayfirst=dayfirst, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return None


def parse_visibility_period(value: Any) -> tuple[str | None, str | None]:
    if value is None or pd.isna(value):
        return None, None
    parts = [part.strip() for part in str(value).split(" - ", 1)]
    if len(parts) != 2:
        return normalize_date(value, dayfirst=False), None
    return normalize_date(parts[0], dayfirst=False), normalize_date(parts[1], dayfirst=False)


def build_sku_master_map(listing_df: pd.DataFrame, channel_item_df: pd.DataFrame) -> pd.DataFrame:
    listing = listing_df[["style id", "seller sku code", "sku id", "sku code"]].copy()
    listing.columns = ["style_id", "myntra_seller_sku", "sku_id", "myntra_sku_code"]
    listing["myntra_seller_sku_norm"] = listing["myntra_seller_sku"].apply(normalize_sku)

    channel = channel_item_df[channel_item_df["Uniware Sku Code"].notna()][
        ["Seller Sku Code", "Uniware Sku Code"]
    ].copy()
    channel.columns = ["seller_sku_code", "uniware_sku"]
    channel["seller_sku_norm"] = channel["seller_sku_code"].apply(normalize_sku)
    channel = channel.drop_duplicates("seller_sku_norm")

    result = listing.merge(
        channel[["seller_sku_norm", "uniware_sku"]],
        left_on="myntra_seller_sku_norm",
        right_on="seller_sku_norm",
        how="left",
    )
    result["internal_sku"] = result["uniware_sku"].apply(normalize_sku)
    result["style_color"] = result["internal_sku"].apply(extract_style_color)
    return result[
        [
            "style_id",
            "myntra_seller_sku",
            "myntra_sku_code",
            "sku_id",
            "uniware_sku",
            "internal_sku",
            "style_color",
        ]
    ].drop_duplicates(["style_id", "myntra_seller_sku"])


def build_sale_grade_updates(df: pd.DataFrame, sku_candidates: list[str]) -> pd.DataFrame:
    grade_col = find_sale_grade_column(df)
    sku_col = find_column(df, sku_candidates)
    if not grade_col or not sku_col:
        return pd.DataFrame(columns=["style_color", "sale_grade_old"])

    updates = df[[sku_col, grade_col]].copy()
    updates.columns = ["sku", "sale_grade_old"]
    updates["style_color"] = updates["sku"].apply(normalize_sku).apply(extract_style_color)
    updates["sale_grade_old"] = updates["sale_grade_old"].fillna("").astype(str).str.strip()
    updates = updates[(updates["style_color"].notna()) & (updates["sale_grade_old"] != "")]
    if updates.empty:
        return pd.DataFrame(columns=["style_color", "sale_grade_old"])
    return updates[["style_color", "sale_grade_old"]].drop_duplicates("style_color")


def build_sku_mapping_sale_grade_updates(
    listing_df: pd.DataFrame,
    channel_item_df: pd.DataFrame,
    sku_map_df: pd.DataFrame,
) -> pd.DataFrame:
    channel_updates = build_sale_grade_updates(channel_item_df, ["Uniware Sku Code", "uniware_sku", "Item SKU Code"])
    if not channel_updates.empty:
        return channel_updates

    grade_col = find_sale_grade_column(listing_df)
    seller_sku_col = find_column(listing_df, ["seller sku code", "seller_sku_code"])
    if not grade_col or not seller_sku_col:
        return pd.DataFrame(columns=["style_color", "sale_grade_old"])

    updates = listing_df[[seller_sku_col, grade_col]].copy()
    updates.columns = ["myntra_seller_sku", "sale_grade_old"]
    updates = updates.merge(
        sku_map_df[["myntra_seller_sku", "style_color"]].drop_duplicates("myntra_seller_sku"),
        on="myntra_seller_sku",
        how="left",
    )
    updates["sale_grade_old"] = updates["sale_grade_old"].fillna("").astype(str).str.strip()
    updates = updates[(updates["style_color"].notna()) & (updates["sale_grade_old"] != "")]
    if updates.empty:
        return pd.DataFrame(columns=["style_color", "sale_grade_old"])
    return updates[["style_color", "sale_grade_old"]].drop_duplicates("style_color")


def map_style_id_to_sku(df: pd.DataFrame, sku_map: pd.DataFrame, style_id_column: str) -> pd.DataFrame:
    mapped = df.copy()
    map_cols = ["style_id", "internal_sku", "style_color"]
    mapped = mapped.merge(sku_map[map_cols].drop_duplicates("style_id"), left_on=style_id_column, right_on="style_id", how="left")
    return mapped
