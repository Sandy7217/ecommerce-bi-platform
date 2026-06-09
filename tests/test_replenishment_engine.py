from __future__ import annotations

from datetime import date

from backend.services.replenishment_engine import (
    build_hybrid_replenishment_plan,
    pending_replenishment_by_style,
    round_replenishment_qty,
    style_sales_profile_by_style,
)


def test_round_replenishment_qty_uses_moq_ladders_and_ceil_hundreds() -> None:
    assert round_replenishment_qty(0) == 0
    assert round_replenishment_qty(225) == 500
    assert round_replenishment_qty(501) == 800
    assert round_replenishment_qty(870) == 1000
    assert round_replenishment_qty(1265) == 1300
    assert round_replenishment_qty(1901) == 2000


def test_pending_replenishment_excludes_closed_statuses() -> None:
    rows = [
        {"style_color": "nm001-red", "replenishment_qty": 300, "status": "planned"},
        {"style_color": "nm001-red", "replenishment_qty": 200, "status": "completed"},
        {"style_color": "nm002-blue", "replenishment_qty": 400, "status": "pending"},
        {"style_color": "nm002-blue", "replenishment_qty": 100, "status": "cancelled"},
    ]

    assert pending_replenishment_by_style(rows) == {"nm001-red": 300, "nm002-blue": 400}


def test_hybrid_plan_subtracts_inventory_and_manual_replenishment_before_moq() -> None:
    rows = [
        {
            "style_color": "nm001-red",
            "category_new": "NOOS",
            "inventory_status": "INSTOCK",
            "sale_grade_old": "NOOS",
            "total_inventory": 300,
            "ros_7d": 10,
            "ros_30d": 8,
        }
    ]
    manual_rows = [{"style_color": "nm001-red", "replenishment_qty": 300, "status": "planned"}]

    plan = build_hybrid_replenishment_plan(
        rows,
        manual_replenishment_rows=manual_rows,
        style_sales_profile_by_style={"nm001-red": {"qty_30d": 30, "qty_90d": 80, "active_sale_days_90d": 12}},
        lead_time_days=45,
        review_cycle_days=15,
        today=date(2026, 5, 24),
    )

    item = plan["items"][0]
    assert item["predicted_ros"] == 8.7
    assert item["target_stock"] == 522
    assert item["pending_replenishment_qty"] == 300
    assert item["raw_replenishment_qty"] == 0
    assert item["recommended_replenishment_qty"] == 0
    assert item["already_planned"] is True
    assert item["urgency"] == "Covered"


def test_hybrid_plan_marks_stock_covered_noos_styles_as_covered_not_urgent() -> None:
    rows = [
        {
            "style_color": "noos-covered",
            "category_new": "NOOS",
            "sale_grade_old": "NOOS",
            "inventory_status": "OOS",
            "total_inventory": 1000,
            "ros_7d": 2,
            "ros_30d": 2,
        }
    ]

    plan = build_hybrid_replenishment_plan(
        rows,
        style_sales_profile_by_style={"noos-covered": {"qty_30d": 20, "qty_90d": 60, "active_sale_days_90d": 10}},
        lead_time_days=45,
        review_cycle_days=15,
        today=date(2026, 5, 24),
    )

    item = plan["items"][0]
    assert item["raw_replenishment_qty"] == 0
    assert item["recommended_replenishment_qty"] == 0
    assert item["urgency"] == "Covered"
    assert plan["summary"]["urgent_styles"] == 0


