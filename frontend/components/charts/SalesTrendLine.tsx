"use client";

import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltip } from "@/components/charts/ChartTooltip";
import { formatINR, formatNumber } from "@/lib/formatters";

export function SalesTrendLine({ data, title = "Daily sales trend" }: { data: { date: string; sales_value: number; qty?: number }[]; title?: string }) {
  const avg = data.length ? data.reduce((sum, row) => sum + Number(row.sales_value || 0), 0) / data.length : 0;
  const total = data.reduce((sum, row) => sum + Number(row.sales_value || 0), 0);
  const totalQty = data.reduce((sum, row) => sum + Number(row.qty || 0), 0);
  return (
    <div className="h-72 rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="text-sm font-semibold text-ink">{title}</div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Total <b className="text-ink">{formatINR(total)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Qty <b className="text-ink">{formatNumber(totalQty)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Avg <b className="text-ink">{formatINR(avg)}</b></span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="salesGradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="5%" stopColor="#0f9488" stopOpacity={0.22} />
              <stop offset="95%" stopColor="#0f9488" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#dbe3ee" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
          <YAxis stroke="#64748b" fontSize={12} />
          <Tooltip content={<ChartTooltip />} />
          <ReferenceLine y={avg} stroke="#64748b" strokeDasharray="4 4" />
          <Area type="monotone" dataKey="sales_value" name="Sales" stroke="#0f9488" strokeWidth={2} fill="url(#salesGradient)" isAnimationActive />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
