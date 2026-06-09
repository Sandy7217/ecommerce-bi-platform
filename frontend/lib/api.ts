const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.replace("http://localhost:8001", "http://127.0.0.1:8001").replace(/\/$/, "");
const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

const externalApiRoot =
  configuredApiBaseUrl ??
  (configuredApiUrl ? `${configuredApiUrl}/api` : "http://127.0.0.1:8001/api");

export const DIRECT_API_ROOT = externalApiRoot;
export const API_ROOT = typeof window === "undefined" ? externalApiRoot : "/api/backend";

export type SalesKpis = {
  mtd_sales: number;
  mtd_qty: number;
  mtd_sales_lakh: number;
  asp: number;
  return_pct: number;
  return_qty: number;
  return_value: number;
  yesterday_sales: number;
  yesterday_qty: number;
  sales_growth_pct: number;
  qty_growth_pct: number;
  return_pct_change: number;
  comparison_from?: string;
  comparison_to?: string;
  date: string;
};

export type InventoryKpis = {
  total_inventory: number;
  total_styles: number;
  oos_pct: number;
  broken_pct: number;
  instock_pct: number;
  oos_count: number;
  broken_count: number;
  instock_count: number;
  low_stock_alerts: number;
};

export type AlertsCount = {
  count: number;
  oos_count: number;
  p0_p1_count: number;
};

export type TrendPoint = {
  date: string;
  sales_value?: number;
  return_value?: number;
  qty?: number;
  return_qty?: number;
};

export type ForecastPoint = {
  date: string;
  sales_value: number;
  sales_value_low?: number;
  sales_value_high?: number;
  sales_qty: number;
  return_value: number;
  return_value_low?: number;
  return_value_high?: number;
  return_qty: number;
  net_sales: number;
  net_sales_low?: number;
  net_sales_high?: number;
  return_pct: number;
};

export type SalesReturnsForecast = {
  history: ForecastPoint[];
  forecast: ForecastPoint[];
  summary: {
    recent_sales_value: number;
    recent_return_value: number;
    forecast_sales_value: number;
    forecast_return_value: number;
    forecast_net_sales: number;
    forecast_sales_qty: number;
    forecast_return_qty: number;
    forecast_return_pct: number;
    history_start?: string | null;
    history_end?: string | null;
    as_of_date?: string | null;
    forecast_start_date?: string | null;
    training_requested_days?: number;
    training_calendar_days?: number;
    sales_training_days: number;
    return_training_days: number;
    myntra_source_used?: string;
    selected_models?: Record<string, string>;
    backtest_wape?: number | null;
    backtest_wape_by_metric?: Record<string, number | null>;
    confidence_level?: string;
    return_value_rate?: number | null;
    return_qty_rate?: number | null;
    excluded_current_day: string;
  };
  method: string;
  model: string;
  horizon_days: number;
  training_window_days?: number;
  generated_at: string;
  diagnostics?: {
    latest_sales_date?: string | null;
    latest_return_date?: string | null;
    myntra_source_counts?: Record<string, number>;
    band_pct?: number;
  };
};

export type ChannelTrendPoint = {
  date: string;
  channel: string;
  sales_value: number;
  qty: number;
};

export type MarketplaceSummary = {
  marketplace: string;
  sales_value: number;
  sales_qty: number;
  return_value: number;
  return_qty: number;
  return_pct: number;
  net_sales: number;
};

export type CategoryMix = {
  category?: string;
  name?: string;
  value?: number;
  sales_value?: number;
  qty?: number;
  sku_count?: number;
};

export type RegionalState = {
  state: string;
  sales: number;
  qty: number;
  return_pct: number;
};

export type StateTopStyle = {
  style_color: string;
  sales: number;
  qty: number;
};

export type RegionalHeatmapState = {
  state: string;
  sales: number;
  qty: number;
  return_value: number;
  return_qty: number;
  return_pct: number;
  top_styles: StateTopStyle[];
};

export type InventoryStyle = {
  style_color: string;
  category_new?: string;
  status?: string;
  inventory_status?: string;
  total_inventory: number;
  ros_30d: number;
  doi: number;
  priority?: string;
  replenishment_qty?: number;
};

export type ReplenishmentSizeRow = {
  size: string;
  current_qty: number;
  recommended_qty: number;
};

export type ReplenishmentPlanItem = InventoryStyle & {
  ros_7d: number;
  visibility_ros: number;
  predicted_ros: number;
  target_cover_days: number;
  target_stock: number;
  pending_replenishment_qty: number;
  sales_qty_30d?: number;
  sales_qty_90d?: number;
  active_sale_days_90d?: number;
  raw_replenishment_qty: number;
  recommended_replenishment_qty: number;
  replenishment_reason?: string;
  already_planned: boolean;
  action: "Auto" | "Review" | "Hold" | string;
  urgency: string;
  stockout_date?: string | null;
  order_by_date?: string | null;
  days_to_stockout?: number | null;
  size_replenishment: ReplenishmentSizeRow[];
};

