import { ReturnsClient, type ReturnChannel, type ReturnSku, type ReturnSummary, type ReturnTrend } from "@/app/(dashboard)/returns/ReturnsClient";
import { emptySalesKpis, type SalesKpis } from "@/lib/api";
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

export default async function ReturnsPage({ searchParams }: { searchParams?: DashboardSearchParams }) {
  const dateRange = resolveDateRange(searchParams ? await searchParams : undefined);
  const scoped = (path: string) => withDateRange(path, dateRange);
  const [sales, summary, byChannel, highSkus, trend] = await Promise.all([
    safeGet<SalesKpis>(scoped("/sales/kpis"), emptySalesKpis),
    safeGet<ReturnSummary>(scoped("/returns/summary"), { return_value: 0, return_qty: 0 }),
    safeGet<ReturnChannel[]>(scoped("/returns/by_channel"), []),
    safeGet<ReturnSku[]>(scoped("/returns/high_return_skus"), []),
    safeGet<ReturnTrend[]>(scoped("/returns/trend"), []),
  ]);

  return <ReturnsClient sales={sales} summary={summary} byChannel={byChannel} highSkus={highSkus} trend={trend} />;
}
