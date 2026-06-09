import { Alert } from "@/components/ui/Alert";
import { Badge, priorityTone, statusTone } from "@/components/ui/Badge";
import { ChannelBar } from "@/components/charts/ChannelBar";
import { CategoryDonut } from "@/components/charts/CategoryDonut";
import { ChannelTrendChart } from "@/components/charts/MultiLineChart";
import { EmptyState } from "@/components/ui/EmptyState";
import { IndiaMap } from "@/components/charts/IndiaMap";
import { KPICard } from "@/components/ui/KPICard";
import { MarketplaceSalesReturns } from "@/components/charts/MarketplaceSalesReturns";
import { MotionPanel } from "@/components/ui/PageTransition";
import { SalesReturnsChart } from "@/components/charts/MultiLineChart";
import { SalesTrendLine } from "@/components/charts/SalesTrendLine";
import {
  emptyInventoryKpis,
  emptySalesKpis,
  type CategoryMix,
  type ChannelTrendPoint,
  type InventoryKpis,
  type InventoryStyle,
  type MarketplaceSummary,
  type Paginated,
  type RegionalState,
  type SalesKpis,
  type TrendPoint,
} from "@/lib/api";
import { resolveDateRange, withDateRange } from "@/lib/dateRange";
import { formatNumber } from "@/lib/formatters";
import { serverApiGet } from "@/lib/server-api";

type DashboardSearchParams = Promise<Record<string, string | string[] | undefined>>;

async function safeGet<T>(path: string, fallback: T): Promise<T> {
  try {
    return await serverApiGet<T>(path);
  } catch {
    return fallback;
  }
}

export default async function ExecutivePage({ searchParams }: { searchParams?: DashboardSearchParams }) {
  const dateRange = resolveDateRange(searchParams ? await searchParams : undefined);
  const scoped = (path: string) => withDateRange(path, dateRange);
  const salesKpis = await safeGet<SalesKpis>(scoped("/sales/kpis"), emptySalesKpis);
  const trend = await safeGet<TrendPoint[]>(scoped("/sales/trend"), []);
  const returns = await safeGet<TrendPoint[]>(scoped("/returns/trend"), []);
  const channelTrend = await safeGet<ChannelTrendPoint[]>(scoped("/sales/by_channel_trend"), []);
  const marketplaceSummary = await safeGet<MarketplaceSummary[]>(scoped("/sales/marketplace_summary"), []);
  const categories = await safeGet<CategoryMix[]>(scoped("/sales/by_category"), []);
  const states = await safeGet<RegionalState[]>(scoped("/regional/states"), []);
  const inventoryKpis = await safeGet<InventoryKpis>("/inventory/kpis", emptyInventoryKpis);
  const styles = await safeGet<Paginated<InventoryStyle>>("/inventory/styles?limit=5", { items: [], page: 1, limit: 5, total: 0 });

  const channelTotals = Array.from(
    channelTrend.reduce((map, row) => {
      const item = map.get(row.channel) ?? { name: row.channel, value: 0, qty: 0 };
      item.value += row.sales_value;
      item.qty += row.qty;
      map.set(row.channel, item);
      return map;
    }, new Map<string, { name: string; value: number; qty: number }>())
  ).map((entry) => entry[1]);

  const categoryData = categories.map((row) => ({
    name: row.category || row.name || "Unknown",
    value: Number(row.sales_value ?? row.value ?? 0),
    qty: row.qty,
    styles: row.sku_count,
  }));

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <KPICard title="Sales" value={salesKpis.mtd_sales} formatType="inr" trend={salesKpis.sales_growth_pct} delay={0} />
        <KPICard title="Qty" value={salesKpis.mtd_qty} formatType="qty" trend={salesKpis.qty_growth_pct} delay={0.1} />
        <KPICard title="Return %" value={salesKpis.return_pct} formatType="pct" trend={salesKpis.return_pct_change} trendDirection="lower-is-good" trendUnit="pp" alert="orange" delay={0.2} />
        <KPICard title="OOS %" value={inventoryKpis.oos_pct} formatType="pct" alert="red" delay={0.3} />
        <KPICard title="Broken %" value={inventoryKpis.broken_pct} formatType="pct" alert="orange" delay={0.4} />
        <KPICard title="Inventory" value={inventoryKpis.total_inventory} formatType="qty" delay={0.5} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          {trend.length ? <SalesTrendLine data={trend.map((row) => ({ date: row.date, sales_value: row.sales_value || 0, qty: row.qty }))} /> : <EmptyState title="No sales trend" />}
          {trend.length || returns.length ? (
            <SalesReturnsChart sales={trend.map((row) => ({ date: row.date, sales_value: row.sales_value || 0 }))} returns={returns.map((row) => ({ date: row.date, return_value: row.return_value || 0 }))} />
          ) : (
            <EmptyState title="No sales or returns trend" />
          )}
        </div>
        {categoryData.length ? <CategoryDonut data={categoryData} title="Category mix" valueLabel="Revenue" /> : <EmptyState title="No category mix" />}
      </section>

      <section className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        {channelTrend.length ? <ChannelTrendChart data={channelTrend} /> : <EmptyState title="No channel trend" />}
        {channelTotals.length ? <ChannelBar data={channelTotals} /> : <EmptyState title="No channel contribution" />}
      </section>

      {marketplaceSummary.length ? <MarketplaceSalesReturns data={marketplaceSummary} compact /> : <EmptyState title="No marketplace sales and returns" />}

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <MotionPanel className="space-y-3 rounded-lg border border-line bg-white p-4 shadow-soft">
          <div className="text-sm font-semibold text-ink">Top 5 alerts</div>
          {inventoryKpis.oos_count ? <Alert level="critical" title="OOS risk" body={`${formatNumber(inventoryKpis.oos_count)} styles are currently out of stock.`} /> : null}
          {inventoryKpis.low_stock_alerts ? <Alert level="warning" title="Replenishment risk" body={`${formatNumber(inventoryKpis.low_stock_alerts)} styles are flagged P0-P2.`} /> : null}
          {styles.items.slice(0, 3).map((style) => (
            <div className="flex items-center justify-between rounded border border-line p-3 text-sm" key={style.style_color}>
              <div>
                <div className="font-medium text-ink">{style.style_color}</div>
                <div className="mt-1 text-xs text-muted">DOI {style.doi}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={statusTone(style.status || style.inventory_status)}>{style.status || style.inventory_status || "UNKNOWN"}</Badge>
                <Badge tone={priorityTone(style.priority)}>{style.priority || "Monitor"}</Badge>
              </div>
            </div>
          ))}
        </MotionPanel>
        {states.length ? <IndiaMap data={states} /> : <EmptyState title="No regional sales" />}
      </section>
    </div>
  );
}
