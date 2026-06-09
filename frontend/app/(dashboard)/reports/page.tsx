"use client";

import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { AlertTriangle, CalendarDays, Download, Eye, FileSpreadsheet, Filter, Image as ImageIcon, Save, Search } from "lucide-react";

import { Badge, statusTone } from "@/components/ui/Badge";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { KPICard } from "@/components/ui/KPICard";
import { MotionPanel } from "@/components/ui/PageTransition";
import { API_ROOT } from "@/lib/api";
import { formatDateInput } from "@/lib/dateRange";
import { exactINR, formatDate, formatNumber, pct } from "@/lib/formatters";
import { useApiData } from "@/lib/useApiData";

type ReportType = "sales" | "inventory" | "replenishment" | "returns" | "category_analysis" | "anomaly_alerts";
type ReportFormat = "csv" | "excel";

type ReportCard = {
  type: ReportType;
  name: string;
  description: string;
  dateRange: boolean;
};

type PipelineStatus = {
  status: string;
  last_refresh?: string | null;
  uploads: { id?: number; filename?: string; upload_type?: string; rows_processed?: number; status?: string; created_at?: string }[];
};

type AnomalyAlert = {
  id: string;
  severity: "Critical" | "High" | "Medium" | "Monitor" | string;
  alert_type: string;
  scope: "Style" | "Category" | string;
  subject?: string | null;
  style_color?: string | null;
  category_subject?: string | null;
  category?: string | null;
  status?: string | null;
  inventory_status?: string | null;
  sales_delta_pct?: number | null;
  return_delta_pct?: number | null;
  return_pct_recent?: number | null;
  current_inventory?: number | null;
  expected_inventory?: number | null;
  inventory_delta_pct?: number | null;
  sku_count_delta_pct?: number | null;
  reason?: string | null;
  action?: string | null;
};

type AnomalySummary = {
  total: number;
  critical: number;
  high: number;
  medium: number;
  monitor: number;
  style_alerts: number;
  category_alerts: number;
  by_type: Record<string, number>;
};

type AnomalyResponse = {
  items: AnomalyAlert[];
  summary: AnomalySummary;
};

type TargetRow = {
  id?: number | null;
  month: string;
  channel: string;
  target_value: number;
  target_qty?: number | null;
};

type TargetResponse = {
  month: string;
  items: TargetRow[];
  setup_required?: boolean;
};

type DsrMetricRow = {
  platform: string;
  sale_qty: number;
  sale_value: number;
  asp: number;
  net_sale_qty: number;
  net_sale_value: number;
  net_asp: number;
  return_qty: number;
  return_value: number;
  return_pct_qty: number;
  return_pct_value: number;
};

type DsrPayload = {
  date: string;
  month: string;
  target: {
    target_value?: number | null;
    achieved_pct?: number | null;
    status: string;
  };
  daily: { rows: DsrMetricRow[]; total: DsrMetricRow };
  mtd: { rows: DsrMetricRow[]; total: DsrMetricRow };
};

type AnomalyFilters = {
  severity: string;
  alertType: string;
  category: string;
  status: string;
  scope: string;
  search: string;
};

const emptyAnomalies: AnomalyResponse = {
  items: [],
  summary: { total: 0, critical: 0, high: 0, medium: 0, monitor: 0, style_alerts: 0, category_alerts: 0, by_type: {} },
};

const reportCards: ReportCard[] = [
  {
    type: "sales",
    name: "MTD Sales Report",
    description: "Order-level sales extract with SKU, channel, marketplace, price, discount, quantity, order, and location fields.",
    dateRange: true,
  },
  {
    type: "inventory",
    name: "Inventory Report",
    description: "Current SKU master inventory, category, sale grade, status, ROS, DOI, and replenishment priority.",
    dateRange: false,
  },
  {
    type: "replenishment",
    name: "Replenishment Report",
    description: "P0 and P1 replenishment styles with recommended quantities from current stock and ROS.",
    dateRange: false,
  },
  {
    type: "returns",
    name: "Returns Report",
    description: "Return-level extract with SKU, channel, return quantity, value, reason/type, and state.",
    dateRange: true,
  },
  {
    type: "category_analysis",
    name: "Category Analysis Report",
    description: "Style-color category view with old sale grade, new category, stock status, inventory, ROS, and MTD sales.",
    dateRange: true,
  },
  {
    type: "anomaly_alerts",
    name: "Anomaly Alerts Report",
    description: "Style and category anomaly report covering sales spikes, return spikes, overstock risk, inventory depth, and SKU count movement.",
    dateRange: true,
  },
];

