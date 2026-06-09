"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Bell, Bot, Boxes, CircleDollarSign, ClipboardList, Globe2, Layers3, Shield, Tags } from "lucide-react";

const nav = [
  { label: "Executive", href: "/", icon: BarChart3 },
  { label: "Sales", href: "/sales", icon: CircleDollarSign },
  { label: "Inventory", href: "/inventory", icon: Boxes },
  { label: "Categories", href: "/categories", icon: Tags },
  { label: "Ads", href: "/ads", icon: Layers3 },
  { label: "Returns", href: "/returns", icon: ClipboardList },
  { label: "Regional", href: "/regional", icon: Globe2 },
  { label: "Assistant", href: "/assistant", icon: Bot },
  { label: "Reports", href: "/reports", icon: Bell },
  { label: "Admin", href: "/admin", icon: Shield },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-line bg-white px-4 py-5 lg:block">
      <div className="mb-8">
        <div className="text-xl font-semibold text-ink">E-Commerce BI</div>
        <div className="mt-3 rounded border border-line bg-slate-50 px-3 py-3">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Marketplace Intelligence</div>
          <div className="mt-1 text-sm text-muted">Sales, inventory, returns, and alerts</div>
        </div>
        <div className="mt-1 text-xs text-muted">Fashion commerce command center</div>
      </div>
      <nav className="space-y-1">
        {nav.map((item) => {
          const Icon = item.icon;
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              className={`flex items-center gap-3 rounded border-l-2 px-3 py-2 text-sm font-medium transition duration-200 ease-in-out hover:bg-slate-50 hover:text-ink ${
                active ? "border-l-teal bg-teal/5 text-ink" : "border-l-transparent text-muted"
              }`}
              href={item.href}
              key={item.href}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
