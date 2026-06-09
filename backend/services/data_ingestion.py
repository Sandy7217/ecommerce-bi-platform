from __future__ import annotations

from datetime import date
from io import BytesIO
import re
from typing import Any

import pandas as pd

from backend.services.sku_mapper import (
    channel_code,
    extract_style_color,
    find_column,
    is_myntra_channel,
    normalize_channel,
    normalize_date,
    normalize_sku,
    normalize_state,
    parse_visibility_period,
)


MYNTRA_EXCLUDE = {"F", "RTO"}
SALES_MASTER_RETURN_TRACKING = {"DELIVERED", "RTO_DELIVERED_TO_SELLER", "RTO_INITIATED", "RTO_IN_TRANSIT"}
SALES_MASTER_SALE_STATUSES = {"DELIVERED", "DISPATCHED", "PICKING_FOR_INVOICING", "FULFILLABLE"}
INSTOCK_SIZES = ["s", "m", "l", "xl"]
MYNTRA_PO_TYPE_CHANNELS = {
    "PPMP": "MYNTRAPPMP",
    "SJIT": "MYNTRASJIT",
    "MYNTRAPPMP": "MYNTRAPPMP",
    "MYNTRASJIT": "MYNTRASJIT",
    "MYNTRA SJIT": "MYNTRASJIT",
}
MYNTRA_FILE_DATE_RE = re.compile(r"_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})(?:\.[^.]+)?$")


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str)


