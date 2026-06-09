import type { ReactNode } from "react";

type BadgeProps = {
  children: ReactNode;
  tone?: "neutral" | "green" | "amber" | "red" | "blue";
};

const tones = {
  neutral: "bg-slate-100 text-slate-700",
  green: "bg-teal-50 text-teal-700",
  amber: "bg-amber-50 text-amber-700",
  red: "bg-red-50 text-red-700",
  blue: "bg-blue-50 text-blue-700",
};

export function Badge({ children, tone = "neutral" }: BadgeProps) {
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>;
}

export function statusTone(status?: string): BadgeProps["tone"] {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "INSTOCK") return "green";
  if (normalized === "BROKEN") return "amber";
  if (normalized === "OOS") return "red";
  return "neutral";
}

export function priorityTone(priority?: string): BadgeProps["tone"] {
  const normalized = String(priority || "").toUpperCase();
  if (normalized.startsWith("P0")) return "red";
  if (normalized.startsWith("P1")) return "amber";
  if (normalized.startsWith("P2")) return "blue";
  return "neutral";
}
