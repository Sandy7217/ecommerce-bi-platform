"use client";

import { Area, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { ChartTooltip } from "@/components/charts/ChartTooltip";
import type { SalesReturnsForecast } from "@/lib/api";
import { formatINR, formatNumber, pct } from "@/lib/formatters";

const COLORS = ["#0f9488", "#2563eb", "#d97706", "#dc2626", "#64748b", "#7c3aed", "#0891b2"];

export function ChannelTrendChart({ data }: { data: { date: string; channel: string; sales_value: number; qty: number }[] }) {
  const preferred = ["Myntra", "Ajio", "Nykaa", "Flipkart", "Amazon", "TataCliq"];
  const channels = Array.from(new Set(data.map((row) => row.channel))).sort((a, b) => {
    const left = preferred.indexOf(a);
    const right = preferred.indexOf(b);
    return (left === -1 ? 99 : left) - (right === -1 ? 99 : right) || a.localeCompare(b);
  });
  const byDate = new Map<string, Record<string, string | number>>();
  data.forEach((row) => {
    const item = byDate.get(row.date) ?? { date: row.date };
    item[row.channel] = row.sales_value;
    item[`${row.channel} Qty`] = row.qty;
    byDate.set(row.date, item);
  });
  const rows = Array.from(byDate.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const total = data.reduce((sum, row) => sum + Number(row.sales_value || 0), 0);
  const totalQty = data.reduce((sum, row) => sum + Number(row.qty || 0), 0);

  return (
    <div className="h-80 rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="text-sm font-semibold text-ink">Channel sales trend</div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Total <b className="text-ink">{formatINR(total)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Qty <b className="text-ink">{formatNumber(totalQty)}</b></span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={rows}>
          <CartesianGrid stroke="#dbe3ee" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
          <YAxis stroke="#64748b" fontSize={12} />
          <Tooltip
            content={({ active, label, payload }) => {
              if (!active || !payload?.length) return null;
              return (
                <div className="rounded-lg border border-line bg-white px-3 py-2 text-xs shadow-soft">
                  <div className="mb-1 font-semibold text-ink">{label}</div>
                  <div className="space-y-1">
                    {payload
                      .filter((item) => !String(item.dataKey).endsWith(" Qty"))
                      .map((item) => {
                        const qty = Number((item.payload as Record<string, number>)[`${item.dataKey as string} Qty`] || 0);
                        return (
                          <div className="grid grid-cols-[8px_72px_90px_56px] items-center gap-2" key={String(item.dataKey)}>
                            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color || "#64748b" }} />
                            <span className="text-muted">{item.name}</span>
                            <span className="text-right font-medium text-ink">{formatINR(Number(item.value || 0))}</span>
                            <span className="text-right text-muted">{formatNumber(qty)}</span>
                          </div>
                        );
                      })}
                  </div>
                </div>
              );
            }}
          />
          <Legend />
          {channels.map((channel, index) => (
            <Line key={channel} type="monotone" dataKey={channel} stroke={COLORS[index % COLORS.length]} strokeWidth={2} dot={false} isAnimationActive />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SalesReturnsChart({ sales, returns }: { sales: { date: string; sales_value: number }[]; returns: { date: string; return_value: number }[] }) {
  const byDate = new Map<string, { date: string; sales_value: number; return_value: number }>();
  sales.forEach((row) => byDate.set(row.date, { ...(byDate.get(row.date) ?? { date: row.date, sales_value: 0, return_value: 0 }), sales_value: row.sales_value }));
  returns.forEach((row) => byDate.set(row.date, { ...(byDate.get(row.date) ?? { date: row.date, sales_value: 0, return_value: 0 }), return_value: row.return_value }));
  const rows = Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
  const avg = rows.length ? rows.reduce((sum, row) => sum + row.sales_value, 0) / rows.length : 0;
  const totalSales = rows.reduce((sum, row) => sum + row.sales_value, 0);
  const totalReturns = rows.reduce((sum, row) => sum + row.return_value, 0);

  return (
    <div className="h-80 rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="text-sm font-semibold text-ink">Sales vs returns</div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Sales <b className="text-ink">{formatINR(totalSales)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Returns <b className="text-ink">{formatINR(totalReturns)}</b></span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={rows}>
          <CartesianGrid stroke="#dbe3ee" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
          <YAxis stroke="#64748b" fontSize={12} />
          <Tooltip content={<ChartTooltip />} />
          <ReferenceLine y={avg} stroke="#64748b" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="sales_value" name="Sales" stroke="#0f9488" strokeWidth={2} dot={false} isAnimationActive />
          <Line type="monotone" dataKey="return_value" name="Returns" stroke="#dc2626" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ForecastChart({ forecast }: { forecast: SalesReturnsForecast }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selectedTrainingDays = Number(searchParams.get("forecast_training_days") || forecast.summary.training_requested_days || forecast.training_window_days || 730);
  const selectedHorizonDays = Number(searchParams.get("forecast_horizon_days") || forecast.horizon_days || 30);
  const updateForecastParam = (key: "forecast_training_days" | "forecast_horizon_days", value: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set(key, String(value));
    router.push(`${pathname}?${params.toString()}`);
  };
  const historyRows = forecast.history.slice(-30).map((row) => ({
    date: row.date,
    sales_value_history: row.sales_value,
    return_value_history: row.return_value,
  }));
  const forecastRows = forecast.forecast.map((row) => ({
    date: row.date,
    sales_value_forecast: row.sales_value,
    sales_value_low_forecast: row.sales_value_low ?? row.sales_value,
    sales_value_band_forecast: Math.max((row.sales_value_high ?? row.sales_value) - (row.sales_value_low ?? row.sales_value), 0),
    return_value_forecast: row.return_value,
    return_value_low_forecast: row.return_value_low ?? row.return_value,
    return_value_band_forecast: Math.max((row.return_value_high ?? row.return_value) - (row.return_value_low ?? row.return_value), 0),
    net_sales_forecast: row.net_sales,
  }));
  const rows = [...historyRows, ...forecastRows];
  const firstForecastDate = forecast.forecast[0]?.date;
  const selectedModels = forecast.summary.selected_models ? Object.values(forecast.summary.selected_models) : [];
  const selectedModelLabel = Array.from(new Set(selectedModels.map((item) => item.replace("_", " ")))).join(", ") || forecast.method || "auto";
  const backtestLabel = typeof forecast.summary.backtest_wape === "number" ? `${forecast.summary.backtest_wape.toFixed(1)}% WAPE` : "Not enough validation data";

  return (
    <div className="h-[27rem] rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink">30-day sales and return forecast</div>
          <div className="mt-1 text-xs text-muted">
            As of {forecast.summary.as_of_date || forecast.summary.history_end || "-"} | Training {formatNumber(forecast.summary.training_requested_days || forecast.training_window_days || 730)} requested,{" "}
            {formatNumber(forecast.summary.sales_training_days)} sales days, {formatNumber(forecast.summary.return_training_days)} return days
          </div>
          <div className="mt-1 text-xs text-muted">
            Model: {selectedModelLabel} | Backtest {backtestLabel} | Confidence {forecast.summary.confidence_level || "Medium"} | Myntra source: {forecast.summary.myntra_source_used || "Not detected"}
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2 text-xs">
          {[180, 365, 730].map((days) => (
            <button
              className={`rounded border px-2 py-1 transition duration-200 ease-in-out hover:scale-[1.02] ${selectedTrainingDays === days ? "border-teal bg-teal/10 text-teal" : "border-line bg-slate-50 text-muted"}`}
              key={days}
              onClick={() => updateForecastParam("forecast_training_days", days)}
              type="button"
            >
              {days === 730 ? "2 years" : `${days}d`}
            </button>
          ))}
          {[30, 60, 90].map((days) => (
            <button
              className={`rounded border px-2 py-1 transition duration-200 ease-in-out hover:scale-[1.02] ${selectedHorizonDays === days ? "border-blue-600 bg-blue-50 text-blue-700" : "border-line bg-slate-50 text-muted"}`}
              key={days}
              onClick={() => updateForecastParam("forecast_horizon_days", days)}
              type="button"
            >
              {days}d horizon
            </button>
          ))}
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Recent sales <b className="text-ink">{formatINR(forecast.summary.recent_sales_value)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Forecast sales <b className="text-ink">{formatINR(forecast.summary.forecast_sales_value)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Forecast returns <b className="text-ink">{formatINR(forecast.summary.forecast_return_value)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Net <b className="text-ink">{formatINR(forecast.summary.forecast_net_sales)}</b></span>
          <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Return rate <b className="text-ink">{pct(forecast.summary.forecast_return_pct)}</b></span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height="74%">
        <ComposedChart data={rows}>
          <CartesianGrid stroke="#dbe3ee" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
          <YAxis stroke="#64748b" fontSize={12} />
          <Tooltip content={<ChartTooltip />} />
          <Legend />
          {firstForecastDate ? <ReferenceLine x={firstForecastDate} stroke="#94a3b8" strokeDasharray="4 4" /> : null}
          <Area dataKey="sales_value_low_forecast" stackId="salesBand" stroke="none" fill="transparent" legendType="none" />
          <Area dataKey="sales_value_band_forecast" name="Sales confidence band" stackId="salesBand" stroke="none" fill="#2563eb" fillOpacity={0.1} legendType="none" />
          <Area dataKey="return_value_low_forecast" stackId="returnBand" stroke="none" fill="transparent" legendType="none" />
          <Area dataKey="return_value_band_forecast" name="Return confidence band" stackId="returnBand" stroke="none" fill="#d97706" fillOpacity={0.1} legendType="none" />
          <Line type="monotone" dataKey="sales_value_history" name="Sales history" stroke="#0f9488" strokeWidth={2} dot={false} isAnimationActive />
          <Line type="monotone" dataKey="return_value_history" name="Return history" stroke="#dc2626" strokeWidth={2} dot={false} isAnimationActive />
          <Line type="monotone" dataKey="sales_value_forecast" name="Sales forecast" stroke="#2563eb" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive />
          <Line type="monotone" dataKey="return_value_forecast" name="Return forecast" stroke="#d97706" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive />
          <Line type="monotone" dataKey="net_sales_forecast" name="Net forecast" stroke="#64748b" strokeWidth={1.5} strokeDasharray="2 4" dot={false} isAnimationActive />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
