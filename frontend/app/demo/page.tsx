"use client";

import {
  BarChart3,
  Bell,
  Bot,
  Boxes,
  CalendarDays,
  CircleDollarSign,
  ClipboardList,
  Database,
  Globe2,
  Layers3,
  LogOut,
  Shield,
  Tags,
  UserCircle,
} from "lucide-react";

import { ChannelBar } from "@/components/charts/ChannelBar";
import { CategoryDonut } from "@/components/charts/CategoryDonut";
import { IndiaMap } from "@/components/charts/IndiaMap";
import { ChannelTrendChart, SalesReturnsChart } from "@/components/charts/MultiLineChart";
import { MarketplaceSalesReturns } from "@/components/charts/MarketplaceSalesReturns";
import { SalesTrendLine } from "@/components/charts/SalesTrendLine";
import { KPICard } from "@/components/ui/KPICard";

const nav = [
  { label: "Executive", icon: BarChart3 },
  { label: "Sales", icon: CircleDollarSign },
  { label: "Inventory", icon: Boxes },
  { label: "Categories", icon: Tags },
  { label: "Ads", icon: Layers3 },
  { label: "Returns", icon: ClipboardList },
  { label: "Regional", icon: Globe2 },
  { label: "Assistant", icon: Bot },
  { label: "Reports", icon: Bell },
  { label: "Admin", icon: Shield },
];

const salesTrend = [
  { date: "2026-05-11", sales_value: 840000, qty: 720 },
  { date: "2026-05-12", sales_value: 790000, qty: 690 },
  { date: "2026-05-13", sales_value: 910000, qty: 805 },
  { date: "2026-05-14", sales_value: 760000, qty: 670 },
  { date: "2026-05-15", sales_value: 880000, qty: 760 },
  { date: "2026-05-16", sales_value: 940000, qty: 835 },
  { date: "2026-05-17", sales_value: 1230000, qty: 1080 },
  { date: "2026-05-18", sales_value: 1050000, qty: 920 },
  { date: "2026-05-19", sales_value: 1020000, qty: 905 },
  { date: "2026-05-20", sales_value: 1120000, qty: 980 },
  { date: "2026-05-21", sales_value: 1010000, qty: 880 },
  { date: "2026-05-22", sales_value: 890000, qty: 790 },
  { date: "2026-05-23", sales_value: 1180000, qty: 1010 },
  { date: "2026-05-24", sales_value: 1210000, qty: 1045 },
  { date: "2026-05-25", sales_value: 980000, qty: 845 },
  { date: "2026-05-26", sales_value: 930000, qty: 812 },
  { date: "2026-05-27", sales_value: 960000, qty: 835 },
  { date: "2026-05-28", sales_value: 1910000, qty: 1600 },
  { date: "2026-05-29", sales_value: 2140000, qty: 1785 },
  { date: "2026-05-30", sales_value: 1760000, qty: 1460 },
  { date: "2026-05-31", sales_value: 1940000, qty: 1620 },
  { date: "2026-06-01", sales_value: 1650000, qty: 1380 },
  { date: "2026-06-02", sales_value: 1540000, qty: 1295 },
  { date: "2026-06-03", sales_value: 1580000, qty: 1320 },
];

const returnsTrend = salesTrend.map((row, index) => ({
  date: row.date,
  return_value: Math.round(row.sales_value * ([0.14, 0.16, 0.19, 0.13, 0.17, 0.15][index % 6])),
}));

const categoryData = [
  { name: "NOOS", value: 6850000, qty: 6280, styles: 42 },
  { name: "Potential NOOS", value: 5420000, qty: 4815, styles: 57 },
  { name: "Green", value: 4250000, qty: 3710, styles: 86 },
  { name: "Yellow", value: 3180000, qty: 2840, styles: 134 },
  { name: "Red", value: 2260000, qty: 1930, styles: 171 },
  { name: "Winter", value: 1840000, qty: 1185, styles: 39 },
  { name: "Launch", value: 1470000, qty: 980, styles: 55 },
  { name: "Watchlist", value: 980000, qty: 760, styles: 72 },
];

const channelTotals = [
  { name: "Myntra", value: 14350000, qty: 12720 },
  { name: "Ajio", value: 5260000, qty: 4620 },
  { name: "Nykaa", value: 3560000, qty: 2830 },
  { name: "Flipkart", value: 2920000, qty: 2540 },
  { name: "Amazon", value: 1610000, qty: 1420 },
  { name: "TataCliq", value: 720000, qty: 610 },
];

const channelMix = [
  { channel: "Myntra", ratio: 0.51, qtyRatio: 0.49 },
  { channel: "Ajio", ratio: 0.19, qtyRatio: 0.18 },
  { channel: "Nykaa", ratio: 0.13, qtyRatio: 0.11 },
  { channel: "Flipkart", ratio: 0.1, qtyRatio: 0.12 },
  { channel: "Amazon", ratio: 0.05, qtyRatio: 0.07 },
  { channel: "TataCliq", ratio: 0.02, qtyRatio: 0.03 },
];

