"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, CheckCircle2, Download } from "lucide-react";
import toast from "react-hot-toast";

import { CategoryDonut } from "@/components/charts/CategoryDonut";
import { ReplenishmentBarChart } from "@/components/charts/ReplenishmentCharts";
import { Badge, priorityTone, statusTone } from "@/components/ui/Badge";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { KPICard } from "@/components/ui/KPICard";
import { MotionPanel } from "@/components/ui/PageTransition";
import { CardSkeleton } from "@/components/ui/Skeleton";
import {
  apiDownloadUrl,
  emptyInventoryKpis,
  emptyReplenishmentPlan,
  type InventoryCategoryStyle,
  type InventoryKpis,
  type InventoryStyle,
  type MatrixRow,
  type Paginated,
  type ReplenishmentPlan,
  type ReplenishmentPlanItem,
  type ReplenishmentSizeRow,
} from "@/lib/api";
import { resolveDateRange, withDateRange } from "@/lib/dateRange";
import { formatDate, formatINR, formatNumber, formatQty, pct } from "@/lib/formatters";
import { inventoryHealthTotals } from "@/lib/inventoryHealth";
import { useApiData } from "@/lib/useApiData";

function urgencyRank(urgency?: string) {
  if (urgency?.startsWith("P0")) return 0;
  if (urgency?.startsWith("P1")) return 1;
  if (urgency?.startsWith("P2")) return 2;
  if (urgency === "Covered") return 3;
  if (urgency === "Monitor") return 4;
  if (urgency === "No Replenishment") return 8;
  return 9;
}

function formatDoi(value?: number) {
  return Number(value || 0) >= 999 ? "Inf" : formatNumber(Number(value || 0));
}

function urgencyTone(urgency?: string) {
  if (urgency?.startsWith("P0")) return "red";
  if (urgency?.startsWith("P1")) return "amber";
  if (urgency?.startsWith("P2")) return "blue";
  if (urgency === "Covered") return "green";
  return "neutral";
}

function actionTone(action?: string) {
  if (action === "Auto") return "green";
  if (action === "Review") return "amber";
  if (action === "Hold") return "red";
  return "neutral";
}

function safeDate(value?: string | null) {
  return value ? formatDate(value) : "--";
}

function SizeSplit({ rows }: { rows?: ReplenishmentSizeRow[] }) {
  const values = rows ?? [];
  if (!values.length) return <span className="text-muted">--</span>;
  return (
    <div className="flex max-w-[260px] flex-wrap justify-end gap-1">
      {values.slice(0, 5).map((row) => (
        <span className="rounded border border-line bg-slate-50 px-2 py-1 text-[11px] font-medium text-ink" key={row.size}>
          {row.size} {formatNumber(row.recommended_qty)}
        </span>
      ))}
      {values.length > 5 ? <span className="rounded border border-line bg-slate-50 px-2 py-1 text-[11px] text-muted">+{values.length - 5}</span> : null}
    </div>
  );
}

type Tone = "darkGreen" | "lightGreen" | "neutral" | "yellow" | "lightRed" | "red";

const toneClass: Record<Tone, string> = {
  darkGreen: "border-emerald-300 bg-emerald-100 text-emerald-900",
  lightGreen: "border-lime-200 bg-lime-50 text-lime-800",
  neutral: "border-slate-200 bg-slate-50 text-slate-700",
  yellow: "border-yellow-200 bg-yellow-50 text-yellow-800",
  lightRed: "border-orange-200 bg-orange-50 text-orange-800",
  red: "border-rose-200 bg-rose-50 text-rose-800",
};

