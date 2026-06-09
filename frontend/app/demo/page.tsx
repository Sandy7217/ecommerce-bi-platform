import {
  AlertTriangle,
  BarChart3,
  Boxes,
  CircleDollarSign,
  Download,
  LineChart,
  PackageCheck,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";

const kpis = [
  { label: "MTD sales", value: "Rs 42.8L", change: "+18.6%", tone: "teal", bars: [42, 48, 55, 61, 58, 66, 72, 81] },
  { label: "Net quantity", value: "18,420", change: "+11.2%", tone: "blue", bars: [36, 44, 41, 52, 60, 62, 70, 74] },
  { label: "Return %", value: "14.8%", change: "-2.1 pp", tone: "amber", bars: [68, 64, 60, 58, 55, 51, 49, 46] },
  { label: "OOS styles", value: "96", change: "-14 styles", tone: "danger", bars: [82, 79, 75, 69, 63, 58, 53, 48] },
];

const channels = [
  { name: "Myntra", sales: "Rs 17.4L", value: 92, returns: "13.2%" },
  { name: "Ajio", sales: "Rs 9.8L", value: 68, returns: "16.1%" },
  { name: "Nykaa", sales: "Rs 5.6L", value: 42, returns: "10.7%" },
  { name: "Flipkart", sales: "Rs 4.9L", value: 37, returns: "18.9%" },
  { name: "Amazon", sales: "Rs 3.2L", value: 24, returns: "12.4%" },
];

const trend = [38, 44, 41, 53, 61, 58, 67, 72, 78, 74, 83, 88];

const categories = [
  { name: "Topwear", revenue: "Rs 15.2L", inventory: "5,820", value: 78, tone: "bg-teal" },
  { name: "Dresses", revenue: "Rs 10.7L", inventory: "3,940", value: 59, tone: "bg-blue" },
  { name: "Bottomwear", revenue: "Rs 8.9L", inventory: "2,870", value: 49, tone: "bg-amber" },
  { name: "Winterwear", revenue: "Rs 4.1L", inventory: "1,430", value: 27, tone: "bg-danger" },
];

const alerts = [
  { style: "STYLE-1042-BLACK", channel: "Myntra", status: "OOS", doi: "0", action: "Replenish P0", tone: "red" },
  { style: "STYLE-2198-MAROON", channel: "Ajio", status: "Broken", doi: "134", action: "Hold buy", tone: "amber" },
  { style: "STYLE-0877-TEAL", channel: "Nykaa", status: "High return", doi: "48", action: "Check fit issue", tone: "blue" },
  { style: "STYLE-3321-IVORY", channel: "Flipkart", status: "NOOS", doi: "21", action: "Scale stock", tone: "green" },
];

const navItems = [
  { label: "Executive", icon: BarChart3 },
  { label: "Sales", icon: TrendingUp },
  { label: "Inventory", icon: Boxes },
  { label: "Reports", icon: LineChart },
];

const toneClasses = {
  teal: "border-teal/30 bg-teal/5 text-teal",
  blue: "border-blue/30 bg-blue/5 text-blue",
  amber: "border-amber/30 bg-amber/5 text-amber",
  danger: "border-danger/30 bg-danger/5 text-danger",
};

const badgeClasses = {
  red: "bg-red-50 text-red-700",
  amber: "bg-amber-50 text-amber-700",
  blue: "bg-blue-50 text-blue-700",
  green: "bg-teal-50 text-teal-700",
};

function KpiCard({ item }: { item: (typeof kpis)[number] }) {
  return (
    <div className={`rounded-lg border bg-white p-4 shadow-soft ${toneClasses[item.tone as keyof typeof toneClasses]}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase text-muted">{item.label}</div>
          <div className="mt-2 text-2xl font-semibold leading-tight text-ink">{item.value}</div>
        </div>
        <span className="shrink-0 rounded-md bg-white px-2 py-1 text-xs font-semibold shadow-sm">{item.change}</span>
      </div>
      <div className="mt-4 flex h-12 items-end gap-1" aria-hidden="true">
        {item.bars.map((height, index) => (
          <span className="w-full rounded-sm bg-current opacity-40" style={{ height: `${height}%` }} key={`${item.label}-${index}`} />
        ))}
      </div>
    </div>
  );
}

function TrendPanel() {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Sales and returns trend</h2>
          <p className="mt-1 text-sm text-muted">Sample period: Jun 2026</p>
        </div>
        <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-semibold text-ink shadow-sm" type="button">
          <Download className="h-4 w-4" />
          Export
        </button>
      </div>
      <div className="mt-6 h-64 rounded-md border border-line bg-slate-50 p-4">
        <div className="grid h-full grid-cols-12 items-end gap-2">
          {trend.map((height, index) => (
            <div className="flex h-full flex-col justify-end gap-2" key={index}>
              <span className="rounded-t bg-teal" style={{ height: `${height}%` }} />
              <span className="rounded-t bg-amber" style={{ height: `${Math.max(18, 78 - height / 2)}%` }} />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-4 text-xs font-semibold text-muted">
        <span className="inline-flex items-center gap-2"><span className="h-2 w-5 rounded bg-teal" />Sales value</span>
        <span className="inline-flex items-center gap-2"><span className="h-2 w-5 rounded bg-amber" />Return value</span>
      </div>
    </section>
  );
}

function ChannelPanel() {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
      <h2 className="text-base font-semibold text-ink">Marketplace contribution</h2>
      <div className="mt-5 space-y-4">
        {channels.map((channel) => (
          <div key={channel.name}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-semibold text-ink">{channel.name}</span>
              <span className="text-muted">{channel.sales}</span>
            </div>
            <div className="mt-2 h-2 rounded bg-slate-100">
              <div className="h-2 rounded bg-blue" style={{ width: `${channel.value}%` }} />
            </div>
            <div className="mt-1 text-xs text-muted">Returns {channel.returns}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function CategoryPanel() {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-ink">Category matrix</h2>
        <PackageCheck className="h-5 w-5 text-teal" />
      </div>
      <div className="mt-5 space-y-5">
        {categories.map((category) => (
          <div key={category.name}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-semibold text-ink">{category.name}</span>
              <span className="text-muted">{category.revenue}</span>
            </div>
            <div className="mt-2 h-2 rounded bg-slate-100">
              <div className={`h-2 rounded ${category.tone}`} style={{ width: `${category.value}%` }} />
            </div>
            <div className="mt-1 text-xs text-muted">{category.inventory} units</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AlertTable() {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Style risk queue</h2>
          <p className="mt-1 text-sm text-muted">Replenishment and returns exceptions</p>
        </div>
        <AlertTriangle className="h-5 w-5 text-amber" />
      </div>
      <div className="mt-5 overflow-hidden rounded-md border border-line">
        <table className="w-full min-w-[680px] border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-3 font-semibold">Style</th>
              <th className="px-4 py-3 font-semibold">Channel</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">DOI</th>
              <th className="px-4 py-3 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {alerts.map((alert) => (
              <tr className="bg-white" key={alert.style}>
                <td className="px-4 py-3 font-semibold text-ink">{alert.style}</td>
                <td className="px-4 py-3 text-muted">{alert.channel}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${badgeClasses[alert.tone as keyof typeof badgeClasses]}`}>{alert.status}</span>
                </td>
                <td className="px-4 py-3 text-muted">{alert.doi}</td>
                <td className="px-4 py-3 text-muted">{alert.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function DemoDashboardPage() {
  return (
    <main className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-ink text-white">
              <CircleDollarSign className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold uppercase text-muted">E-Commerce BI Platform</div>
              <h1 className="text-xl font-semibold leading-tight text-ink">Executive Overview</h1>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-line bg-slate-50 px-3 py-2 text-sm font-semibold text-muted">
            <ShieldCheck className="h-4 w-4 text-teal" />
            Public demo data
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-5 px-5 py-5 lg:grid-cols-[220px_1fr]">
        <aside className="rounded-lg border border-line bg-white p-3 shadow-soft">
          <nav className="grid gap-1">
            {navItems.map((item, index) => {
              const Icon = item.icon;
              return (
                <a className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-semibold ${index === 0 ? "bg-ink text-white" : "text-muted hover:bg-slate-50 hover:text-ink"}`} href="#" key={item.label}>
                  <Icon className="h-4 w-4" />
                  {item.label}
                </a>
              );
            })}
          </nav>
        </aside>

        <div className="space-y-5">
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {kpis.map((item) => (
              <KpiCard item={item} key={item.label} />
            ))}
          </section>

          <section className="grid gap-5 xl:grid-cols-[1.65fr_1fr]">
            <TrendPanel />
            <ChannelPanel />
          </section>

          <section className="grid gap-5 xl:grid-cols-[1fr_1.35fr]">
            <CategoryPanel />
            <AlertTable />
          </section>
        </div>
      </div>
    </main>
  );
}