const channelTrend = salesTrend.flatMap((row, dayIndex) =>
  channelMix.map((channel, channelIndex) => {
    const movement = 0.88 + ((dayIndex + channelIndex) % 5) * 0.06;
    return {
      date: row.date,
      channel: channel.channel,
      sales_value: Math.round(row.sales_value * channel.ratio * movement),
      qty: Math.round(row.qty * channel.qtyRatio * movement),
    };
  })
);

const marketplaceSummary = [
  { marketplace: "Myntra", sales_value: 14350000, sales_qty: 12720, return_value: 2470000, return_qty: 2210, return_pct: 17.2, net_sales: 11880000 },
  { marketplace: "Ajio", sales_value: 5260000, sales_qty: 4620, return_value: 1040000, return_qty: 910, return_pct: 19.8, net_sales: 4220000 },
  { marketplace: "Nykaa", sales_value: 3560000, sales_qty: 2830, return_value: 430000, return_qty: 362, return_pct: 12.1, net_sales: 3130000 },
  { marketplace: "Flipkart", sales_value: 2920000, sales_qty: 2540, return_value: 690000, return_qty: 615, return_pct: 23.6, net_sales: 2230000 },
  { marketplace: "Amazon", sales_value: 1610000, sales_qty: 1420, return_value: 260000, return_qty: 235, return_pct: 16.1, net_sales: 1350000 },
  { marketplace: "TataCliq", sales_value: 720000, sales_qty: 610, return_value: 82000, return_qty: 76, return_pct: 11.4, net_sales: 638000 },
];

const regionalData = [
  { state: "Uttar Pradesh", sales: 6420000, qty: 5680, return_value: 1210000, return_qty: 1045, return_pct: 18.8 },
  { state: "Maharashtra", sales: 4280000, qty: 3740, return_value: 640000, return_qty: 520, return_pct: 15.0 },
  { state: "Delhi", sales: 3310000, qty: 2845, return_value: 520000, return_qty: 436, return_pct: 15.7 },
  { state: "Karnataka", sales: 2860000, qty: 2410, return_value: 438000, return_qty: 351, return_pct: 15.3 },
  { state: "Gujarat", sales: 2240000, qty: 1940, return_value: 395000, return_qty: 328, return_pct: 17.6 },
  { state: "Rajasthan", sales: 1760000, qty: 1525, return_value: 346000, return_qty: 304, return_pct: 19.7 },
  { state: "Tamil Nadu", sales: 1540000, qty: 1310, return_value: 212000, return_qty: 178, return_pct: 13.8 },
  { state: "West Bengal", sales: 1260000, qty: 1095, return_value: 230000, return_qty: 202, return_pct: 18.3 },
  { state: "Punjab", sales: 860000, qty: 730, return_value: 168000, return_qty: 145, return_pct: 19.5 },
  { state: "Haryana", sales: 780000, qty: 675, return_value: 112000, return_qty: 94, return_pct: 14.4 },
];

const alerts = [
  { title: "OOS risk", body: "196 demo styles are currently out of stock.", tone: "critical" },
  { title: "Replenishment risk", body: "248 styles are flagged P0-P2 for the next buying cycle.", tone: "warning" },
  { title: "Return spike", body: "Flipkart westernwear returns crossed the 7-day threshold.", tone: "warning" },
];

const styleQueue = [
  { style: "DEMO-TOP-104-BLACK", doi: 0, status: "OOS", action: "Replenish P0" },
  { style: "DEMO-DRS-219-MAROON", doi: 142, status: "BROKEN", action: "Hold buy" },
  { style: "DEMO-BOT-087-TEAL", doi: 48, status: "HIGH RETURN", action: "Check fit issue" },
  { style: "DEMO-KRT-332-IVORY", doi: 19, status: "NOOS", action: "Scale stock" },
  { style: "DEMO-WIN-512-SAGE", doi: 93, status: "WATCHLIST", action: "Review discount" },
];

function DemoSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-line bg-white px-4 py-5 lg:block">
      <div className="mb-8">
        <div className="text-xl font-semibold text-ink">E-Commerce BI</div>
        <div className="mt-3 rounded border border-line bg-slate-50 px-3 py-4 text-center">
          <div className="text-2xl font-semibold tracking-[0.12em] text-ink">COMMERCE</div>
          <div className="mt-1 text-[10px] font-semibold uppercase tracking-[0.28em] text-teal">BI Platform</div>
        </div>
        <div className="mt-2 text-xs text-muted">Fashion commerce command center</div>
      </div>
      <nav className="space-y-1">
        {nav.map((item, index) => {
          const Icon = item.icon;
          return (
            <a
              className={`flex items-center gap-3 rounded border-l-2 px-3 py-2 text-sm font-medium transition duration-200 ease-in-out ${
                index === 0 ? "border-l-teal bg-teal/5 text-ink" : "border-l-transparent text-muted"
              }`}
              href={`#${item.label.toLowerCase()}`}
              key={item.label}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </a>
          );
        })}
      </nav>
    </aside>
  );
}