function metricBand(value: string, tone: Tone) {
  return <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${toneClass[tone]}`}>{value}</span>;
}

function salesQtyMix(qty: number, mixPct: number) {
  return `${formatNumber(qty || 0)} (${pct(mixPct || 0)})`;
}

function salesTone(value: number, maxSales: number): Tone {
  if (value <= 0) return "neutral";
  const share = value / Math.max(maxSales, 1);
  if (share >= 0.45) return "darkGreen";
  if (share >= 0.25) return "lightGreen";
  if (share >= 0.1) return "neutral";
  if (share >= 0.04) return "yellow";
  return "lightRed";
}

function returnTone(value: number): Tone {
  if (value <= 10) return "darkGreen";
  if (value <= 20) return "lightGreen";
  if (value <= 30) return "neutral";
  if (value <= 40) return "yellow";
  if (value <= 55) return "lightRed";
  return "red";
}

function instockTone(value: number): Tone {
  if (value >= 85) return "darkGreen";
  if (value >= 70) return "lightGreen";
  if (value >= 50) return "neutral";
  if (value >= 30) return "yellow";
  if (value > 0) return "lightRed";
  return "red";
}

function brokenTone(value: number): Tone {
  if (value <= 5) return "darkGreen";
  if (value <= 15) return "lightGreen";
  if (value <= 30) return "neutral";
  if (value <= 45) return "yellow";
  if (value <= 60) return "lightRed";
  return "red";
}

function oosTone(value: number): Tone {
  if (value <= 0) return "darkGreen";
  if (value <= 5) return "lightGreen";
  if (value <= 10) return "neutral";
  if (value <= 20) return "yellow";
  if (value <= 35) return "lightRed";
  return "red";
}

function categoryTone(row: MatrixRow, maxSales: number): Tone {
  if (row.category === "Grand Total") return "neutral";
  const salesShare = Number(row.sales_value || 0) / Math.max(maxSales, 1);
  if (row.oos_pct >= 35 || row.return_pct > 55) return "red";
  if (row.oos_pct >= 20 || row.return_pct > 40) return "lightRed";
  if (row.instock_pct >= 85 && row.return_pct <= 10 && salesShare >= 0.25) return "darkGreen";
  if (row.instock_pct >= 70 && row.return_pct <= 20 && salesShare >= 0.1) return "lightGreen";
  if (row.instock_pct >= 50 && row.oos_pct <= 10 && row.return_pct <= 30) return "neutral";
  return "yellow";
}

function matrixRowClass(row: MatrixRow, maxSales: number) {
  if (row.category === "Grand Total") return "bg-slate-100 font-semibold";
  const tone = categoryTone(row, maxSales);
  if (tone === "darkGreen") return "bg-emerald-50/80";
  if (tone === "lightGreen") return "bg-lime-50/70";
  if (tone === "yellow") return "bg-yellow-50/60";
  if (tone === "lightRed") return "bg-orange-50/60";
  if (tone === "red") return "bg-rose-50/60";
  return "";
}

function InventoryPageContent() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [grade, setGrade] = useState("");
  const [urgency, setUrgency] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const dateRange = useMemo(() => {
    const params: Record<string, string> = {};
    searchParams.forEach((value, key) => {
      params[key] = value;
    });
    return resolveDateRange(params);
  }, [searchParams]);
  const matrixPath = useMemo(() => withDateRange("/inventory/category_status_matrix", dateRange), [dateRange]);
  const matrixDownloadPath = useMemo(() => withDateRange("/inventory/category_status_matrix/download", dateRange), [dateRange]);
  const drilldownPath = useMemo(() => {
    if (!selectedCategory) return null;
    return withDateRange(`/inventory/category_styles?category=${encodeURIComponent(selectedCategory)}&limit=500`, dateRange);
  }, [dateRange, selectedCategory]);
  const kpis = useApiData<InventoryKpis>("/inventory/kpis", emptyInventoryKpis);
  const styles = useApiData<Paginated<InventoryStyle>>("/inventory/styles?limit=200", { items: [], page: 1, limit: 200, total: 0 });
  const replenishmentPlan = useApiData<ReplenishmentPlan>("/inventory/replenishment_plan?limit=200", emptyReplenishmentPlan);
  const matrix = useApiData<MatrixRow[]>(matrixPath, []);
  const drilldown = useApiData<Paginated<InventoryCategoryStyle>>(drilldownPath, { items: [], page: 1, limit: 500, total: 0 });
  const error = kpis.error || styles.error || replenishmentPlan.error || matrix.error || (selectedCategory ? drilldown.error : null);
  const retry = () => {
    kpis.retry();
    styles.retry();
    replenishmentPlan.retry();
    matrix.retry();
    if (selectedCategory) drilldown.retry();
  };

  const filteredPlan = useMemo(() => {
    return replenishmentPlan.data.items
      .filter((row) => !search || row.style_color.toLowerCase().includes(search.toLowerCase()))
      .filter((row) => !status || (row.status || row.inventory_status) === status)
      .filter((row) => !grade || (row.category_new || "Unknown") === grade)
      .filter((row) => !urgency || String(row.urgency || "").startsWith(urgency))
      .sort((a, b) => urgencyRank(a.urgency) - urgencyRank(b.urgency));
  }, [grade, replenishmentPlan.data.items, search, status, urgency]);

  const urgentRows = replenishmentPlan.data.items.filter((row) => row.urgency?.startsWith("P0") || row.urgency?.startsWith("P1")).slice(0, 6);
  const categories = Array.from(new Set(replenishmentPlan.data.items.map((row) => row.category_new || "Unknown"))).sort();
  const loading = kpis.loading || styles.loading || replenishmentPlan.loading || matrix.loading;
  const drilldownRows = selectedCategory ? drilldown.data.items : [];
  const healthInventory = inventoryHealthTotals(matrix.data);
  const maxMatrixSales = Math.max(...matrix.data.filter((row) => row.category !== "Grand Total").map((row) => Number(row.sales_value || 0)), 1);

  if (error) return <ErrorState message={error} onRetry={retry} />;

  return (
    <div className="w-full space-y-6">
      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        {loading ? (
          Array.from({ length: 6 }).map((_, index) => <CardSkeleton key={index} />)
        ) : (
          <>
            <KPICard title="Total Inventory" value={kpis.data.total_inventory} format={formatQty} delay={0} />
            <KPICard title="Total Styles" value={kpis.data.total_styles} format={formatNumber} delay={0.1} />
            <KPICard title="Instock Styles" value={kpis.data.instock_count} format={formatNumber} delay={0.2} />
            <KPICard title="Broken Styles" value={kpis.data.broken_count} format={formatNumber} alert="orange" delay={0.3} />
            <KPICard title="OOS Styles" value={kpis.data.oos_count} format={formatNumber} alert="red" delay={0.4} />
            <KPICard title="Low Stock Alerts" value={kpis.data.low_stock_alerts} format={formatNumber} alert="orange" delay={0.5} />
          </>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        {loading ? (
          Array.from({ length: 6 }).map((_, index) => <CardSkeleton key={`plan-${index}`} />)
        ) : (
          <>
            <KPICard title="Hybrid Reco Qty" value={replenishmentPlan.data.summary.recommended_qty} format={formatQty} alert="green" delay={0} />
            <KPICard title="Eligible Styles" value={replenishmentPlan.data.summary.eligible_styles} format={formatNumber} alert="green" delay={0.1} />
            <KPICard title="No Replenishment" value={replenishmentPlan.data.summary.no_replenishment_styles} format={formatNumber} delay={0.2} />
            <KPICard title="Urgent Styles" value={replenishmentPlan.data.summary.urgent_styles} format={formatNumber} alert="red" delay={0.3} />
            <KPICard title="Already Given" value={replenishmentPlan.data.summary.already_planned_styles} format={formatNumber} alert="green" delay={0.3} />
            <KPICard title="Manual Pending Qty" value={replenishmentPlan.data.summary.manual_pending_qty} format={formatQty} alert="green" delay={0.4} />
          </>
        )}
      </section>

      <section className="grid min-w-0 gap-4 xl:grid-cols-4">
        <ReplenishmentBarChart title="Urgency quantity" data={replenishmentPlan.data.charts.urgency} barColor="#dc2626" />
        <ReplenishmentBarChart title="Category quantity" data={replenishmentPlan.data.charts.category} barColor="#2563eb" />
        <ReplenishmentBarChart title="Manual vs new" data={replenishmentPlan.data.charts.manual_vs_new} barColor="#0f9488" />
        <ReplenishmentBarChart title="Size quantity" data={replenishmentPlan.data.charts.size} barColor="#d97706" />
      </section>

      {urgentRows.length ? (
        <MotionPanel className="rounded-lg border border-danger/20 bg-danger/5 p-4 shadow-soft">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
            <AlertTriangle className="h-4 w-4 text-danger" />
            Urgent replenishment alerts
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {urgentRows.map((row) => (
              <div className="rounded border border-danger/20 bg-white px-3 py-3 text-sm" key={row.style_color}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-ink">{row.style_color}</div>
                    <div className="mt-1 text-xs text-muted">{row.category_new || "Unknown"} | {row.inventory_status || row.status || "UNKNOWN"}</div>
                  </div>
                  <Badge tone={urgencyTone(row.urgency)}>{row.urgency}</Badge>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  <span className="rounded bg-slate-50 px-2 py-1 text-muted">Stock <b className="text-ink">{formatNumber(row.total_inventory || 0)}</b></span>
                  <span className="rounded bg-slate-50 px-2 py-1 text-muted">Reco <b className="text-ink">{formatNumber(row.recommended_replenishment_qty || 0)}</b></span>
                  <span className="rounded bg-slate-50 px-2 py-1 text-muted">By <b className="text-ink">{safeDate(row.order_by_date)}</b></span>
                </div>
              </div>
            ))}
          </div>
        </MotionPanel>
      ) : null}

      <section className="grid min-w-0 items-start gap-4 xl:grid-cols-[1fr_2fr]">
        <CategoryDonut
          title="Inventory health"
          valueLabel="Styles"
          data={[
            { name: "Instock", value: kpis.data.instock_count, qty: healthInventory.instock },
            { name: "Broken", value: kpis.data.broken_count, qty: healthInventory.broken },
            { name: "OOS", value: kpis.data.oos_count, qty: healthInventory.oos },
          ]}
        />
        <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-ink">Hybrid replenishment plan</div>
            <a className="inline-flex items-center gap-2 rounded bg-ink px-4 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02]" href={apiDownloadUrl("/inventory/download_replenishment")} onClick={() => toast.success("Downloading replenishment CSV")}>
              <Download className="h-4 w-4" />
              Download Replenishment CSV
            </a>
          </div>
          <div className="mb-4 grid gap-3 md:grid-cols-4">
            <input className="rounded border border-line px-3 py-2 text-sm" onChange={(event) => setSearch(event.target.value)} placeholder="Search style" value={search} />
            <select className="rounded border border-line px-3 py-2 text-sm" onChange={(event) => setStatus(event.target.value)} value={status}>
              <option value="">All statuses</option>
              <option value="INSTOCK">INSTOCK</option>
              <option value="BROKEN">BROKEN</option>
              <option value="OOS">OOS</option>
            </select>
            <select className="rounded border border-line px-3 py-2 text-sm" onChange={(event) => setGrade(event.target.value)} value={grade}>
              <option value="">All grades</option>
              {categories.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
            <select className="rounded border border-line px-3 py-2 text-sm" onChange={(event) => setUrgency(event.target.value)} value={urgency}>
              <option value="">All urgency</option>
              <option value="P0">P0</option>
              <option value="P1">P1</option>
              <option value="P2">P2</option>
              <option value="Covered">Covered</option>
              <option value="Monitor">Monitor</option>
              <option value="No Replenishment">No Replenishment</option>
            </select>
          </div>
          <DataTable
            rows={filteredPlan}
            rowKey={(row) => row.style_color}
            empty={<EmptyState title="No replenishment rows" />}
            minWidth="1740px"
            rowClassName={(row: ReplenishmentPlanItem) => {
              if (row.urgency?.startsWith("P0")) return "bg-red-50/80";
              if (row.urgency?.startsWith("P1")) return "bg-amber-50/70";
              if (row.already_planned) return "bg-blue-50/70";
              if (row.action === "No Replenishment") return "bg-slate-50/70";
              return "";
            }}
            columns={[
              { key: "style_color", label: "Style", sortable: true, copy: true },
              { key: "urgency", label: "Urgency", sortable: true, render: (row) => <Badge tone={urgencyTone(row.urgency)}>{row.urgency || "Monitor"}</Badge> },
              { key: "replenishment_reason", label: "Reason", sortable: true, render: (row) => <span className="text-xs text-muted">{row.replenishment_reason || "--"}</span> },
              {
                key: "already_planned",
                label: "Given",
                sortable: true,
                render: (row) =>
                  row.already_planned ? (
                    <Badge tone="blue"><CheckCircle2 className="h-3.5 w-3.5" /> {formatNumber(row.pending_replenishment_qty || 0)}</Badge>
                  ) : (
                    <span className="text-muted">--</span>
                  ),
              },
              { key: "category_new", label: "Category", sortable: true, render: (row) => row.category_new || "Unknown" },
              { key: "inventory_status", label: "Status", sortable: true, render: (row) => <Badge tone={statusTone(row.inventory_status || row.status)}>{row.inventory_status || row.status || "UNKNOWN"}</Badge> },
              { key: "action", label: "Action", sortable: true, render: (row) => <Badge tone={actionTone(row.action)}>{row.action || "Review"}</Badge> },
              { key: "predicted_ros", label: "Pred ROS", sortable: true, align: "right", render: (row) => Number(row.predicted_ros || 0).toFixed(2) },
              { key: "ros_30d", label: "ROS", sortable: true, align: "right" },
              { key: "sales_qty_90d", label: "90D Qty", sortable: true, align: "right", render: (row) => formatNumber(row.sales_qty_90d || 0) },
              { key: "total_inventory", label: "Stock", sortable: true, align: "right", render: (row) => formatNumber(row.total_inventory || 0) },
              { key: "doi", label: "DOI", sortable: true, align: "right", render: (row) => formatDoi(row.doi) },
              { key: "target_stock", label: "Target", sortable: true, align: "right", render: (row) => formatNumber(row.target_stock || 0) },
              { key: "recommended_replenishment_qty", label: "Reco Qty", sortable: true, align: "right", render: (row) => formatNumber(row.recommended_replenishment_qty || 0) },
              { key: "size_replenishment", label: "Size Split", align: "right", render: (row) => <SizeSplit rows={row.size_replenishment} /> },
              { key: "order_by_date", label: "Order By", sortable: true, render: (row) => safeDate(row.order_by_date) },
            ]}
          />
        </MotionPanel>
      </section>

      <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm font-semibold text-ink">Category x status matrix</div>
          <a className="inline-flex items-center gap-2 rounded border border-line bg-white px-4 py-2 text-sm font-medium text-ink transition duration-200 ease-in-out hover:bg-slate-50" href={apiDownloadUrl(matrixDownloadPath)} onClick={() => toast.success("Downloading category matrix Excel")}>
            <Download className="h-4 w-4" />
            Download Excel
          </a>
        </div>
        <DataTable
          rows={matrix.data}
          rowKey={(row) => row.category}
          empty={<EmptyState title="No category status matrix" />}
          maxHeight="620px"
          minWidth="2100px"
          rowClassName={(row) => `${matrixRowClass(row, maxMatrixSales)} cursor-pointer ${selectedCategory === row.category ? "ring-2 ring-inset ring-teal/40" : ""}`}
          onRowDoubleClick={(row) => {
            setSelectedCategory(row.category);
            toast.success(`Showing styles under ${row.category}`);
          }}
          columns={[
            { key: "category", label: "Category", sortable: true, render: (row) => metricBand(row.category, categoryTone(row, maxMatrixSales)) },
            { key: "sales_value", label: "Sales Value", sortable: true, align: "right", render: (row) => metricBand(formatINR(Number(row.sales_value || 0)), salesTone(Number(row.sales_value || 0), maxMatrixSales)) },
            { key: "sales_qty", label: "Sale Qty", sortable: true, align: "right", render: (row) => formatNumber(row.sales_qty || 0) },
            { key: "return_pct", label: "Return %", sortable: true, align: "right", render: (row) => metricBand(pct(Number(row.return_pct || 0)), returnTone(Number(row.return_pct || 0))) },
            { key: "broken_styles", label: "Broken Styles", sortable: true, align: "right" },
            { key: "broken_pct", label: "Broken %", sortable: true, align: "right", render: (row) => metricBand(pct(row.broken_pct), brokenTone(row.broken_pct)) },
            { key: "broken_inventory", label: "Broken Inv", sortable: true, align: "right", render: (row) => formatNumber(row.broken_inventory) },
            { key: "broken_sales_qty", label: "Broken Sale Qty", sortable: true, align: "right", render: (row) => salesQtyMix(row.broken_sales_qty, row.broken_sales_mix_pct) },
            { key: "broken_return_pct", label: "Broken Return %", sortable: true, align: "right", render: (row) => metricBand(pct(row.broken_return_pct), returnTone(row.broken_return_pct)) },
            { key: "instock_styles", label: "Instock Styles", sortable: true, align: "right" },
            { key: "instock_pct", label: "Instock %", sortable: true, align: "right", render: (row) => metricBand(pct(row.instock_pct), instockTone(row.instock_pct)) },
            { key: "instock_inventory", label: "Instock Inv", sortable: true, align: "right", render: (row) => formatNumber(row.instock_inventory) },
            { key: "instock_sales_qty", label: "Instock Sale Qty", sortable: true, align: "right", render: (row) => salesQtyMix(row.instock_sales_qty, row.instock_sales_mix_pct) },
            { key: "instock_return_pct", label: "Instock Return %", sortable: true, align: "right", render: (row) => metricBand(pct(row.instock_return_pct), returnTone(row.instock_return_pct)) },
            { key: "oos_styles", label: "OOS Styles", sortable: true, align: "right" },
            { key: "oos_pct", label: "OOS %", sortable: true, align: "right", render: (row) => metricBand(pct(row.oos_pct), oosTone(row.oos_pct)) },
            { key: "oos_inventory", label: "OOS Inv", sortable: true, align: "right", render: (row) => formatNumber(row.oos_inventory) },
            { key: "oos_sales_qty", label: "OOS Sale Qty", sortable: true, align: "right", render: (row) => salesQtyMix(row.oos_sales_qty, row.oos_sales_mix_pct) },
            { key: "oos_return_pct", label: "OOS Return %", sortable: true, align: "right", render: (row) => metricBand(pct(row.oos_return_pct), returnTone(row.oos_return_pct)) },
            { key: "total_styles", label: "Total Styles", sortable: true, align: "right" },
            { key: "total_inventory", label: "Total Inv", sortable: true, align: "right", render: (row) => formatNumber(row.total_inventory) },
          ]}
        />
      </MotionPanel>

      <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-ink">Category style drilldown</div>
            <div className="text-xs text-muted">{selectedCategory ? `Showing ${selectedCategory} styles` : "Double click a category row above to view style-level details."}</div>
          </div>
          {selectedCategory ? (
            <button className="rounded border border-line px-3 py-2 text-xs font-medium text-muted transition duration-200 ease-in-out hover:bg-slate-50 hover:text-ink" onClick={() => setSelectedCategory(null)} type="button">
              Clear
            </button>
          ) : null}
        </div>
        <DataTable
          rows={drilldownRows}
          rowKey={(row) => row.style_color}
          empty={<EmptyState title={selectedCategory ? "No styles found" : "No category selected"} />}
          maxHeight="520px"
          minWidth="1280px"
          columns={[
            { key: "style_color", label: "Style", sortable: true, copy: true },
            { key: "category_new", label: "Category", sortable: true },
            { key: "status", label: "Status", sortable: true, render: (row) => <Badge tone={statusTone(row.status)}>{row.status || "UNKNOWN"}</Badge> },
            { key: "total_inventory", label: "Stock", sortable: true, align: "right", render: (row) => formatNumber(row.total_inventory || 0) },
            { key: "ros_30d", label: "ROS 30D", sortable: true, align: "right" },
            { key: "doi", label: "DOI", sortable: true, align: "right", render: (row) => formatDoi(row.doi) },
            { key: "priority", label: "Priority", sortable: true, render: (row) => <Badge tone={priorityTone(row.priority)}>{row.priority || "Monitor"}</Badge> },
            { key: "sales_value", label: "Sales Value", sortable: true, align: "right", render: (row) => formatINR(row.sales_value || 0) },
            { key: "sales_qty", label: "Sale Qty", sortable: true, align: "right", render: (row) => formatNumber(row.sales_qty || 0) },
            { key: "return_qty", label: "Return Qty", sortable: true, align: "right", render: (row) => formatNumber(row.return_qty || 0) },
            { key: "return_pct", label: "Return %", sortable: true, align: "right", render: (row) => metricBand(pct(row.return_pct || 0), returnTone(row.return_pct || 0)) },
          ]}
        />
      </MotionPanel>
    </div>
  );
}

export default function InventoryPage() {
  return (
    <Suspense fallback={<div className="w-full space-y-6"><CardSkeleton /></div>}>
      <InventoryPageContent />
    </Suspense>
  );
}
