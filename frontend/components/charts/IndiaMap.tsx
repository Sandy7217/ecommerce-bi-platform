"use client";

import { useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";

import type { RegionalHeatmapState, RegionalState, StateTopStyle } from "@/lib/api";
import { exactINR, formatINR, formatNumber, pct } from "@/lib/formatters";

type HeatmapRow = RegionalHeatmapState | (RegionalState & Partial<RegionalHeatmapState>);
type GeoShape = {
  rsmKey: string;
  properties: {
    NAME_1?: string;
    ST_NM?: string;
    name?: string;
  };
};

const INDIA_TOPOLOGY = "/maps/india-states.json";
const HEAT_COLORS = ["#dcfce7", "#bef264", "#fde68a", "#fb923c", "#dc2626"];

function normalizeState(value: string): string {
  return value.toLowerCase().replace(/&/g, "and").replace(/\s+/g, " ").trim();
}

function geoStateKey(value: string): string {
  const normalized = normalizeState(value);
  const aliases: Record<string, string> = {
    orissa: "odisha",
    uttaranchal: "uttarakhand",
    "andaman and nicobar": "andaman and nicobar islands",
    "jammu and kashmir": "jammu and kashmir",
  };
  return aliases[normalized] ?? normalized;
}

function stateName(geo: GeoShape): string {
  return String(geo.properties.NAME_1 || geo.properties.ST_NM || geo.properties.name || "");
}

function colorIndex(value: number, max: number) {
  if (value <= 0) return -1;
  if (max <= 0) return 0;
  return Math.min(Math.floor((value / max) * HEAT_COLORS.length), HEAT_COLORS.length - 1);
}

function buildLegend(max: number) {
  const step = max / HEAT_COLORS.length;
  return HEAT_COLORS.map((color, index) => {
    const start = index === 0 ? 0 : step * index;
    const end = index === HEAT_COLORS.length - 1 ? max : step * (index + 1);
    return {
      color,
      label: index === HEAT_COLORS.length - 1 ? `${formatINR(start)}+` : `${formatINR(start)} - ${formatINR(end)}`,
    };
  });
}

function topStyles(styles?: StateTopStyle[]) {
  return (styles ?? []).slice(0, 5);
}

export function IndiaMap({ data }: { data: HeatmapRow[] }) {
  const [hovered, setHovered] = useState<HeatmapRow | null>(null);
  const byState = useMemo(() => new Map(data.map((row) => [normalizeState(row.state), row])), [data]);
  const maxSales = Math.max(...data.map((row) => row.sales), 1);
  const totalSales = data.reduce((sum, row) => sum + Number(row.sales || 0), 0);
  const totalQty = data.reduce((sum, row) => sum + Number(row.qty || 0), 0);
  const totalReturnQty = data.reduce((sum, row) => sum + Number(row.return_qty || 0), 0);
  const legend = buildLegend(maxSales);
  const topStates = [...data].sort((a, b) => b.sales - a.sales).slice(0, 5);

  return (
    <div className="relative min-h-[560px] rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink">Regional sales heatmap</div>
          <div className="mt-1 text-xs text-muted">Darker states have higher MTD sales</div>
        </div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">
            Sales <b className="text-ink">{formatINR(totalSales)}</b>
          </span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">
            Qty <b className="text-ink">{formatNumber(totalQty)}</b>
          </span>
          {totalReturnQty ? (
            <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">
              Return Qty <b className="text-ink">{formatNumber(totalReturnQty)}</b>
            </span>
          ) : null}
        </div>
      </div>

      {hovered ? (
        <div className="absolute right-4 top-20 z-[3] w-72 rounded-lg border border-line bg-white px-3 py-3 text-xs shadow-soft">
          <div className="mb-2 flex items-start justify-between gap-3">
            <div className="font-semibold text-ink">{hovered.state}</div>
            <div className="rounded bg-slate-50 px-2 py-1 font-medium text-muted">{pct(Number(hovered.return_pct || 0))} returns</div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-muted">
            <div>Sales <b className="block text-ink">{exactINR(hovered.sales)}</b></div>
            <div>Qty <b className="block text-ink">{formatNumber(hovered.qty)}</b></div>
            <div>Return value <b className="block text-ink">{exactINR(Number(hovered.return_value || 0))}</b></div>
            <div>Return qty <b className="block text-ink">{formatNumber(Number(hovered.return_qty || 0))}</b></div>
          </div>
          {topStyles(hovered.top_styles).length ? (
            <div className="mt-3 border-t border-line pt-2">
              <div className="mb-1 font-medium text-ink">Top styles</div>
              <div className="space-y-1">
                {topStyles(hovered.top_styles).map((style) => (
                  <div className="flex items-center justify-between gap-3" key={style.style_color}>
                    <span className="truncate text-muted">{style.style_color}</span>
                    <span className="shrink-0 font-medium text-ink">{formatINR(style.sales)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-4">
        <div className="rounded border border-line bg-slate-50/40 p-3">
          <ComposableMap
            className="mx-auto h-[430px] w-full max-w-[520px]"
            height={430}
            projection="geoMercator"
            projectionConfig={{ scale: 700, center: [82, 22] }}
            width={420}
          >
            <Geographies geography={INDIA_TOPOLOGY}>
              {({ geographies }: { geographies: GeoShape[] }) =>
                geographies.map((geo) => {
                  const row = byState.get(geoStateKey(stateName(geo)));
                  const index = colorIndex(Number(row?.sales || 0), maxSales);
                  return (
                    <Geography
                      geography={geo}
                      key={geo.rsmKey}
                      fill={index >= 0 ? HEAT_COLORS[index] : "#f1f5f9"}
                      stroke="#ffffff"
                      strokeWidth={0.7}
                      style={{
                        default: { outline: "none", transition: "fill 160ms ease" },
                        hover: { outline: "none", fill: "#0f9488" },
                        pressed: { outline: "none" },
                      }}
                      onMouseEnter={() => setHovered(row ?? null)}
                      onMouseLeave={() => setHovered(null)}
                    />
                  );
                })
              }
            </Geographies>
          </ComposableMap>
        </div>
        <div className="grid gap-3 xl:grid-cols-[220px_1fr]">
          <div className="rounded border border-line bg-slate-50/50 p-3">
            <div className="mb-2 text-xs font-semibold uppercase text-muted">Sales legend</div>
            <div className="space-y-2">
              {legend.map((item) => (
                <div className="flex items-center gap-2 text-xs text-muted" key={item.label}>
                  <span className="h-3 w-6 rounded-sm border border-white shadow-sm" style={{ backgroundColor: item.color }} />
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-2 text-xs sm:grid-cols-2 xl:grid-cols-1">
            {topStates.map((row) => (
              <button
                className="w-full rounded border border-line bg-slate-50/50 px-3 py-2 text-left transition duration-200 ease-in-out hover:scale-[1.02] hover:bg-white"
                key={row.state}
                onMouseEnter={() => setHovered(row)}
                onMouseLeave={() => setHovered(null)}
                type="button"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-ink">{row.state}</span>
                  <span className="font-semibold text-ink">{formatINR(row.sales)}</span>
                </div>
                <div className="mt-1 text-muted">{formatNumber(row.qty)} units · {pct(Number(row.return_pct || 0))} returns</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