def _aggregate_sales_rows(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty or not {"order_id", "internal_sku", "qty", "selling_price"}.issubset(rows.columns):
        return rows
    columns = list(rows.columns)
    key_mask = rows["order_id"].notna() & rows["internal_sku"].notna() & (_text(rows["order_id"]).str.strip() != "") & (_text(rows["internal_sku"]).str.strip() != "")
    keyed = rows[key_mask].copy()
    unkeyed = rows[~key_mask].copy()
    if keyed.empty:
        return rows

    keyed["_qty"] = _num(keyed["qty"])
    keyed["_sale_value"] = _num(keyed["selling_price"]) * keyed["_qty"]
    keyed["_mrp_value"] = _num(keyed.get("mrp", pd.Series(index=keyed.index))) * keyed["_qty"]
    keyed["_discount_value"] = _num(keyed.get("discount", pd.Series(index=keyed.index))) * keyed["_qty"]

    keys = ["order_id", "internal_sku"]
    aggregations: dict[str, str] = {column: "first" for column in keyed.columns if column not in {*keys, "qty", "selling_price", "mrp", "discount", "_qty", "_sale_value", "_mrp_value", "_discount_value"}}
    aggregations.update({"qty": "sum", "_sale_value": "sum", "_mrp_value": "sum", "_discount_value": "sum"})
    grouped = keyed.groupby(keys, as_index=False, dropna=False).agg(aggregations)
    grouped["selling_price"] = grouped["_sale_value"] / grouped["qty"].replace(0, pd.NA)
    if "mrp" in columns:
        grouped["mrp"] = grouped["_mrp_value"] / grouped["qty"].replace(0, pd.NA)
    if "discount" in columns:
        grouped["discount"] = grouped["_discount_value"] / grouped["qty"].replace(0, pd.NA)
    grouped = grouped.drop(columns=["_sale_value", "_mrp_value", "_discount_value"], errors="ignore")
    return pd.concat([unkeyed[columns], grouped[columns]], ignore_index=True)


def _myntra_po_type_channel(value: Any) -> str:
    raw = "" if value is None or pd.isna(value) else str(value).strip().upper()
    return MYNTRA_PO_TYPE_CHANNELS.get(raw, "MYNTRAPPMP")


def _myntra_default_channel(file_name: str | None) -> str:
    upper = str(file_name or "").upper()
    if "SJIT" in upper and "ORDERS_REPORT" in upper:
        return "MYNTRASJIT"
    return "MYNTRAPPMP"


def _single_day_from_myntra_file(file_name: str | None) -> str | None:
    match = MYNTRA_FILE_DATE_RE.search(str(file_name or ""))
    if not match:
        return None
    start_date, end_date = match.groups()
    return start_date if start_date == end_date else None


def _myntra_order_dates(values: pd.Series, file_name: str | None) -> pd.Series:
    text = _text(values).str.strip()
    has_date = text.str.contains(r"\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", regex=True)
    parsed = pd.to_datetime(text.where(has_date), errors="coerce", dayfirst=False)
    dates = parsed.dt.strftime("%Y-%m-%d")
    fallback_date = _single_day_from_myntra_file(file_name)
    return dates.fillna(fallback_date) if fallback_date else dates


def _unicommerce_order_dates(data: pd.DataFrame) -> pd.Series:
    order_text = _text(data["Order Date as dd/mm/yyyy hh:MM:ss"]).str.strip()
    iso_order_date = order_text.str.match(r"\d{4}-\d{2}-\d{2}")
    order_dates = pd.to_datetime(order_text.where(iso_order_date), errors="coerce", dayfirst=False).fillna(
        pd.to_datetime(order_text.where(~iso_order_date), errors="coerce", dayfirst=True)
    )
    if "Created" not in data.columns:
        return order_dates.dt.strftime("%Y-%m-%d")
    created_dates = pd.to_datetime(data["Created"], errors="coerce", dayfirst=False)
    return created_dates.fillna(order_dates).dt.strftime("%Y-%m-%d")


def read_upload_dataframe(file_name: str, content: bytes) -> pd.DataFrame:
    suffix = file_name.lower().rsplit(".", 1)[-1]
    if suffix in {"xlsx", "xls"}:
        return pd.read_excel(BytesIO(content))
    return pd.read_csv(BytesIO(content))


def process_myntra_orders(df: pd.DataFrame, sku_map: pd.DataFrame, file_name: str | None = None) -> pd.DataFrame:
    data = df[~df["order status"].isin(MYNTRA_EXCLUDE)].copy()
    po_type_column = find_column(data, ["po_type", "po type", "PO Type"])
    po_type = data[po_type_column] if po_type_column else pd.Series(_myntra_default_channel(file_name), index=data.index)
    data["myntra_channel"] = po_type.apply(_myntra_po_type_channel)
    data = data.merge(
        sku_map[["style_id", "myntra_seller_sku", "internal_sku", "style_color"]],
        left_on=["style id", "seller sku code"],
        right_on=["style_id", "myntra_seller_sku"],
        how="left",
    )
    rows = pd.DataFrame(
        {
            "date": _myntra_order_dates(data["created on"], file_name),
            "internal_sku": data["internal_sku"],
            "style_color": data["style_color"],
            "channel": data["myntra_channel"],
            "marketplace": data["myntra_channel"].apply(normalize_channel),
            "selling_price": _num(data["final amount"]),
            "mrp": _num(data["total mrp"]),
            "discount": _num(data["discount"]),
            "qty": 1,
            "order_id": _text(data["store order id"]),
            "order_status": data["order status"],
            "state": data["state"].apply(normalize_state),
            "city": data["city"],
            "size": data["size"],
            "style_id": data["style id"],
            "source": "myntra_orders",
        }
    ).dropna(subset=["date"])
    return _aggregate_sales_rows(rows)


def split_unicommerce_cancelled_returns(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df.copy()
    if "Reverse Pickup Code" in data.columns:
        has_return_code = data["Reverse Pickup Code"].notna() & (_text(data["Reverse Pickup Code"]).str.strip() != "")
        cancelled = data["Sale Order Item Status"].eq("CANCELLED")
        return data[~(cancelled & ~has_return_code)].copy(), data[cancelled & has_return_code].copy()

    tracking = _text(data.get("Shipping Tracking Status", pd.Series(index=data.index))).str.upper()
    cancelled = data["Sale Order Item Status"].eq("CANCELLED")
    returns = data[cancelled & tracking.isin(SALES_MASTER_RETURN_TRACKING)].copy()
    sales = data[
        (~cancelled & data["Sale Order Item Status"].isin(SALES_MASTER_SALE_STATUSES))
        | (cancelled & tracking.isin(SALES_MASTER_RETURN_TRACKING))
    ].copy()
    sales = sales[~(cancelled & tracking.isin(SALES_MASTER_RETURN_TRACKING))].copy()
    return sales, returns


def process_unicommerce_sales(df: pd.DataFrame, source: str = "unicommerce", include_myntra: bool = False) -> pd.DataFrame:
    data = df.copy() if include_myntra else df[~df["Channel Name"].apply(is_myntra_channel)].copy()
    sales, _returns = split_unicommerce_cancelled_returns(data)
    sales["internal_sku"] = sales["Item SKU Code"].apply(normalize_sku)
    sales["style_color"] = sales["internal_sku"].apply(extract_style_color)
    rows = pd.DataFrame(
        {
            "date": _unicommerce_order_dates(sales),
            "internal_sku": sales["internal_sku"],
            "style_color": sales["style_color"],
            "channel": sales["Channel Name"].apply(channel_code),
            "marketplace": sales["Channel Name"].apply(normalize_channel),
            "selling_price": _num(sales["Selling Price"]),
            "mrp": _num(sales["MRP"]),
            "discount": _num(sales["Discount"]),
            "qty": 1,
            "order_id": _text(sales["Sale Order Code"]),
            "order_status": sales["Sale Order Item Status"],
            "state": sales["Shipping Address State"].apply(normalize_state),
            "city": sales["Shipping Address City"],
            "size": sales["Item Type Size"],
            "style_id": None,
            "source": source,
        }
    ).dropna(subset=["date"])
    return _aggregate_sales_rows(rows)


def process_sales_master(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df.copy()
    sales = process_unicommerce_sales(data, source="sales_master", include_myntra=True)
    _sales_rows, return_rows = split_unicommerce_cancelled_returns(data)
    returns = process_unicommerce_cancelled_returns(return_rows, source="sales_master")
    return sales, returns


def process_unicommerce_cancelled_returns(df: pd.DataFrame, source: str = "unicommerce") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "internal_sku", "style_color", "channel", "qty", "return_value", "return_type", "order_id", "invoice_no", "state", "city", "source"])
    data = df.copy()
    data["internal_sku"] = data["Item SKU Code"].apply(normalize_sku)
    data["style_color"] = data["internal_sku"].apply(extract_style_color)
    return pd.DataFrame(
        {
            "date": pd.to_datetime(data["Order Date as dd/mm/yyyy hh:MM:ss"], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d"),
            "internal_sku": data["internal_sku"],
            "style_color": data["style_color"],
            "channel": data["Channel Name"].apply(normalize_channel),
            "qty": 1,
            "return_value": _num(data.get("Selling Price", pd.Series(index=data.index))),
            "return_type": "Customer Return",
            "order_id": _text(data["Sale Order Code"]),
            "invoice_no": data.get("Invoice Number"),
            "state": data["Shipping Address State"].apply(normalize_state),
            "city": data["Shipping Address City"],
            "source": source,
        }
    ).dropna(subset=["date"])


def process_returns(df: pd.DataFrame, source: str = "returns") -> pd.DataFrame:
    data = df.copy()
    if "Voucher Type" in data.columns:
        data = data[_text(data["Voucher Type"]).str.upper().eq("CREDIT NOTE")].copy()
    data["internal_sku"] = data["Product SKU Code"].apply(normalize_sku)
    data["style_color"] = data["internal_sku"].apply(extract_style_color)
    returns = pd.DataFrame(
        {
            "date": pd.to_datetime(data["Date"], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d"),
            "internal_sku": data["internal_sku"],
            "style_color": data["style_color"],
            "channel": data["Channel entry"],
            "qty": _num(data["Qty"]),
            "return_value": _num(data["Unit Price"]),
            "return_type": data.get("Return Type", "Customer Return"),
            "order_id": _text(data["Sale Order Number"]),
            "invoice_no": data["Invoice number"],
            "state": data["Shipping Address State"].apply(normalize_state),
            "city": data["Shipping Address City"],
            "source": source,
        }
    ).dropna(subset=["date"])
    columns = list(returns.columns)
    grouped = returns.groupby(["order_id", "internal_sku", "date"], as_index=False, dropna=False).agg(
        {
            "style_color": "first",
            "channel": "first",
            "qty": "sum",
            "return_value": "sum",
            "return_type": "first",
            "invoice_no": "first",
            "state": "first",
            "city": "first",
            "source": "first",
        }
    )
    return grouped[columns]


def process_inventory_snapshot(df: pd.DataFrame, snapshot_date: date | str) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df.copy()
    data.columns = data.columns.str.strip().str.lower().str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_")
    sku_col = "item_skucode" if "item_skucode" in data.columns else "item_sku_code" if "item_sku_code" in data.columns else None
    if sku_col and {"size", "inventory"}.issubset(data.columns):
        data["internal_sku"] = data[sku_col].apply(normalize_sku)
        data["style_color"] = data["internal_sku"].apply(extract_style_color)
        data["size"] = _text(data["size"]).str.upper().str.strip()
        data["inventory_qty"] = _num(data["inventory"]).astype(int)
        history = (
            data.groupby(["style_color", "size"], as_index=False)["inventory_qty"]
            .sum()
            .dropna(subset=["style_color"])
            .rename(columns={"inventory_qty": "qty"})
        )
        history["snapshot_date"] = str(snapshot_date)

        size_matrix = history.pivot_table(index="style_color", columns="size", values="qty", aggfunc="sum", fill_value=0)
        status_sizes = [size.upper() for size in INSTOCK_SIZES]
        totals = history.groupby("style_color", as_index=False)["qty"].sum().rename(columns={"qty": "total_inventory"})

        def get_group_status(style_color: str) -> str:
            row = size_matrix.loc[style_color] if style_color in size_matrix.index else {}
            vals = [float(row.get(size, 0) or 0) for size in status_sizes]
            if not vals or all(value < 5 for value in vals):
                return "OOS"
            if any(value < 5 for value in vals):
                return "BROKEN"
            return "INSTOCK"

        master = totals.copy()
        master["inventory_status"] = master["style_color"].apply(get_group_status)
        master["snapshot_date"] = str(snapshot_date)
        return master[["style_color", "total_inventory", "inventory_status", "snapshot_date"]], history[["snapshot_date", "style_color", "size", "qty"]]

    row_col = "row_labels" if "row_labels" in data.columns else data.columns[0]
    data["style_color"] = data[row_col].apply(normalize_sku).apply(extract_style_color)
    numeric_cols = [col for col in data.columns if col not in {row_col, "grand_total", "style_color"}]
    size_cols = [col for col in numeric_cols if col.lower() not in {"total", "blank"}]
    data[size_cols] = data[size_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    if "grand_total" in data.columns:
        data["total_inventory"] = _num(data["grand_total"])
    else:
        data["total_inventory"] = data[size_cols].sum(axis=1)
    status_sizes = [size for size in INSTOCK_SIZES if size in data.columns]

    def get_status(row: pd.Series) -> str:
        vals = [float(row.get(size, 0) or 0) for size in status_sizes]
        if not vals or all(value < 5 for value in vals):
            return "OOS"
        if any(value < 5 for value in vals):
            return "BROKEN"
        return "INSTOCK"

    data["inventory_status"] = data.apply(get_status, axis=1)
    data["snapshot_date"] = str(snapshot_date)

    history_rows: list[dict[str, Any]] = []
    for _, row in data.iterrows():
        for size in size_cols:
            history_rows.append(
                {
                    "snapshot_date": row["snapshot_date"],
                    "style_color": row["style_color"],
                    "size": size.upper(),
                    "qty": int(row.get(size, 0) or 0),
                }
            )
    master = data[["style_color", "total_inventory", "inventory_status", "snapshot_date"]].dropna(subset=["style_color"])
    return master, pd.DataFrame(history_rows).dropna(subset=["style_color"])


def process_pla_report(df: pd.DataFrame, sku_map: pd.DataFrame, upload_date: date | str) -> pd.DataFrame:
    data = df.copy()
    data = data.merge(sku_map[["style_id", "internal_sku", "style_color"]].drop_duplicates("style_id"), left_on="product_id", right_on="style_id", how="left")
    return pd.DataFrame(
        {
            "upload_date": str(upload_date),
            "style_id": data["product_id"],
            "internal_sku": data["internal_sku"],
            "style_color": data["style_color"],
            "campaign_id": data["campaign_id"].astype(str),
            "campaign_name": data.get("campaign_name"),
            "impressions": _num(data["impressions"]).astype(int),
            "clicks": _num(data["clicks"]).astype(int),
            "ctr": _num(data["ctr"]),
            "cvr": _num(data["cvr"]),
            "avg_cpc": _num(data["avg_cpc"]),
            "spend": _num(data["budget_spend"]),
            "units_direct": _num(data["units_sold_direct"]).astype(int),
            "units_indirect": _num(data["units_sold_indirect"]).astype(int),
            "revenue": _num(data["total_revenue"]),
            "roi": _num(data["roi_total"]),
            "channel": "Myntra",
        }
    )


def process_visibility_report(df: pd.DataFrame, sku_map: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    periods = data["Time Period"].apply(parse_visibility_period)
    data["period_start"] = periods.apply(lambda item: item[0])
    data["period_end"] = periods.apply(lambda item: item[1])
    data = data.merge(sku_map[["style_id", "internal_sku", "style_color"]].drop_duplicates("style_id"), left_on="Product ID", right_on="style_id", how="left")
    return pd.DataFrame(
        {
            "period_start": data["period_start"],
            "period_end": data["period_end"],
            "style_id": data["Product ID"],
            "internal_sku": data["internal_sku"],
            "style_color": data["style_color"],
            "mrp": _num(data["MRP"]),
            "selling_price": _num(data["Selling Price"]),
            "discount_pct": _num(data["Discount(%)"]),
            "units_sold": _num(data["Units Sold"]).astype(int),
            "ros": _num(data["ROS"]),
            "revenue": _num(data["Revenue"]),
            "return_pct": _num(data["Return(%)"]),
            "consideration_pct": _num(data["Consideration(%)"]),
            "conversion_pct": _num(data["Conversion(%)"]),
            "list_page_count": _num(data["List Page Count"]).astype(int),
            "pdp_count": _num(data["PDP Count"]).astype(int),
            "channel": "Myntra",
        }
    ).dropna(subset=["period_start"])


def process_replenishment_upload(df: pd.DataFrame, uploaded_by: str | None = None) -> pd.DataFrame:
    data = df.copy()
    data["style_color"] = data["SKU"].apply(normalize_sku)
    return pd.DataFrame(
        {
            "style_color": data["style_color"],
            "replenishment_qty": _num(data["Manual Replenishment Qty"]).astype(int),
            "replenishment_date": date.today().isoformat(),
            "uploaded_by": uploaded_by,
            "notes": None,
            "status": "planned",
        }
    ).dropna(subset=["style_color"])
