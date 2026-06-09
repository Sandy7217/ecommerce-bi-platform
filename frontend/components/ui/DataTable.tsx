"use client";

import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ArrowDown, ArrowUp, Copy } from "lucide-react";
import toast from "react-hot-toast";

type Column<T extends object> = {
  key: keyof T | string;
  label: string;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
  align?: "left" | "right";
  copy?: boolean;
};

type DataTableProps<T extends object> = {
  columns: Column<T>[];
  rows: T[];
  rowKey?: (row: T, index: number) => string;
  empty?: ReactNode;
  maxHeight?: string;
  minWidth?: string;
  rowClassName?: (row: T, index: number) => string;
  onRowDoubleClick?: (row: T, index: number) => void;
};

function cellValue<T extends object>(row: T, key: keyof T | string) {
  return (row as Record<string, unknown>)[String(key)];
}

export function DataTable<T extends object>({
  columns,
  rows,
  rowKey,
  empty,
  maxHeight = "520px",
  minWidth = "100%",
  rowClassName,
  onRowDoubleClick,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);
  const safeRows = rows ?? [];

  const sortedRows = useMemo(() => {
    if (!sort) return safeRows;
    return [...safeRows].sort((a, b) => {
      const av = cellValue(a, sort.key);
      const bv = cellValue(b, sort.key);
      const result = typeof av === "number" && typeof bv === "number" ? av - bv : String(av ?? "").localeCompare(String(bv ?? ""));
      return sort.direction === "asc" ? result : -result;
    });
  }, [safeRows, sort]);

  const updateSort = (key: string) => {
    setSort((current) => {
      if (!current || current.key !== key) return { key, direction: "asc" };
      if (current.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  };

  if (!safeRows.length) {
    return <>{empty}</>;
  }

  return (
    <div className="min-w-0 w-full overflow-hidden rounded-lg border border-line bg-white shadow-soft">
      <div className="overflow-auto" style={{ maxHeight }}>
        <table className="min-w-full border-collapse text-sm" style={{ minWidth }}>
          <thead className="sticky top-0 z-[1] bg-slate-50 text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              {columns.map((column) => {
                const key = String(column.key);
                const active = sort?.key === key;
                const SortIcon = sort?.direction === "desc" ? ArrowDown : ArrowUp;
                return (
                  <th className={`px-4 py-3 font-semibold ${column.align === "right" ? "text-right" : ""}`} key={key}>
                    <button
                      className="inline-flex items-center gap-1 transition duration-200 ease-in-out hover:text-ink"
                      disabled={!column.sortable}
                      onClick={() => updateSort(key)}
                      type="button"
                    >
                      {column.label}
                      {column.sortable ? <SortIcon className={`h-3.5 w-3.5 ${active ? "opacity-100" : "opacity-30"}`} /> : null}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, index) => (
              <motion.tr
                className={`border-t border-line odd:bg-white even:bg-slate-50/30 transition duration-200 ease-in-out hover:bg-teal/5 ${rowClassName?.(row, index) ?? ""}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: Math.min(index, 12) * 0.035 }}
                key={rowKey ? rowKey(row, index) : index}
                onDoubleClick={() => onRowDoubleClick?.(row, index)}
              >
                {columns.map((column) => {
                  const raw = cellValue(row, column.key);
                  const value = column.render ? column.render(row) : String(raw ?? "");
                  return (
                    <td className={`px-4 py-3 text-ink ${column.align === "right" ? "text-right" : ""}`} key={String(column.key)}>
                      <span className="inline-flex items-center gap-2">
                        {value}
                        {column.copy && raw ? (
                          <button
                            aria-label="Copy value"
                            className="rounded p-1 text-muted transition duration-200 ease-in-out hover:bg-slate-100 hover:text-ink"
                            onClick={() => {
                              navigator.clipboard.writeText(String(raw));
                              toast.success("Copied");
                            }}
                            type="button"
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </button>
                        ) : null}
                      </span>
                    </td>
                  );
                })}
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
