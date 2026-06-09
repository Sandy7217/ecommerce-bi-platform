"use client";

import { useMemo } from "react";

import { CategoryDonut } from "@/components/charts/CategoryDonut";
import { SalesTrendLine } from "@/components/charts/SalesTrendLine";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { KPICard } from "@/components/ui/KPICard";
import { MotionPanel } from "@/components/ui/PageTransition";
import { exactINR, formatINR, formatNumber, pct } from "@/lib/formatters";
import type { SalesKpis } from "@/lib/api";

export type ReturnSummary = {
  return_value: number;
  return_qty: number;
};

export type ReturnChannel = {
  channel: string;
  return_value: number;
};

export type ReturnSku = {
  style_color: string;
  sales_qty: number;
  return_qty: number;
  return_pct: number;
  inventory: number;
  sale_grade: string;
  share: number;
};

export type ReturnTrend = {
  date: string;
  return_value: number;
  return_qty: number;
};

export function ReturnsClient({
  sales,
  summary,
  byChannel,
  highSkus,
  trend,
}: {
  sales: SalesKpis;
  summary: ReturnSummary;
  byChannel: ReturnChannel[];
  highSkus: ReturnSku[];
  trend: ReturnTrend[];
}) {
  const channelRows = useMemo(
    () => byChannel.map((row) => ({ name: row.channel || "Unknown", value: Number(row.return_value || 0) })).sort((a, b) => b.value - a.value),
    [byChannel]
  );
  const topSku = highSkus[0]?.style_color || "NA";
  const trendRows = trend.map((row) => ({ date: row.date, sales_value: Number(row.return_value || 0), qty: row.return_qty }));

  return (
    <div className="w-full space-y-6">
      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <KPICard title="Return Value" value={summary.return_value} format={formatINR} alert="orange" delay={0} />
        <KPICard title="Return Qty" value={summary.return_qty} format={formatNumber} alert="orange" delay={0.1} />
        <KPICard title="Return %" value={sales.return_pct} format={pct} alert="orange" delay={0.2} />
        <KPICard title="Sales Qty" value={sales.mtd_qty} format={formatNumber} delay={0.3} />
        <KPICard title="High Return SKUs" value={highSkus.length} format={formatNumber} alert="red" delay={0.4} />
        <KPICard title="Top SKU" value={topSku} alert="red" delay={0.5} />
      </section>

      <section className="grid min-w-0 items-start gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        {trendRows.length ? <SalesTrendLine data={trendRows} title="Daily returns trend" /> : <EmptyState title="No returns trend" />}
        {channelRows.length ? <CategoryDonut data={channelRows} title="Returns by channel" valueLabel="Revenue" /> : <EmptyState title="No return channel data" />}
      </section>

      <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm font-semibold text-ink">High return styles</div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Returns <b className="text-ink">{exactINR(summary.return_value)}</b></span>
            <span className="rounded border border-line bg-slate-50 px-2 py-1 text-muted">Qty <b className="text-ink">{formatNumber(summary.return_qty)}</b></span>
          </div>
        </div>
        <DataTable
          rows={highSkus.slice(0, 100)}
          rowKey={(row) => row.style_color}
          empty={<EmptyState title="No return SKUs" />}
          minWidth="1040px"
          columns={[
            { key: "style_color", label: "Style", sortable: true, copy: true },
            { key: "sales_qty", label: "Sales Qty", sortable: true, align: "right", render: (row) => formatNumber(row.sales_qty || 0) },
            { key: "return_qty", label: "Return Qty", sortable: true, align: "right", render: (row) => formatNumber(row.return_qty) },
            { key: "return_pct", label: "Return %", sortable: true, align: "right", render: (row) => pct(Number(row.return_pct || 0)) },
            { key: "inventory", label: "Inventory", sortable: true, align: "right", render: (row) => formatNumber(row.inventory || 0) },
            { key: "sale_grade", label: "Sale Grade", sortable: true, render: (row) => row.sale_grade || "Unknown" },
            {
              key: "share",
              label: "Share",
              sortable: true,
              align: "right",
              render: (row) => pct(Number(row.share || 0)),
            },
          ]}
        />
      </MotionPanel>
    </div>
  );
}