export type ReplenishmentChartRow = {
  name: string;
  qty?: number;
  styles?: number;
};

export type ReplenishmentPlan = Paginated<ReplenishmentPlanItem> & {
  summary: {
    total_styles: number;
    urgent_styles: number;
    due_this_week_styles: number;
    already_planned_styles: number;
    manual_pending_qty: number;
    recommended_qty: number;
    eligible_styles: number;
    no_replenishment_styles: number;
    auto_styles: number;
    review_styles: number;
    hold_styles: number;
  };
  charts: {
    urgency: ReplenishmentChartRow[];
    category: ReplenishmentChartRow[];
    manual_vs_new: ReplenishmentChartRow[];
    size: ReplenishmentChartRow[];
  };
};

export type InventoryCategoryStyle = InventoryStyle & {
  sales_value: number;
  sales_qty: number;
  return_value: number;
  return_qty: number;
  return_pct: number;
};

export type Paginated<T> = {
  items: T[];
  page: number;
  limit: number;
  total: number;
};

export type TopProduct = {
  style_color: string;
  revenue: number;
  orders: number;
  qty: number;
  ros: number;
  growth_pct: number;
  return_pct: number;
};

export type MatrixRow = {
  category: string;
  sales_value: number;
  sales_qty: number;
  return_value: number;
  return_qty: number;
  return_pct: number;
  broken_sales_value: number;
  broken_sales_qty: number;
  broken_sales_mix_pct: number;
  broken_return_value: number;
  broken_return_qty: number;
  broken_return_pct: number;
  broken_styles: number;
  broken_pct: number;
  broken_inventory: number;
  instock_sales_value: number;
  instock_sales_qty: number;
  instock_sales_mix_pct: number;
  instock_return_value: number;
  instock_return_qty: number;
  instock_return_pct: number;
  instock_styles: number;
  instock_pct: number;
  instock_inventory: number;
  oos_sales_value: number;
  oos_sales_qty: number;
  oos_sales_mix_pct: number;
  oos_return_value: number;
  oos_return_qty: number;
  oos_return_pct: number;
  oos_styles: number;
  oos_pct: number;
  oos_inventory: number;
  total_styles: number;
  total_inventory: number;
};

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${response.status}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${response.status}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`${response.status}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export function apiDownloadUrl(path: string): string {
  return `${API_ROOT}${path}`;
}

export const emptySalesKpis: SalesKpis = {
  mtd_sales: 0,
  mtd_qty: 0,
  mtd_sales_lakh: 0,
  asp: 0,
  return_pct: 0,
  return_qty: 0,
  return_value: 0,
  yesterday_sales: 0,
  yesterday_qty: 0,
  sales_growth_pct: 0,
  qty_growth_pct: 0,
  return_pct_change: 0,
  date: "",
};

export const emptySalesReturnsForecast: SalesReturnsForecast = {
  history: [],
  forecast: [],
  summary: {
    recent_sales_value: 0,
    recent_return_value: 0,
    forecast_sales_value: 0,
    forecast_return_value: 0,
    forecast_net_sales: 0,
    forecast_sales_qty: 0,
    forecast_return_qty: 0,
    forecast_return_pct: 0,
    history_start: null,
    history_end: null,
    as_of_date: null,
    forecast_start_date: null,
    training_requested_days: 730,
    training_calendar_days: 0,
    sales_training_days: 0,
    return_training_days: 0,
    myntra_source_used: "",
    selected_models: {},
    backtest_wape: null,
    backtest_wape_by_metric: {},
    confidence_level: "",
    return_value_rate: null,
    return_qty_rate: null,
    excluded_current_day: "",
  },
  method: "",
  model: "",
  horizon_days: 30,
  training_window_days: 730,
  generated_at: "",
};

export const emptyInventoryKpis: InventoryKpis = {
  total_inventory: 0,
  total_styles: 0,
  oos_pct: 0,
  broken_pct: 0,
  instock_pct: 0,
  oos_count: 0,
  broken_count: 0,
  instock_count: 0,
  low_stock_alerts: 0,
};

export const emptyReplenishmentPlan: ReplenishmentPlan = {
  items: [],
  page: 1,
  limit: 200,
  total: 0,
  summary: {
    total_styles: 0,
    urgent_styles: 0,
    due_this_week_styles: 0,
    already_planned_styles: 0,
    manual_pending_qty: 0,
    recommended_qty: 0,
    eligible_styles: 0,
    no_replenishment_styles: 0,
    auto_styles: 0,
    review_styles: 0,
    hold_styles: 0,
  },
  charts: {
    urgency: [],
    category: [],
    manual_vs_new: [],
    size: [],
  },
};
