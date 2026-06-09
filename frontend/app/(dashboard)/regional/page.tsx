import { RegionalClient } from "@/app/(dashboard)/regional/RegionalClient";
import { type RegionalHeatmapState } from "@/lib/api";
import { resolveDateRange, withDateRange } from "@/lib/dateRange";
import { serverApiGet } from "@/lib/server-api";

type RegionalSearchParams = Promise<Record<string, string | string[] | undefined>>;

async function safeGet<T>(path: string, fallback: T): Promise<T> {
  try {
    return await serverApiGet<T>(path);
  } catch {
    return fallback;
  }
}

export default async function RegionalPage({ searchParams }: { searchParams?: RegionalSearchParams }) {
  const dateRange = resolveDateRange(searchParams ? await searchParams : undefined);
  const states = await safeGet<RegionalHeatmapState[]>(withDateRange("/regional/state_heatmap", dateRange), []);
  return <RegionalClient states={states} />;
}