const alertTypeOptions = [
  "Sales + Return Spike",
  "Sales Spike",
  "Return Spike",
  "Overstock Risk",
  "Category Inventory Depth Increase",
  "Category Inventory Depth Decrease",
  "Category SKU Count Change",
];

function defaultReportRange() {
  const today = new Date();
  return {
    from: formatDateInput(new Date(today.getFullYear(), today.getMonth(), 1)),
    to: formatDateInput(today),
  };
}

function severityTone(severity?: string) {
  const normalized = String(severity || "").toLowerCase();
  if (normalized === "critical") return "red";
  if (normalized === "high") return "amber";
  if (normalized === "medium") return "blue";
  return "neutral";
}

function displaySubject(row: AnomalyAlert) {
  return row.style_color || row.category_subject || row.category || "Unknown";
}

function percentValue(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? pct(value) : "NA";
}

function numberValue(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? formatNumber(value) : "NA";
}

function defaultDsrDate() {
  return formatDateInput(new Date());
}

function monthLabel(value: string) {
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(new Date(`${value}-01T00:00:00`));
}

function achievedTone(status?: string) {
  if (status === "green") return "text-emerald-700";
  if (status === "orange") return "text-amber-700";
  if (status === "red") return "text-red-700";
  return "text-muted";
}

function metricCell(value: number, mode: "qty" | "money" | "pct" = "qty") {
  if (mode === "pct") return pct(Number(value || 0));
  if (mode === "money") return exactINR(Number(value || 0));
  return formatNumber(Number(value || 0));
}

function dsrDateLabel(value: string) {
  const parts = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "2-digit" }).formatToParts(new Date(`${value}T00:00:00`));
  return `${parts.find((part) => part.type === "day")?.value}-${parts.find((part) => part.type === "month")?.value}-${parts.find((part) => part.type === "year")?.value}`;
}

function dsrMonthLabel(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short" }).format(new Date(`${value}T00:00:00`)).toUpperCase();
}

function dsrTargetLabel(payload: DsrPayload) {
  return payload.target.target_value ? exactINR(Number(payload.target.target_value)) : "\u2014";
}

function dsrAchievedLabel(payload: DsrPayload) {
  return typeof payload.target.achieved_pct === "number" ? `Achieved ${pct(payload.target.achieved_pct)}` : "Achieved \u2014";
}

function achievedCellClass(status?: string) {
  if (status === "green") return "bg-[#00B050] text-white";
  if (status === "orange") return "bg-[#F4B183] text-ink";
  if (status === "red") return "bg-[#C00000] text-white";
  return "bg-[#1F3864] text-white";
}

