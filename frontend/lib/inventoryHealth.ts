import type { MatrixRow } from "@/lib/api";

export type InventoryHealthTotals = {
  instock: number;
  broken: number;
  oos: number;
};

export function inventoryHealthTotals(matrix: MatrixRow[]): InventoryHealthTotals {
  const grandTotal = matrix.find((row) => row.category === "Grand Total");
  const rows = grandTotal ? [grandTotal] : matrix;

  return rows.reduce(
    (totals, row) => ({
      instock: totals.instock + Number(row.instock_inventory || 0),
      broken: totals.broken + Number(row.broken_inventory || 0),
      oos: totals.oos + Number(row.oos_inventory || 0),
    }),
    { instock: 0, broken: 0, oos: 0 }
  );
}
