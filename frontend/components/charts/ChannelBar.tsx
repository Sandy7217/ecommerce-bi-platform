"use client";

import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltip } from "@/components/charts/ChartTooltip";
import { formatINR, formatNumber } from "@/lib/formatters";

export function ChannelBar({ data, title = "Channel contribution" }: { data: { name: string; value: number; qty?: number }[]; title?: string }) {
  const avg = data.length ? data.reduce((sum, row) => sum + Number(row.value || 0), 0) / data.length : 0;
  const total = data.reduce((sum, row) => sum + Number(row.value || 0), 0);
  const totalQty = data.reduce((sum, row) => sum + Number(row.qty || 0), 0);
  return (
    <div className="h-72 rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="text-sm font-semibold text-ink">{title}</div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Total <b className="text-ink">{formatINR(total)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Qty <b className="text-ink">{formatNumber(totalQty)}</b></span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <BarChart data={data}>
          <CartesianGrid stroke="#dbe3ee" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
          <YAxis stroke="#64748b" fontSize={12} />
          <Tooltip content={<ChartTooltip />} />
          <ReferenceLine y={avg} stroke="#64748b" strokeDasharray="4 4" />
          <Bar dataKey="value" name="Sales" fill="#2563eb" radius={[4, 4, 0, 0]} isAnimationActive />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
