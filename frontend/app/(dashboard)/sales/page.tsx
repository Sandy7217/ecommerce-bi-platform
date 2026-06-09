import { SalesClient } from "@/app/(dashboard)/sales/SalesClient";
import {
  emptySalesKpis,
  emptySalesReturnsForecast,
  type CategoryMix,
  type ChannelTrendPoint,
  type MarketplaceSummary,
  type RegionalHeatmapState,
  type SalesKpis,
  type SalesReturnsForecast,
  type TopProduct,
  type TrendPoint,
} from "@/lib/api";
import { resolveDateRange, withDateRange } from "@/lib/dateRange";
import { serverApiGet } from "@/lib/server-api";

type DashboardSearchParams = Promise<Record<string, string | string[] | undefined>>;

async function safeGet<T>(path: string, fallback: T): Promise<T> {
  try {
    return await serverApiGet<T>(path);
  } catch {
    return fallback;
  }
}

function firstParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function numericParam(value: string | string[] | undefined, fallback: number, allowed: number[]) {
  const parsed = Number(firstParam(value));
  return allowed.includes(parsed) ? parsed : fallback;
}

export default async function SalesPage({ searchParams }: { searchParams?: DashboardSearchParams }) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const dateRange = resolveDateRange(resolvedSearchParams);
  const forecastTrainingDays = numericParam(resolvedSearchParams?.forecast_training_days, 730, [180, 365, 730]);
  const forecastHorizonDays = numericParam(resolvedSearchParams?.forecast_horizon_days, 30, [30, 60, 90]);
  const scoped = (path: string) => withDateRange(path, dateRange);
  const [kpis, trend, returns, channelTrend, marketplaceSummary, topProducts, categories, states, forecast] = await Promise.all([
    safeGet<SalesKpis>(scoped("/sales/kpis"), emptySalesKpis),
    safeGet<TrendPoint[]>(scoped("/sales/trend"), []),
    safeGet<TrendPoint[]>(scoped("/returns/trend"), []),
    safeGet<ChannelTrendPoint[]>(scoped("/sales/by_channel_trend"), []),
    safeGet<MarketplaceSummary[]>(scoped("/sales/marketplace_summary"), []),
    safeGet<TopProduct[]>(scoped("/sales/top_products?limit=20"), []),
    safeGet<CategoryMix[]>(scoped("/sales/by_category"), []),
    safeGet<RegionalHeatmapState[]>(scoped("/regional/state_heatmap"), []),
    safeGet<SalesReturnsForecast>(`/forecast/sales_returns?horizon_days=${forecastHorizonDays}&training_days=${forecastTrainingDays}&include_diagnostics=true`, emptySalesReturnsForecast),
  ]);

  return <SalesClient kpis={kpis} trend={trend} returns={returns} channelTrend={channelTrend} marketplaceSummary={marketplaceSummary} topProducts={topProducts} categories={categories} states={states} forecast={forecast} />;
}
