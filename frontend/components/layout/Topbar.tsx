"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Bell, CalendarDays, Database, LogOut, UserCircle } from "lucide-react";

import { apiGet, type AlertsCount } from "@/lib/api";
import { DATE_RANGE_PRESETS, presetDateRange, resolveDateRange, type DateRangePreset, type DateRangeValue } from "@/lib/dateRange";

const labels: Record<string, string> = {
  "/": "Executive Summary",
  "/sales": "Sales",
  "/inventory": "Inventory",
  "/categories": "Categories",
  "/ads": "Ads",
  "/returns": "Returns",
  "/regional": "Regional",
  "/assistant": "Assistant",
  "/reports": "Reports",
  "/admin": "Admin",
  "/admin/upload": "Upload Center",
  "/admin/users": "User Management",
  "/admin/settings": "Settings",
};

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [syncedAt, setSyncedAt] = useState(new Date());
  const [now, setNow] = useState(new Date());
  const [alerts, setAlerts] = useState<AlertsCount>({ count: 0, oos_count: 0, p0_p1_count: 0 });
  const [accountLabel, setAccountLabel] = useState("Account");
  const title = labels[pathname] ?? labels[`/${pathname.split("/")[1]}`] ?? "E-Commerce BI";
  const minutes = Math.max(0, Math.floor((now.getTime() - syncedAt.getTime()) / 60000));
  const dot = minutes <= 5 ? "bg-teal" : minutes <= 30 ? "bg-amber" : "bg-danger";
  const alertCount = alerts.count || 0;
  const dateRange = useMemo(() => {
    const params: Record<string, string> = {};
    searchParams.forEach((value, key) => {
      params[key] = value;
    });
    return resolveDateRange(params);
  }, [searchParams]);
  const [customFrom, setCustomFrom] = useState(dateRange.fromDate);
  const [customTo, setCustomTo] = useState(dateRange.toDate);

  useEffect(() => {
    apiGet<AlertsCount>("/alerts/count")
      .then((data) => {
        setAlerts(data);
        setSyncedAt(new Date());
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        const email = data?.user?.email;
        if (email) setAccountLabel(email.split("@")[0] || "Account");
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setCustomFrom(dateRange.fromDate);
    setCustomTo(dateRange.toDate);
  }, [dateRange.fromDate, dateRange.toDate]);

  const breadcrumb = useMemo(() => (pathname === "/" ? ["Executive"] : pathname.split("/").filter(Boolean).map((part) => part[0].toUpperCase() + part.slice(1))), [pathname]);

  function pushRange(range: DateRangeValue) {
    const next = new URLSearchParams(searchParams.toString());
    next.set("range", range.preset);
    next.set("from_date", range.fromDate);
    next.set("to_date", range.toDate);
    router.push(`${pathname}?${next.toString()}`, { scroll: false });
  }

  function handlePresetChange(value: string) {
    const preset = value as DateRangePreset;
    if (preset === "custom") {
      pushRange({ preset, fromDate: customFrom || dateRange.fromDate, toDate: customTo || dateRange.toDate });
      return;
    }
    pushRange(presetDateRange(preset as Exclude<DateRangePreset, "custom">));
  }

  function handleCustomDate(field: "from" | "to", value: string) {
    const fromDate = field === "from" ? value : customFrom;
    const toDate = field === "to" ? value : customTo;
    if (field === "from") setCustomFrom(value);
    if (field === "to") setCustomTo(value);
    if (fromDate && toDate) {
      pushRange({ preset: "custom", fromDate, toDate });
    }
  }

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    window.location.replace("/login");
  }

  return (
    <header className="sticky top-0 z-10 border-b border-line bg-white/90 px-6 py-4 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs text-muted">{breadcrumb.join(" / ")}</div>
          <div className="mt-1 text-sm font-semibold text-ink">{title}</div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 text-xs sm:w-auto sm:text-sm">
          <div className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-muted">
            <CalendarDays className="h-4 w-4" />
            <select
              aria-label="Date range"
              className="bg-transparent text-sm text-muted outline-none"
              onChange={(event) => handlePresetChange(event.target.value)}
              value={dateRange.preset}
            >
              {DATE_RANGE_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </select>
          </div>
          {dateRange.preset === "custom" ? (
            <div className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-muted">
              <input aria-label="From date" className="w-32 bg-transparent text-sm outline-none" onChange={(event) => handleCustomDate("from", event.target.value)} type="date" value={customFrom} />
              <input aria-label="To date" className="w-32 bg-transparent text-sm outline-none" onChange={(event) => handleCustomDate("to", event.target.value)} type="date" value={customTo} />
            </div>
          ) : null}
          <div className="inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-muted">
            <span className={`h-2 w-2 rounded-full ${dot}`} />
            Last synced: {minutes} mins ago
          </div>
          <button className="relative inline-flex items-center gap-2 rounded border border-line px-3 py-2 text-muted transition duration-200 ease-in-out hover:scale-[1.02]" type="button">
            <Bell className="h-4 w-4" />
            Alerts
            <span className="absolute -right-2 -top-2 rounded-full bg-danger px-1.5 py-0.5 text-[10px] font-semibold text-white">{alertCount}</span>
          </button>
          <button className="hidden items-center gap-2 rounded border border-line px-3 py-2 text-muted transition duration-200 ease-in-out hover:scale-[1.02] sm:inline-flex" type="button">
            <Database className="h-4 w-4" />
            Synced
          </button>
          <button className="hidden items-center gap-2 rounded bg-ink px-3 py-2 text-white transition duration-200 ease-in-out hover:scale-[1.02] sm:inline-flex" type="button">
            <UserCircle className="h-4 w-4" />
            {accountLabel}
          </button>
          <button
            className="hidden items-center gap-2 rounded border border-line px-3 py-2 text-muted transition duration-200 ease-in-out hover:scale-[1.02] sm:inline-flex"
            onClick={handleLogout}
            type="button"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
