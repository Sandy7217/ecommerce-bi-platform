"use client";

import { useMemo } from "react";

import { ChannelBar } from "@/components/charts/ChannelBar";
import { CategoryDonut } from "@/components/charts/CategoryDonut";
import { Badge } from "@/components/ui/Badge";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { KPICard } from "@/components/ui/KPICard";
import { MotionPanel } from "@/components/ui/PageTransition";
import { type DateRangeValue, withDateRange } from "@/lib/dateRange";
import { exactINR, formatINR, formatNumber } from "@/lib/formatters";
import { useApiData } from "@/lib/useApiData";

type PlaRow = {
  style_color: string;
  campaign_name?: string;
  campaign_id?: string;
  channel?: string;
  impressions?: number;
  clicks?: number;
  ctr?: number;
  cvr?: number;
  spend?: number;
  revenue?: number;
  roi?: number;
  units_direct?: number;
  units_indirect?: number;
  problem?: string;
};

function problemTone(problem?: string) {
  const value = String(problem || "").toLowerCase();
  if (value.includes("healthy")) return "green";
  if (value.includes("low")) return "amber";
  if (value.includes("leakage")) return "red";
  return "neutral";
}

export function AdsClient({ dateRange }: { dateRange: DateRangeValue }) {
  const pla = useApiData<PlaRow[]>(withDateRange("/ads/pla", dateRange), []);
  const problemSkus = useApiData<PlaRow[]>(withDateRange("/ads/problem_skus", dateRange), []);
  const error = pla.error || problemSkus.error;

  const totals = useMemo(() => {
    const rows = pla.data;
    const spend = rows.reduce((sum, row) => sum + Number(row.spend || 0), 0);
    const revenue = rows.reduce((sum, row) => sum + Number(row.revenue || 0), 0);
    const impressions = rows.reduce((sum, row) => sum + Number(row.impressions || 0), 0);
    const clicks = rows.reduce((sum, row) => sum + Number(row.clicks || 0), 0);
    const units = rows.reduce((sum, row) => sum + Number(row.units_direct || 0) + Number(row.units_indirect || 0), 0);
    return { spend, revenue, impressions, clicks, units, roi: spend ? revenue / spend : 0 };
  }, [pla.data]);

  const problemCounts = useMemo(() => {
    const grouped = new Map<string, number>();
    problemSkus.data.forEach((row) => grouped.set(row.problem || "Unknown", (grouped.get(row.problem || "Unknown") || 0) + 1));
    return Array.from(grouped.entries()).map(([name, value]) => ({ name, value }));
  }, [problemSkus.data]);

  const styleRows = useMemo(() => {
    const grouped = new Map<string, { name: string; value: number; qty: number }>();
    pla.data.forEach((row) => {
      const style = row.style_color || "Unknown";
      const current = grouped.get(style) || { name: style, value: 0, qty: 0 };
      current.value += Number(row.revenue || 0);
      current.qty += Number(row.units_direct || 0) + Number(row.units_indirect || 0);
      grouped.set(style, current);
    });
    return Array.from(grouped.values()).sort((a, b) => b.value - a.value).slice(0, 8);
  }, [pla.data]);

  const topRows = [...problemSkus.data]
    .sort((a, b) => Number(b.spend || 0) - Number(a.spend || 0))
    .slice(0, 100);

  if (error) return <ErrorState message={error} onRetry={() => { pla.retry(); problemSkus.retry(); }} />;

  return (
    <div className="w-full space-y-6">
      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <KPICard title="PLA Spend" value={totals.spend} format={formatINR} delay={0} />
        <KPICard title="PLA Revenue" value={totals.revenue} format={formatINR} delay={0.1} />
        <KPICard title="ROI" value={totals.roi} format={(value) => `${value.toFixed(1)}x`} delay={0.2} />
        <KPICard title="Impressions" value={totals.impressions} format={formatNumber} delay={0.3} />
        <KPICard title="Clicks" value={totals.clicks} format={formatNumber} delay={0.4} />
        <KPICard title="Units" value={totals.units} format={formatNumber} delay={0.5} />
      </section>

      <section className="grid min-w-0 items-start gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        {styleRows.length ? <ChannelBar data={styleRows} title="Top PLA revenue styles" /> : <EmptyState title="No PLA revenue" />}
        {problemCounts.length ? <CategoryDonut data={problemCounts} title="Ad issue classifier" valueLabel="SKUs" /> : <EmptyState title="No ad issue data" />}
      </section>

      <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="mb-4 text-sm font-semibold text-ink">PLA performance by style</div>
        <DataTable
          rows={topRows}
          rowKey={(row, index) => `${row.style_color}-${row.campaign_id || index}`}
          empty={<EmptyState title="No PLA rows" />}
          minWidth="1180px"
          columns={[
            { key: "style_color", label: "Style", sortable: true, copy: true },
            { key: "campaign_name", label: "Campaign", sortable: true },
            { key: "channel", label: "Channel", sortable: true },
            { key: "spend", label: "Spend", sortable: true, align: "right", render: (row) => exactINR(Number(row.spend || 0)) },
            { key: "revenue", label: "Revenue", sortable: true, align: "right", render: (row) => exactINR(Number(row.revenue || 0)) },
            { key: "roi", label: "ROI", sortable: true, align: "right", render: (row) => `${Number(row.roi || 0).toFixed(2)}x` },
            { key: "ctr", label: "CTR", sortable: true, align: "right", render: (row) => `${Number(row.ctr || 0).toFixed(2)}%` },
            { key: "cvr", label: "CVR", sortable: true, align: "right", render: (row) => `${Number(row.cvr || 0).toFixed(2)}%` },
            { key: "problem", label: "Classifier", sortable: true, render: (row) => <Badge tone={problemTone(row.problem)}>{row.problem || "Unknown"}</Badge> },
          ]}
        />
      </MotionPanel>
    </div>
  );
}