function DemoTopbar() {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-white/95 px-6 py-4 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs text-muted">Executive</div>
          <div className="mt-1 text-sm font-semibold text-ink">Executive Summary</div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 text-xs sm:w-auto sm:text-sm">
          <div className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-muted">
            <CalendarDays className="h-4 w-4" />
            30 days
          </div>
          <div className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-muted">
            <span className="h-2 w-2 rounded-full bg-danger" />
            Last synced: demo snapshot
          </div>
          <button className="relative inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-muted" type="button">
            <Bell className="h-4 w-4" />
            Alerts
            <span className="absolute -right-2 -top-2 rounded-full bg-danger px-1.5 py-0.5 text-[10px] font-semibold text-white">58</span>
          </button>
          <button className="hidden items-center gap-2 rounded border border-line px-3 py-2 text-muted sm:inline-flex" type="button">
            <Database className="h-4 w-4" />
            Synced
          </button>
          <button className="hidden items-center gap-2 rounded bg-ink px-3 py-2 text-white sm:inline-flex" type="button">
            <UserCircle className="h-4 w-4" />
            demo.operator
          </button>
          <button className="hidden items-center gap-2 rounded border border-line px-3 py-2 text-muted sm:inline-flex" type="button">
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}

function AlertsPanel() {
  return (
    <div className="min-h-[560px] rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-4 text-sm font-semibold text-ink">Top 5 alerts</div>
      <div className="space-y-3">
        {alerts.map((alert) => (
          <div
            className={`rounded-lg border p-4 ${alert.tone === "critical" ? "border-red-200 bg-red-50/50" : "border-amber-200 bg-amber-50/40"}`}
            key={alert.title}
          >
            <div className="font-semibold text-ink">{alert.title}</div>
            <div className="mt-2 text-sm text-muted">{alert.body}</div>
          </div>
        ))}
        {styleQueue.map((style) => (
          <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded border border-line px-4 py-3 text-sm" key={style.style}>
            <div className="min-w-0">
              <div className="truncate font-semibold text-ink">{style.style}</div>
              <div className="mt-1 text-xs text-muted">DOI {style.doi}</div>
            </div>
            <div className="text-xs font-semibold text-ink">{style.status}</div>
            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-ink">{style.action}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DemoDashboardPage() {
  return (
    <main className="min-h-screen bg-canvas text-ink">
      <DemoSidebar />
      <div className="lg:pl-64">
        <DemoTopbar />
        <div className="space-y-6 px-6 py-6">
          <section className="grid scroll-mt-24 gap-4 md:grid-cols-2 xl:grid-cols-6" id="executive">
            <KPICard title="Sales" value={28420000} formatType="inr" trend={138.7} sparkline={[22, 28, 36, 52, 78, 88]} />
            <KPICard title="Qty" value={24740} formatType="qty" trend={92.4} sparkline={[20, 29, 34, 48, 67, 75]} />
            <KPICard title="Return %" value={18.6} formatType="pct" trend={-3.4} trendDirection="lower-is-good" trendUnit="pp" alert="orange" sparkline={[54, 47, 42, 35, 31, 27]} />
            <KPICard title="OOS %" value={12.4} formatType="pct" trend={-5.8} trendDirection="lower-is-good" trendUnit="pp" alert="red" sparkline={[72, 64, 58, 46, 37, 29]} />
            <KPICard title="Broken %" value={7.8} formatType="pct" trend={-1.9} trendDirection="lower-is-good" trendUnit="pp" alert="orange" sparkline={[44, 41, 38, 34, 30, 27]} />
            <KPICard title="Inventory" value={194000} formatType="qty" sparkline={[28, 37, 46, 58, 72, 84]} />
          </section>

          <section className="grid scroll-mt-24 gap-5 xl:grid-cols-[2fr_1fr]" id="sales">
            <SalesTrendLine data={salesTrend} title="Daily sales trend" />
            <CategoryDonut data={categoryData} title="Category mix" valueLabel="Revenue" />
          </section>

          <section className="grid scroll-mt-24 gap-5 xl:grid-cols-[2fr_1fr]" id="returns">
            <SalesReturnsChart sales={salesTrend.map((row) => ({ date: row.date, sales_value: row.sales_value }))} returns={returnsTrend} />
            <ChannelBar data={channelTotals} />
          </section>

          <section className="scroll-mt-24" id="ads">
            <ChannelTrendChart data={channelTrend} />
          </section>

          <section className="scroll-mt-24" id="reports">
            <MarketplaceSalesReturns data={marketplaceSummary} compact />
          </section>

          <section className="grid scroll-mt-24 gap-5 xl:grid-cols-[1fr_1fr]" id="regional">
            <AlertsPanel />
            <IndiaMap data={regionalData} />
          </section>
          <div aria-hidden="true" className="h-48" />
        </div>
      </div>
    </main>
  );
}
