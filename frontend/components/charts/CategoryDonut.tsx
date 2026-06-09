"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { ChartTooltip } from "@/components/charts/ChartTooltip";
import { formatINR, formatNumber } from "@/lib/formatters";

const COLORS = ["#0f9488", "#2563eb", "#d97706", "#dc2626", "#64748b", "#94a3b8"];

type DonutRow = { name: string; value: number; qty?: number; styles?: number };

export function CategoryDonut({ data, title = "Category mix", valueLabel = "Value" }: { data: DonutRow[]; title?: string; valueLabel?: string }) {
  const orderedData = [...data].sort((a, b) => Number(b.value || 0) - Number(a.value || 0));
  const chartData = orderedData.filter((row) => Number(row.value || 0) > 0);
  const total = orderedData.reduce((sum, row) => sum + Number(row.value || 0), 0);
  const totalQty = orderedData.reduce((sum, row) => sum + Number(row.qty || 0), 0);
  const totalStyles = orderedData.reduce((sum, row) => sum + Number(row.styles || 0), 0);
  const isRevenue = valueLabel.toLowerCase().includes("revenue");
  let currentPercent = 0;
  const donutSegments = chartData.map((row, index) => {
    const start = currentPercent;
    const end = currentPercent + (Number(row.value || 0) * 100) / Math.max(total, 1);
    currentPercent = end;
    return `${COLORS[index % COLORS.length]} ${start}% ${end}%`;
  });
  const donutBackground = chartData.length ? `conic-gradient(${donutSegments.join(", ")})` : "#e2e8f0";
  return (
    <div className="min-w-0 w-full min-h-[340px] rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="text-sm font-semibold text-ink">{title}</div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Total <b className="text-ink">{isRevenue ? formatINR(total) : formatNumber(total)}</b></span>
          {totalQty ? <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Qty <b className="text-ink">{formatNumber(totalQty)}</b></span> : null}
          {totalStyles ? <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Styles <b className="text-ink">{formatNumber(totalStyles)}</b></span> : null}
        </div>
      </div>
      <div className="grid min-h-[260px] grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-3">
        <div className="relative h-[250px]">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="relative h-44 w-44 rounded-full shadow-inner" style={{ background: donutBackground }}>
              <div className="absolute inset-10 rounded-full bg-white shadow-soft" />
            </div>
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={chartData.length > 1 ? 1 : 0} startAngle={90} endAngle={-270} isAnimationActive>
                {chartData.map((entry, index) => (
                  <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-center">
            <div>
              <div className="text-[10px] uppercase text-muted">{valueLabel}</div>
              <div className="text-sm font-semibold text-ink">{isRevenue ? formatINR(total) : formatNumber(total)}</div>
            </div>
          </div>
        </div>
        <div className="max-h-[250px] space-y-2 overflow-auto pr-1 text-xs">
          {orderedData.map((row, index) => (
            <div className="rounded border border-line bg-slate-50/40 px-2 py-2" key={row.name}>
              <div className="flex items-start justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2 text-muted">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                <span className="truncate">{row.name}</span>
              </span>
              <span className="text-right font-medium text-ink" title={`${valueLabel}: ${row.value}`}>
                {isRevenue ? formatINR(row.value) : formatNumber(row.value)}
                <span className="block text-[10px] text-muted">{total ? ((row.value * 100) / total).toFixed(1) : "0.0"}%</span>
              </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-2 pl-4 text-[10px] text-muted">
                {typeof row.qty === "number" ? <span>Qty {formatNumber(row.qty)}</span> : null}
                {typeof row.styles === "number" ? <span>Styles {formatNumber(row.styles)}</span> : null}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