def test_hybrid_plan_uses_category_baseline_for_oos_styles_and_allocates_sizes() -> None:
    rows = [
        {
            "style_color": "nm001-red",
            "category_new": "NOOS",
            "inventory_status": "INSTOCK",
            "sale_grade_old": "NOOS",
            "total_inventory": 900,
            "ros_7d": 6,
            "ros_30d": 6,
        },
        {
            "style_color": "nm002-red",
            "category_new": "NOOS",
            "inventory_status": "OOS",
            "sale_grade_old": "NOOS",
            "total_inventory": 0,
            "ros_7d": 0,
            "ros_30d": 0,
        },
    ]
    size_inventory = {
        "nm002-red": {"S": 0, "M": 0, "L": 0, "XL": 0},
    }
    size_sales = {
        "nm002-red": {"S": 1, "M": 4, "L": 3, "XL": 2},
    }

    plan = build_hybrid_replenishment_plan(
        rows,
        manual_replenishment_rows=[],
        size_inventory_by_style=size_inventory,
        size_sales_by_style=size_sales,
        style_sales_profile_by_style={
            "nm001-red": {"qty_30d": 30, "qty_90d": 90, "active_sale_days_90d": 18},
            "nm002-red": {"qty_30d": 0, "qty_90d": 12, "active_sale_days_90d": 6},
        },
        lead_time_days=45,
        review_cycle_days=15,
        today=date(2026, 5, 24),
    )

    oos_item = next(item for item in plan["items"] if item["style_color"] == "nm002-red")
    assert oos_item["predicted_ros"] == 6
    assert oos_item["recommended_replenishment_qty"] == 500
    assert oos_item["urgency"].startswith("P0")
    assert oos_item["stockout_date"] == "2026-05-24"
    assert oos_item["order_by_date"] == "2026-04-09"
    assert oos_item["size_replenishment"] == [
        {"size": "M", "current_qty": 0, "recommended_qty": 200},
        {"size": "L", "current_qty": 0, "recommended_qty": 100},
        {"size": "XL", "current_qty": 0, "recommended_qty": 100},
        {"size": "S", "current_qty": 0, "recommended_qty": 100},
    ]


def test_style_sales_profile_counts_last_30_and_90_days() -> None:
    profile = style_sales_profile_by_style(
        [
            {"date": "2026-05-24", "style_color": "nm001-red", "qty": 2},
            {"date": "2026-05-23", "style_color": "nm001-red", "qty": 3},
            {"date": "2026-04-01", "style_color": "nm001-red", "qty": 4},
            {"date": "2026-01-01", "style_color": "nm001-red", "qty": 10},
        ],
        today=date(2026, 5, 24),
    )

    assert profile["nm001-red"] == {"qty_30d": 5, "qty_90d": 9, "active_sale_days_90d": 3}


def test_hybrid_plan_only_recommends_good_noos_sale_status_styles() -> None:
    rows = [
        {
            "style_color": "noos-good",
            "category_new": "NOOS",
            "sale_grade_old": "NOOS",
            "inventory_status": "INSTOCK",
            "total_inventory": 0,
            "ros_7d": 3,
            "ros_30d": 4,
        },
        {
            "style_color": "red-good",
            "category_new": "Red",
            "sale_grade_old": "Red",
            "inventory_status": "OOS",
            "total_inventory": 0,
            "ros_7d": 3,
            "ros_30d": 4,
        },
        {
            "style_color": "noos-slow",
            "category_new": "NOOS",
            "sale_grade_old": "NOOS(Red)",
            "inventory_status": "INSTOCK",
            "total_inventory": 0,
            "ros_7d": 0.1,
            "ros_30d": 0.8,
        },
        {
            "style_color": "old-discontinue",
            "category_new": "Discontinue",
            "sale_grade_old": "Discontinue",
            "inventory_status": "OOS",
            "total_inventory": 0,
            "ros_7d": 0,
            "ros_30d": 0,
        },
    ]

    plan = build_hybrid_replenishment_plan(
        rows,
        style_sales_profile_by_style={
            "noos-good": {"qty_30d": 20, "qty_90d": 50, "active_sale_days_90d": 10},
            "red-good": {"qty_30d": 20, "qty_90d": 50, "active_sale_days_90d": 10},
            "noos-slow": {"qty_30d": 2, "qty_90d": 4, "active_sale_days_90d": 2},
            "old-discontinue": {"qty_30d": 0, "qty_90d": 0, "active_sale_days_90d": 0},
        },
        lead_time_days=45,
        review_cycle_days=15,
        today=date(2026, 5, 24),
    )

    items = {item["style_color"]: item for item in plan["items"]}
    assert items["noos-good"]["recommended_replenishment_qty"] == 500
    assert items["noos-good"]["action"] == "Auto"
    assert items["red-good"]["recommended_replenishment_qty"] == 0
    assert items["red-good"]["action"] == "No Replenishment"
    assert items["red-good"]["replenishment_reason"] == "Sale status is not NOOS"
    assert items["noos-slow"]["recommended_replenishment_qty"] == 0
    assert items["noos-slow"]["replenishment_reason"] == "Sales performance below replenishment threshold"
    assert items["old-discontinue"]["recommended_replenishment_qty"] == 0
    assert items["old-discontinue"]["urgency"] == "No Replenishment"
    assert items["old-discontinue"]["replenishment_reason"] == "Discontinued and no sales in last 90 days"
    assert plan["summary"]["recommended_qty"] == 500
    assert plan["summary"]["eligible_styles"] == 1
    assert plan["summary"]["no_replenishment_styles"] == 3
