"use client";

import { formatINR, formatNumber } from "@/lib/formatters";

type TooltipProps = {
  active?: boolean;
  label?: string;
  payload?: { name: string; value: number; color?: string; dataKey?: string }[];
};

export function ChartTooltip({ active, label, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-2 text-xs shadow-soft">
      {label ? <div className="mb-1 font-semibold text-ink">{label}</div> : null}
      <div className="space-y-1">
        {payload.filter((item) => {
          const key = String(item.dataKey || item.name || "");
          return !key.includes("_band_") && !key.includes("_low_");
        }).map((item) => {
          const key = String(item.dataKey || item.name || "");
          const formatted = key.includes("sales") || key.includes("revenue") || key.includes("value") ? formatINR(Number(item.value || 0)) : formatNumber(Number(item.value || 0));
          return (
            <div className="flex items-center justify-between gap-5" key={`${item.name}-${key}`}>
              <span className="inline-flex items-center gap-2 text-muted">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color || "#64748b" }} />
                {item.name}
              </span>
              <span className="font-medium text-ink">{formatted}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
