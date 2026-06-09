from __future__ import annotations

import unittest

import pandas as pd

from backend.services.data_ingestion import process_myntra_orders, process_unicommerce_sales
from backend.services.sku_mapper import is_myntra_channel, normalize_channel


def _myntra_row(po_type: str, style_id: int, seller_sku: str, order_id: str) -> dict:
    return {
        "order status": "C",
        "style id": style_id,
        "seller sku code": seller_sku,
        "created on": "2026-05-20",
        "final amount": 1499,
        "total mrp": 2499,
        "discount": 1000,
        "store order id": order_id,
        "state": "MH",
        "city": "Mumbai",
        "size": "M",
        "po_type": po_type,
    }


def _unicommerce_row(channel: str, order_date: str, created: str, order_id: str, sku: str) -> dict:
    return {
        "Channel Name": channel,
        "Sale Order Item Status": "DISPATCHED",
        "Order Date as dd/mm/yyyy hh:MM:ss": order_date,
        "Created": created,
        "Item SKU Code": sku,
        "Selling Price": 1000,
        "MRP": 1500,
        "Discount": 500,
        "Sale Order Code": order_id,
        "Shipping Address State": "MH",
        "Shipping Address City": "Mumbai",
        "Item Type Size": "M",
    }


class MyntraOrderIngestionTest(unittest.TestCase):
    def test_po_type_splits_myntra_marketplace_between_ppmp_and_sjit(self) -> None:
        orders = pd.DataFrame(
            [
                _myntra_row("PPMP", 101, "seller-ppmp", "ORD-PPMP"),
                _myntra_row("SJIT", 102, "seller-sjit", "ORD-SJIT"),
            ]
        )
        sku_map = pd.DataFrame(
            [
                {"style_id": 101, "myntra_seller_sku": "seller-ppmp", "internal_sku": "nm001-red-m", "style_color": "nm001-red"},
                {"style_id": 102, "myntra_seller_sku": "seller-sjit", "internal_sku": "nm002-blue-m", "style_color": "nm002-blue"},
            ]
        )

        processed = process_myntra_orders(orders, sku_map).sort_values("order_id").reset_index(drop=True)

        self.assertEqual(processed.loc[0, "channel"], "MYNTRAPPMP")
        self.assertEqual(processed.loc[0, "marketplace"], "Myntra")
        self.assertEqual(processed.loc[1, "channel"], "MYNTRASJIT")
        self.assertEqual(processed.loc[1, "marketplace"], "Myntra SJIT")
        self.assertTrue(is_myntra_channel("Myntra SJIT"))
        self.assertEqual(normalize_channel("MYNTRASJIT"), "Myntra SJIT")

    def test_po_type_mapping_stays_aligned_after_excluding_rows(self) -> None:
        excluded = _myntra_row("PPMP", 100, "seller-excluded", "ORD-EXCLUDED")
        excluded["order status"] = "F"
        orders = pd.DataFrame(
            [
                excluded,
                _myntra_row("SJIT", 102, "seller-sjit", "ORD-SJIT"),
            ]
        )
        sku_map = pd.DataFrame(
            [
                {"style_id": 102, "myntra_seller_sku": "seller-sjit", "internal_sku": "nm002-blue-m", "style_color": "nm002-blue"},
            ]
        )

        processed = process_myntra_orders(orders, sku_map).reset_index(drop=True)

        self.assertEqual(len(processed), 1)
        self.assertEqual(processed.loc[0, "order_id"], "ORD-SJIT")
        self.assertEqual(processed.loc[0, "channel"], "MYNTRASJIT")
        self.assertEqual(processed.loc[0, "marketplace"], "Myntra SJIT")

    def test_po_type_column_matching_allows_export_header_variants(self) -> None:
        orders = pd.DataFrame([_myntra_row("SJIT", 102, "seller-sjit", "ORD-SJIT")]).rename(columns={"po_type": "PO Type"})
        sku_map = pd.DataFrame(
            [
                {"style_id": 102, "myntra_seller_sku": "seller-sjit", "internal_sku": "nm002-blue-m", "style_color": "nm002-blue"},
            ]
        )

        processed = process_myntra_orders(orders, sku_map).reset_index(drop=True)

        self.assertEqual(processed.loc[0, "channel"], "MYNTRASJIT")
        self.assertEqual(processed.loc[0, "marketplace"], "Myntra SJIT")

    def test_sjit_order_report_filename_defaults_missing_po_type_to_sjit(self) -> None:
        row = _myntra_row("PPMP", 102, "seller-sjit", "ORD-SJIT")
        row.pop("po_type")
        row["created on"] = "24:31.0"
        orders = pd.DataFrame([row])
        sku_map = pd.DataFrame(
            [
                {"style_id": 102, "myntra_seller_sku": "seller-sjit", "internal_sku": "nm002-blue-m", "style_color": "nm002-blue"},
            ]
        )

        processed = process_myntra_orders(
            orders,
            sku_map,
            file_name="zN2zzhUk_2026-03-22_SJIT_Orders_Report_24113_2026-03-21_2026-03-21.csv",
        ).reset_index(drop=True)

        self.assertEqual(processed.loc[0, "channel"], "MYNTRASJIT")
        self.assertEqual(processed.loc[0, "marketplace"], "Myntra SJIT")
        self.assertEqual(processed.loc[0, "date"], "2026-03-21")

    def test_unicommerce_sales_use_created_date_and_can_retain_myntra_ppmp(self) -> None:
        orders = pd.DataFrame(
            [
                _unicommerce_row("MYNTRAPPMP", "2026-05-24 23:57:55", "2026-05-25 00:13:25", "UNI-MYNTRA", "NM001-Red-M"),
                _unicommerce_row("AJIO_DROPSHIP", "2026-05-25 09:12:52", "2026-05-25 09:13:18", "UNI-AJIO", "NM002-Blue-M"),
            ]
        )

        processed = process_unicommerce_sales(orders, source="unicommerce", include_myntra=True).sort_values("order_id").reset_index(drop=True)

        self.assertEqual(len(processed), 2)
        self.assertEqual(processed.loc[0, "channel"], "AJIO_DROPSHIP")
        self.assertEqual(processed.loc[0, "date"], "2026-05-25")
        self.assertEqual(processed.loc[1, "channel"], "MYNTRAPPMP")
        self.assertEqual(processed.loc[1, "date"], "2026-05-25")

    def test_unicommerce_duplicate_order_sku_preserves_quantity(self) -> None:
        orders = pd.DataFrame(
            [
                _unicommerce_row("MYNTRAPPMP", "2026-05-25 09:12:52", "2026-05-25 09:13:18", "UNI-MYNTRA", "NM001-Red-M"),
                _unicommerce_row("MYNTRAPPMP", "2026-05-25 09:12:52", "2026-05-25 09:13:18", "UNI-MYNTRA", "NM001-Red-M"),
            ]
        )

        processed = process_unicommerce_sales(orders, source="unicommerce", include_myntra=True).reset_index(drop=True)

        self.assertEqual(len(processed), 1)
        self.assertEqual(processed.loc[0, "qty"], 2)
        self.assertEqual(processed.loc[0, "selling_price"], 1000)


if __name__ == "__main__":
    unittest.main()