export default function ReportsPage() {
  const pipeline = useApiData<PipelineStatus>("/admin/pipeline_status", { status: "unknown", last_refresh: null, uploads: [] });
  const initialRange = useMemo(() => defaultReportRange(), []);
  const [ranges, setRanges] = useState<Record<ReportType, { from: string; to: string }>>(
    Object.fromEntries(reportCards.map((report) => [report.type, initialRange])) as Record<ReportType, { from: string; to: string }>
  );
  const [lastGenerated, setLastGenerated] = useState<Record<ReportType, string>>({} as Record<ReportType, string>);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [filters, setFilters] = useState<AnomalyFilters>({ severity: "", alertType: "", category: "", status: "", scope: "", search: "" });
  const [dsrDate, setDsrDate] = useState(defaultDsrDate);
  const [targetAmount, setTargetAmount] = useState("50000000");
  const [targetSaving, setTargetSaving] = useState(false);
  const [dsrPreview, setDsrPreview] = useState<DsrPayload | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const anomalyRange = ranges.anomaly_alerts ?? initialRange;
  const targetMonth = dsrDate.slice(0, 7);
  const targetData = useApiData<TargetResponse>(`/targets?month=${targetMonth}`, { month: `${targetMonth}-01`, items: [] });
  const currentTarget = useMemo(() => targetData.data.items.find((row) => row.channel === "ALL") || targetData.data.items[0], [targetData.data.items]);
  const targetSummary = currentTarget ? `${monthLabel(targetMonth)} Target: ${exactINR(Number(currentTarget.target_value || 0))}` : `${monthLabel(targetMonth)} Target: Not Set`;
  const achievedSummary = dsrPreview?.target.achieved_pct;
  const previewSections = useMemo(() => {
    if (!dsrPreview) return [];
    return [
      { label: "DSR", summary: "Daily Sale & Return Summary", leftHeader: "Date", leftValue: dsrDateLabel(dsrPreview.date), rows: dsrPreview.daily.rows, total: dsrPreview.daily.total },
      { label: "MTD", summary: "Monthly Sale & Return Summary", leftHeader: "Month", leftValue: dsrMonthLabel(dsrPreview.date), rows: dsrPreview.mtd.rows, total: dsrPreview.mtd.total },
    ];
  }, [dsrPreview]);
  const anomalyQuery = useMemo(() => {
    const params = new URLSearchParams({
      from_date: anomalyRange.from,
      to_date: anomalyRange.to,
      limit: "500",
    });
    if (filters.severity) params.set("severity", filters.severity);
    if (filters.alertType) params.set("alert_type", filters.alertType);
    if (filters.category) params.set("category", filters.category);
    if (filters.status) params.set("status", filters.status);
    if (filters.scope) params.set("scope", filters.scope);
    if (filters.search.trim()) params.set("search", filters.search.trim());
    return `/alerts/anomalies?${params.toString()}`;
  }, [anomalyRange.from, anomalyRange.to, filters]);

  const anomalies = useApiData<AnomalyResponse>(anomalyQuery, emptyAnomalies);
  const categoryOptions = useMemo(() => {
    const values = new Set((anomalies.data.items || []).map((row) => row.category).filter(Boolean) as string[]);
    return [...values].sort((a, b) => a.localeCompare(b));
  }, [anomalies.data.items]);

  function updateRange(type: ReportType, key: "from" | "to", value: string) {
    setRanges((current) => ({
      ...current,
      [type]: { ...current[type], [key]: value },
    }));
  }

  function updateFilter(key: keyof AnomalyFilters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  useEffect(() => {
    if (currentTarget?.target_value) {
      setTargetAmount(String(currentTarget.target_value));
    }
  }, [currentTarget?.target_value]);

  async function saveTarget() {
    if (targetData.data.setup_required) {
      toast.error("Run the targets table migration before saving custom DSR targets.");
      return;
    }
    setTargetSaving(true);
    try {
      const response = await fetch(`${API_ROOT}/targets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ month: targetMonth, channel: "ALL", target_value: Number(targetAmount || 0), target_qty: 0 }),
      });
      if (!response.ok) throw new Error(await response.text());
      toast.success("DSR target saved");
      targetData.retry();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Target save failed");
    } finally {
      setTargetSaving(false);
    }
  }

  async function fetchDsrPreview() {
    setPreviewLoading(true);
    try {
      const response = await fetch(`${API_ROOT}/reports/dsr?date=${dsrDate}`);
      if (!response.ok) throw new Error(await response.text());
      setDsrPreview((await response.json()) as DsrPayload);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "DSR preview failed");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function downloadDsr(format: "excel" | "png") {
    const key = `dsr-${format}`;
    setDownloading(key);
    try {
      const response = await fetch(`${API_ROOT}/reports/dsr/download?date=${dsrDate}&format=${format}`);
      if (!response.ok) throw new Error(await response.text());
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") ?? "";
      const filename = disposition.match(/filename="?([^"]+)"?/)?.[1] ?? `dsr-report-${dsrDate}.${format === "png" ? "png" : "xlsx"}`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
      toast.success(format === "png" ? "DSR image downloaded" : "DSR Excel downloaded");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "DSR download failed");
    } finally {
      setDownloading(null);
    }
  }

  async function downloadReport(report: ReportCard, format: ReportFormat) {
    const key = `${report.type}-${format}`;
    const range = ranges[report.type] ?? initialRange;
    const params = new URLSearchParams({ type: report.type, format });
    if (report.dateRange) {
      params.set("from_date", range.from);
      params.set("to_date", range.to);
    }
    setDownloading(key);
    try {
      const response = await fetch(`${API_ROOT}/reports/download?${params.toString()}`);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") ?? "";
      const filename = disposition.match(/filename="?([^"]+)"?/)?.[1] ?? `${report.type}.${format === "csv" ? "csv" : "xlsx"}`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
      setLastGenerated((current) => ({ ...current, [report.type]: new Date().toISOString() }));
      toast.success(`${report.name} downloaded`);
    } catch (downloadError) {
      toast.error(downloadError instanceof Error ? downloadError.message : "Report download failed");
    } finally {
      setDownloading(null);
    }
  }

  async function downloadFilteredCsv() {
    setDownloading("anomaly-filtered-csv");
    try {
      const params = new URLSearchParams({
        from_date: anomalyRange.from,
        to_date: anomalyRange.to,
      });
      if (filters.severity) params.set("severity", filters.severity);
      if (filters.alertType) params.set("alert_type", filters.alertType);
      if (filters.category) params.set("category", filters.category);
      if (filters.status) params.set("status", filters.status);
      if (filters.scope) params.set("scope", filters.scope);
      if (filters.search.trim()) params.set("search", filters.search.trim());
      const response = await fetch(`${API_ROOT}/alerts/anomalies/download?${params.toString()}`);
      if (!response.ok) throw new Error(await response.text());
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "anomaly-alerts-report.csv";
      link.click();
      URL.revokeObjectURL(url);
      toast.success("Filtered anomaly CSV downloaded");
    } catch (downloadError) {
      toast.error(downloadError instanceof Error ? downloadError.message : "Anomaly CSV download failed");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="w-full space-y-6">
      <MotionPanel className="rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <FileSpreadsheet className="h-4 w-4 text-teal" />
              Daily Sale & Return Report (DSR)
            </div>
            <div className="mt-1 text-xs leading-5 text-muted">Daily and MTD sales vs returns by marketplace.</div>
            <div className="mt-2 text-xs font-medium text-ink">
              {targetSummary}
              {typeof achievedSummary === "number" ? <span className={`ml-2 ${achievedTone(dsrPreview?.target.status)}`}>| Achieved: {pct(achievedSummary)}</span> : null}
              {targetData.data.setup_required ? <span className="ml-2 text-amber-700">| Target table setup pending</span> : null}
              {targetData.error ? <span className="ml-2 text-red-700">| Target API unavailable</span> : null}
            </div>
          </div>
          <div className="rounded border border-line bg-slate-50 px-2 py-1 text-[11px] text-muted">Excel + WhatsApp-ready PNG</div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(210px,0.5fr)_minmax(360px,1fr)_auto]">
          <label className="text-xs font-medium text-muted">
            <span className="mb-1 flex items-center gap-1">
              <CalendarDays className="h-3.5 w-3.5" />
              DSR date
            </span>
            <input className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal" onChange={(event) => setDsrDate(event.target.value)} type="date" value={dsrDate} />
          </label>
          <div className="grid gap-2 rounded border border-line bg-slate-50 p-3 md:grid-cols-[1fr_auto]">
            <label className="text-xs font-medium text-muted">
              <span className="mb-1 block">Monthly target amount</span>
              <input
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal"
                min={1}
                onChange={(event) => setTargetAmount(event.target.value)}
                type="number"
                value={targetAmount}
              />
            </label>
            <button
              className="inline-flex items-center justify-center gap-2 self-end rounded bg-ink px-3 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
              disabled={targetSaving || targetData.data.setup_required}
              onClick={saveTarget}
              type="button"
            >
              <Save className="h-4 w-4" />
              Save
            </button>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <button
              className="inline-flex items-center gap-2 rounded bg-ink px-3 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
              disabled={downloading === "dsr-excel"}
              onClick={() => downloadDsr("excel")}
              type="button"
            >
              <Download className="h-4 w-4" />
              Download Excel
            </button>
            <button
              className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-sm font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
              disabled={downloading === "dsr-png"}
              onClick={() => downloadDsr("png")}
              type="button"
            >
              <ImageIcon className="h-4 w-4" />
              Download Image
            </button>
            <button
              className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-sm font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
              disabled={previewLoading}
              onClick={fetchDsrPreview}
              type="button"
            >
              <Eye className="h-4 w-4" />
              Preview
            </button>
          </div>
        </div>
      </MotionPanel>

      {dsrPreview ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-4">
          <div className="max-h-[90vh] w-full max-w-6xl overflow-auto rounded-lg bg-white p-5 shadow-soft">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <div className="text-lg font-semibold text-ink">NAYAM BY LAKSHITA</div>
                <div className="text-xs text-muted">DSR preview for {formatDate(dsrPreview.date)}</div>
              </div>
              <button className="rounded border border-line px-3 py-1 text-sm text-ink" onClick={() => setDsrPreview(null)} type="button">
                Close
              </button>
            </div>
            {previewSections.map((section) => (
              <div className="mb-5 overflow-x-auto" key={section.label}>
                <div className="grid grid-cols-[140px_1fr] border border-black text-center text-sm font-semibold">
                  <div className={`${section.label === "MTD" ? "bg-[#BDD7EE] text-ink" : "bg-[#1F3864] text-white"} px-3 py-2`}>{section.label}</div>
                  <div className={`${section.label === "MTD" ? "bg-[#BDD7EE] text-ink" : "bg-[#1F3864] text-white"} px-3 py-2`}>{section.summary}</div>
                </div>
                <table className="min-w-[1360px] border-collapse text-xs">
                  <thead>
                    <tr className="bg-[#FF0000] text-white">
                      {[section.leftHeader, "Platform", "Sale Qty", "Sale Value", "ASP", "Net Sale Qty", "Net Sale Value", "ASP", "RETURN Qty", "RETURN Value", "Return % Qty", "Return % Value", "Target"].map((header, index) => (
                        <th className={`border border-black px-2 py-1 ${index === 12 ? "bg-[#BDD7EE] text-ink" : ""}`} key={`${header}-${index}`}>{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...section.rows, section.total].map((row) => (
                      <tr className={row.platform === "TOTAL" ? "bg-[#F2F2F2] font-semibold" : ""} key={`${section.label}-${row.platform}`}>
                        <td className="border border-black px-2 py-1 text-center">{row.platform === "TOTAL" ? "TOTAL" : section.leftValue}</td>
                        <td className="border border-black px-2 py-1">{row.platform}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.sale_qty)}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.sale_value, "money")}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.asp)}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.net_sale_qty)}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.net_sale_value, "money")}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.net_asp)}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.return_qty)}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.return_value, "money")}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.return_pct_qty, "pct")}</td>
                        <td className="border border-black px-2 py-1 text-right">{metricCell(row.return_pct_value, "pct")}</td>
                        <td className="border border-black px-2 py-1 text-center">{row.platform === "TOTAL" ? dsrTargetLabel(dsrPreview) : ""}</td>
                      </tr>
                    ))}
                    <tr>
                      <td className="border border-black px-2 py-1" colSpan={12} />
                      <td className={`border border-black px-2 py-1 text-center font-semibold ${achievedCellClass(dsrPreview.target.status)}`}>{dsrAchievedLabel(dsrPreview)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-2">
        {reportCards.map((report) => {
          const range = ranges[report.type] ?? initialRange;
          const lastGeneratedAt = lastGenerated[report.type];
          return (
            <MotionPanel className="rounded-lg border border-line bg-white p-4 shadow-soft" key={report.type}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="max-w-2xl">
                  <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <FileSpreadsheet className="h-4 w-4 text-teal" />
                    {report.name}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-muted">{report.description}</div>
                </div>
                <div className="rounded border border-line bg-slate-50 px-2 py-1 text-[11px] text-muted">
                  Last generated: {lastGeneratedAt ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(lastGeneratedAt)) : "Never"}
                </div>
              </div>

              {report.dateRange ? (
                <div className="mt-4 flex flex-wrap items-center gap-2 rounded border border-line bg-slate-50 p-3 text-xs text-muted">
                  <CalendarDays className="h-4 w-4" />
                  <label className="flex items-center gap-2">
                    From
                    <input className="rounded border border-line bg-white px-2 py-1 text-ink outline-none focus:border-teal" onChange={(event) => updateRange(report.type, "from", event.target.value)} type="date" value={range.from} />
                  </label>
                  <label className="flex items-center gap-2">
                    To
                    <input className="rounded border border-line bg-white px-2 py-1 text-ink outline-none focus:border-teal" onChange={(event) => updateRange(report.type, "to", event.target.value)} type="date" value={range.to} />
                  </label>
                </div>
              ) : (
                <div className="mt-4 rounded border border-line bg-slate-50 px-3 py-2 text-xs text-muted">Uses the current SKU master snapshot.</div>
              )}

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  className="inline-flex items-center gap-2 rounded bg-ink px-3 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
                  disabled={downloading === `${report.type}-csv`}
                  onClick={() => downloadReport(report, "csv")}
                  type="button"
                >
                  <Download className="h-4 w-4" />
                  CSV
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-sm font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
                  disabled={downloading === `${report.type}-excel`}
                  onClick={() => downloadReport(report, "excel")}
                  type="button"
                >
                  <Download className="h-4 w-4" />
                  Excel
                </button>
              </div>
            </MotionPanel>
          );
        })}
      </section>

      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-5">
        <KPICard title="Anomaly Alerts" value={anomalies.data.summary.total} format={formatNumber} alert={anomalies.data.summary.total ? "orange" : "green"} delay={0} />
        <KPICard title="Critical" value={anomalies.data.summary.critical} format={formatNumber} alert={anomalies.data.summary.critical ? "red" : "green"} delay={0.1} />
        <KPICard title="High" value={anomalies.data.summary.high} format={formatNumber} alert={anomalies.data.summary.high ? "orange" : "green"} delay={0.2} />
        <KPICard title="Style Alerts" value={anomalies.data.summary.style_alerts} format={formatNumber} delay={0.3} />
        <KPICard title="Category Alerts" value={anomalies.data.summary.category_alerts} format={formatNumber} delay={0.4} />
      </section>

      <section className="grid min-w-0 items-start gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(360px,0.8fr)]">
        <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                <AlertTriangle className="h-4 w-4 text-amber" />
                Anomaly alert system
              </div>
              <div className="mt-1 text-xs text-muted">Sales, returns, inventory depth, and category SKU movement at style and category level.</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-sm font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
                disabled={downloading === "anomaly-filtered-csv"}
                onClick={downloadFilteredCsv}
                type="button"
              >
                <Download className="h-4 w-4" />
                Filtered CSV
              </button>
              <button
                className="inline-flex items-center gap-2 rounded bg-ink px-3 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
                disabled={downloading === "anomaly_alerts-excel"}
                onClick={() => downloadReport(reportCards.find((report) => report.type === "anomaly_alerts")!, "excel")}
                type="button"
              >
                <Download className="h-4 w-4" />
                Excel report
              </button>
            </div>
          </div>

          <div className="mb-4 grid gap-2 rounded-lg border border-line bg-slate-50 p-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="text-xs font-medium text-muted">
              <span className="mb-1 flex items-center gap-1">
                <Filter className="h-3.5 w-3.5" />
                Severity
              </span>
              <select className="w-full rounded border border-line bg-white px-2 py-2 text-sm text-ink outline-none focus:border-teal" onChange={(event) => updateFilter("severity", event.target.value)} value={filters.severity}>
                <option value="">All severities</option>
                {["Critical", "High", "Medium", "Monitor"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-muted">
              <span className="mb-1 block">Alert type</span>
              <select className="w-full rounded border border-line bg-white px-2 py-2 text-sm text-ink outline-none focus:border-teal" onChange={(event) => updateFilter("alertType", event.target.value)} value={filters.alertType}>
                <option value="">All alert types</option>
                {alertTypeOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-muted">
              <span className="mb-1 block">Category</span>
              <select className="w-full rounded border border-line bg-white px-2 py-2 text-sm text-ink outline-none focus:border-teal" onChange={(event) => updateFilter("category", event.target.value)} value={filters.category}>
                <option value="">All categories</option>
                {categoryOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-muted">
              <span className="mb-1 block">Status</span>
              <select className="w-full rounded border border-line bg-white px-2 py-2 text-sm text-ink outline-none focus:border-teal" onChange={(event) => updateFilter("status", event.target.value)} value={filters.status}>
                <option value="">All statuses</option>
                {["INSTOCK", "BROKEN", "OOS", "Mixed"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-muted">
              <span className="mb-1 block">Scope</span>
              <select className="w-full rounded border border-line bg-white px-2 py-2 text-sm text-ink outline-none focus:border-teal" onChange={(event) => updateFilter("scope", event.target.value)} value={filters.scope}>
                <option value="">Style and category</option>
                {["Style", "Category"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-muted md:col-span-2 xl:col-span-3">
              <span className="mb-1 flex items-center gap-1">
                <Search className="h-3.5 w-3.5" />
                Search style, category, reason, or action
              </span>
              <input
                className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal"
                onChange={(event) => updateFilter("search", event.target.value)}
                placeholder="Search anomalies"
                type="search"
                value={filters.search}
              />
            </label>
          </div>

          {anomalies.error ? (
            <ErrorState message={anomalies.error} onRetry={anomalies.retry} />
          ) : (
            <DataTable
              rows={anomalies.data.items || []}
              rowKey={(row) => row.id}
              empty={<EmptyState title="No anomaly alerts" body="No style or category anomalies match the current filters." />}
              minWidth="1180px"
              maxHeight="620px"
              rowClassName={(row) => (row.severity === "Critical" ? "bg-red-50/40" : "")}
              columns={[
                { key: "severity", label: "Severity", sortable: true, render: (row) => <Badge tone={severityTone(row.severity)}>{row.severity}</Badge> },
                { key: "alert_type", label: "Alert", sortable: true },
                { key: "subject", label: "Style/Category", sortable: true, copy: true, render: (row) => displaySubject(row) },
                { key: "category", label: "Category", sortable: true, render: (row) => row.category || "Unknown" },
                { key: "status", label: "Status", sortable: true, render: (row) => <Badge tone={statusTone(row.status || row.inventory_status || "")}>{row.status || row.inventory_status || "Unknown"}</Badge> },
                { key: "sales_delta_pct", label: "Sales Delta", sortable: true, align: "right", render: (row) => percentValue(row.sales_delta_pct) },
                { key: "return_pct_recent", label: "Return %", sortable: true, align: "right", render: (row) => percentValue(row.return_pct_recent) },
                { key: "inventory_delta_pct", label: "Inv Delta", sortable: true, align: "right", render: (row) => percentValue(row.inventory_delta_pct) },
                { key: "current_inventory", label: "Inventory", sortable: true, align: "right", render: (row) => numberValue(row.current_inventory) },
                { key: "reason", label: "Reason", render: (row) => row.reason || "Review anomaly" },
                { key: "action", label: "Action", render: (row) => row.action || "Review" },
              ]}
            />
          )}
        </MotionPanel>

        <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
          <div className="mb-4 text-sm font-semibold text-ink">Upload and report log</div>
          {pipeline.error ? (
            <ErrorState message={pipeline.error} onRetry={pipeline.retry} />
          ) : (
            <DataTable
              rows={pipeline.data.uploads || []}
              rowKey={(row, index) => `${row.filename || "upload"}-${index}`}
              empty={<EmptyState title="No upload log rows" />}
              minWidth="720px"
              columns={[
                { key: "filename", label: "File", sortable: true },
                { key: "upload_type", label: "Type", sortable: true },
                { key: "rows_processed", label: "Rows", sortable: true, align: "right", render: (row) => formatNumber(Number(row.rows_processed || 0)) },
                { key: "status", label: "Status", sortable: true, render: (row) => <Badge tone={row.status === "success" ? "green" : "neutral"}>{row.status || "Unknown"}</Badge> },
                { key: "created_at", label: "Created", sortable: true, render: (row) => (row.created_at ? formatDate(row.created_at) : "NA") },
              ]}
            />
          )}
        </MotionPanel>
      </section>
    </div>
  );
}
