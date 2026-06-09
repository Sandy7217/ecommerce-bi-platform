"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { CategoryDonut } from "@/components/charts/CategoryDonut";
import { IndiaMap } from "@/components/charts/IndiaMap";
import { MarketplaceSalesReturns } from "@/components/charts/MarketplaceSalesReturns";
import { ChannelTrendChart, ForecastChart, SalesReturnsChart } from "@/components/charts/MultiLineChart";
import { SalesTrendLine } from "@/components/charts/SalesTrendLine";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { KPICard } from "@/components/ui/KPICard";
import { MotionPanel } from "@/components/ui/PageTransition";
import type { CategoryMix, ChannelTrendPoint, MarketplaceSummary, RegionalHeatmapState, SalesKpis, SalesReturnsForecast, TopProduct, TrendPoint } from "@/lib/api";
import { exactINR, formatINR, formatNumber, formatQty, pct } from "@/lib/formatters";

type SalesClientProps = {
  kpis: SalesKpis;
  trend: TrendPoint[];
  returns: TrendPoint[];
  channelTrend: ChannelTrendPoint[];
  marketplaceSummary: MarketplaceSummary[];
  topProducts: TopProduct[];
  categories: CategoryMix[];
  states: RegionalHeatmapState[];
  forecast: SalesReturnsForecast;
};

export function SalesClient({ kpis, trend, returns, channelTrend, marketplaceSummary, topProducts, categories, states, forecast }: SalesClientProps) {
  const channelTotals = Array.from(
    channelTrend.reduce((map, row) => {
      const item = map.get(row.channel) ?? { name: row.channel, value: 0, qty: 0 };
      item.value += row.sales_value;
      item.qty += row.qty;
      map.set(row.channel, item);
      return map;
    }, new Map<string, { name: string; value: number; qty: number }>())
  ).map((entry) => entry[1]);
  const categoryRevenue = categories.map((row) => ({ name: row.category || row.name || "Unknown", value: Number(row.sales_value ?? row.value ?? 0), qty: row.qty, styles: row.sku_count }));

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <KPICard title="Sales" value={kpis.mtd_sales} format={formatINR} trend={kpis.sales_growth_pct} delay={0} />
        <KPICard title="Qty" value={kpis.mtd_qty} format={formatQty} trend={kpis.qty_growth_pct} delay={0.1} />
        <KPICard title="Yesterday Sales" value={kpis.yesterday_sales} format={formatINR} delay={0.2} />
        <KPICard title="Yesterday Qty" value={kpis.yesterday_qty} format={formatQty} delay={0.3} />
        <KPICard title="ASP" value={kpis.asp} format={formatINR} delay={0.4} />
        <KPICard title="Return %" value={kpis.return_pct} format={pct} trend={kpis.return_pct_change} trendDirection="lower-is-good" trendUnit="pp" alert="orange" delay={0.5} />
      </section>

      <section className="grid items-start gap-4 xl:grid-cols-[0.8fr_1.2fr]">
        {trend.length ? <SalesTrendLine data={trend.map((row) => ({ date: row.date, sales_value: row.sales_value || 0, qty: row.qty }))} /> : <EmptyState title="No sales trend" />}
        {trend.length || returns.length ? (
          <SalesReturnsChart sales={trend.map((row) => ({ date: row.date, sales_value: row.sales_value || 0 }))} returns={returns.map((row) => ({ date: row.date, return_value: row.return_value || 0 }))} />
        ) : (
          <EmptyState title="No sales or returns trend" />
        )}
      </section>

      <section className="grid items-start gap-4 xl:grid-cols-[1fr_1fr]">
        {channelTrend.length ? <ChannelTrendChart data={channelTrend} /> : <EmptyState title="No channel trend" />}
        {channelTotals.length ? <CategoryDonut data={channelTotals} title="Revenue by channel" valueLabel="Revenue" /> : <EmptyState title="No channel revenue" />}
      </section>

      {marketplaceSummary.length ? <MarketplaceSalesReturns data={marketplaceSummary} /> : <EmptyState title="No marketplace sales and returns" />}

      {forecast.forecast.length ? <ForecastChart forecast={forecast} /> : <EmptyState title="No forecast data" />}

      <section className="grid items-start gap-4 xl:grid-cols-[1fr_1fr]">
        {categoryRevenue.length ? <CategoryDonut data={categoryRevenue} title="Revenue by category" valueLabel="Revenue" /> : <EmptyState title="No category revenue" />}
        {states.length ? <IndiaMap data={states} /> : <EmptyState title="No regional sales" />}
      </section>

      <MotionPanel className="rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="mb-4 text-sm font-semibold text-ink">Top 20 products</div>
        <DataTable
          rows={topProducts}
          rowKey={(row) => row.style_color}
          empty={<EmptyState title="No top products" />}
          columns={[
            { key: "style_color", label: "SKU", sortable: true, copy: true },
            { key: "revenue", label: "Revenue", sortable: true, align: "right", render: (row) => exactINR(row.revenue) },
            { key: "orders", label: "Orders", sortable: true, align: "right", render: (row) => formatNumber(row.orders) },
            { key: "ros", label: "ROS", sortable: true, align: "right" },
            {
              key: "growth_pct",
              label: "Growth %",
              sortable: true,
              align: "right",
              render: (row) => {
                const Icon = row.growth_pct >= 0 ? ArrowUpRight : ArrowDownRight;
                return (
                  <span className={`inline-flex items-center gap-1 ${row.growth_pct >= 0 ? "text-teal" : "text-danger"}`}>
                    <Icon className="h-4 w-4" />
                    {pct(Math.abs(row.growth_pct))}
                  </span>
                );
              },
            },
            { key: "return_pct", label: "Return %", sortable: true, align: "right", render: (row) => pct(row.return_pct) },
          ]}
        />
      </MotionPanel>
    </div>
  );
}
