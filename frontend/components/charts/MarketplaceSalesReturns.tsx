"use client";

import type { MarketplaceSummary } from "@/lib/api";
import { exactINR, formatINR, formatNumber, pct } from "@/lib/formatters";

export function MarketplaceSalesReturns({ data, compact = false }: { data: MarketplaceSummary[]; compact?: boolean }) {
  const totalSales = data.reduce((sum, row) => sum + Number(row.sales_value || 0), 0);
  const totalReturns = data.reduce((sum, row) => sum + Number(row.return_value || 0), 0);
  const totalQty = data.reduce((sum, row) => sum + Number(row.sales_qty || 0), 0);
  const totalReturnQty = data.reduce((sum, row) => sum + Number(row.return_qty || 0), 0);
  const maxSales = Math.max(...data.map((row) => row.sales_value), 1);
  const maxReturns = Math.max(...data.map((row) => row.return_value), 1);

  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink">Marketplace sales and returns</div>
          <div className="mt-1 text-xs text-muted">Sales, return value, units, and return percentage by marketplace</div>
        </div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Sales <b className="text-ink">{formatINR(totalSales)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Returns <b className="text-ink">{formatINR(totalReturns)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Qty <b className="text-ink">{formatNumber(totalQty)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Return Qty <b className="text-ink">{formatNumber(totalReturnQty)}</b></span>
        </div>
      </div>
      <div className={`grid gap-3 ${compact ? "lg:grid-cols-2" : "lg:grid-cols-3"}`}>
        {data.map((row) => (
          <div className="rounded border border-line bg-slate-50/40 p-3" key={row.marketplace}>
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="font-medium text-ink">{row.marketplace}</div>
              <div className="rounded bg-white px-2 py-1 text-xs font-medium text-danger">{pct(row.return_pct)} returns</div>
            </div>
            <div className="space-y-3 text-xs">
              <div>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <span className="text-muted">Sales</span>
                  <span className="font-medium text-ink">{formatINR(row.sales_value)} · {formatNumber(row.sales_qty)} units</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-teal/10">
                  <div className="h-full rounded-full bg-teal transition-all duration-500 ease-in-out" style={{ width: `${Math.max((row.sales_value / maxSales) * 100, row.sales_value ? 4 : 0)}%` }} />
                </div>
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <span className="text-muted">Returns</span>
                  <span className="font-medium text-ink">{formatINR(row.return_value)} · {formatNumber(row.return_qty)} units</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-danger/10">
                  <div className="h-full rounded-full bg-danger transition-all duration-500 ease-in-out" style={{ width: `${Math.max((row.return_value / maxReturns) * 100, row.return_value ? 4 : 0)}%` }} />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 overflow-hidden rounded border border-line">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Marketplace</th>
              <th className="px-3 py-2 text-right font-medium">Sales</th>
              <th className="px-3 py-2 text-right font-medium">Sales Qty</th>
              <th className="px-3 py-2 text-right font-medium">Returns</th>
              <th className="px-3 py-2 text-right font-medium">Return Qty</th>
              <th className="px-3 py-2 text-right font-medium">Return %</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, index) => (
              <tr className={index % 2 ? "bg-slate-50/50" : "bg-white"} key={row.marketplace}>
                <td className="px-3 py-2 font-medium text-ink">{row.marketplace}</td>
                <td className="px-3 py-2 text-right text-ink">{exactINR(row.sales_value)}</td>
                <td className="px-3 py-2 text-right text-muted">{formatNumber(row.sales_qty)}</td>
                <td className="px-3 py-2 text-right text-ink">{exactINR(row.return_value)}</td>
                <td className="px-3 py-2 text-right text-muted">{formatNumber(row.return_qty)}</td>
                <td className="px-3 py-2 text-right text-muted">{pct(row.return_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
