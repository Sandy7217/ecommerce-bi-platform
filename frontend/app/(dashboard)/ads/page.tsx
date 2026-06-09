import { AdsClient } from "@/app/(dashboard)/ads/AdsClient";
import { resolveDateRange } from "@/lib/dateRange";

type AdsSearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function AdsPage({ searchParams }: { searchParams?: AdsSearchParams }) {
  const dateRange = resolveDateRange(searchParams ? await searchParams : undefined);
  return <AdsClient dateRange={dateRange} />;
}
