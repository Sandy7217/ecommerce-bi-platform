"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltip } from "@/components/charts/ChartTooltip";
import { formatNumber } from "@/lib/formatters";

type ReplenishmentChartRow = {
  name: string;
  qty?: number;
  styles?: number;
};

type ReplenishmentBarChartProps = {
  title: string;
  data: ReplenishmentChartRow[];
  barColor?: string;
  valueLabel?: string;
};

export function ReplenishmentBarChart({ title, data, barColor = "#0f9488", valueLabel = "Qty" }: ReplenishmentBarChartProps) {
  const rows = data.filter((row) => Number(row.qty || row.styles || 0) > 0).slice(0, 8);
  const totalQty = rows.reduce((sum, row) => sum + Number(row.qty || 0), 0);
  const totalStyles = rows.reduce((sum, row) => sum + Number(row.styles || 0), 0);

  return (
    <div className="h-72 min-w-0 rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="text-sm font-semibold text-ink">{title}</div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          {totalQty ? <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Qty <b className="text-ink">{formatNumber(totalQty)}</b></span> : null}
          {totalStyles ? <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Styles <b className="text-ink">{formatNumber(totalStyles)}</b></span> : null}
        </div>
      </div>
      <ResponsiveContainer width="100%" height="82%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#dbe3ee" strokeDasharray="3 3" vertical={false} />
          <XAxis type="number" stroke="#64748b" fontSize={11} />
          <YAxis type="category" dataKey="name" width={86} stroke="#64748b" fontSize={11} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <Bar dataKey="qty" name={valueLabel} fill={barColor} radius={[0, 4, 4, 0]} isAnimationActive />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
