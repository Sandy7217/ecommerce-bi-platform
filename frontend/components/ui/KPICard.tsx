"use client";

import CountUp from "react-countup";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip } from "recharts";

import { formatINR, formatNumber, formatQty, pct } from "@/lib/formatters";

type KPICardProps = {
  title: string;
  value: number | string;
  format?: (value: number) => string;
  formatType?: "inr" | "qty" | "pct" | "number";
  trend?: number;
  trendDirection?: "higher-is-good" | "lower-is-good";
  trendUnit?: "%" | "pp";
  alert?: "green" | "orange" | "red";
  sparkline?: number[];
  delay?: number;
};

const alertClasses = {
  green: "border-teal/30 bg-teal/5 border-l-teal",
  orange: "border-amber/30 bg-amber/5 border-l-amber",
  red: "border-danger/30 bg-danger/5 border-l-danger",
};

const formatters = {
  inr: formatINR,
  qty: formatQty,
  pct,
  number: formatNumber,
};

export function KPICard({ title, value, format, formatType = "number", trend, trendDirection = "higher-is-good", trendUnit = "%", alert = "green", sparkline = [], delay = 0 }: KPICardProps) {
  const TrendIcon = (trend ?? 0) >= 0 ? ArrowUpRight : ArrowDownRight;
  const favorableTrend = trendDirection === "lower-is-good" ? (trend ?? 0) <= 0 : (trend ?? 0) >= 0;
  const trendClass = favorableTrend ? "text-teal" : "text-danger";
  const numericValue = typeof value === "number" ? value : 0;
  const formatter = format ?? formatters[formatType];
  const points = sparkline.length ? sparkline.map((item, index) => ({ index, value: item })) : [0, numericValue * 0.72, numericValue * 0.88, numericValue].map((item, index) => ({ index, value: item }));
  const valueClass = typeof value === "string" && value.length > 12 ? "break-all text-xl leading-tight" : "break-words text-2xl leading-tight";

  return (
    <motion.div
      className={`rounded-lg border border-l-4 p-4 shadow-soft transition duration-200 ease-in-out hover:scale-[1.02] ${alertClasses[alert]}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      title={`${title}: ${typeof value === "number" ? formatter(value) : value}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-medium uppercase tracking-wide text-muted">{title}</div>
        </div>
        <div className="h-10 w-16 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points}>
              <Tooltip contentStyle={{ display: "none" }} cursor={false} />
              <Line type="monotone" dataKey="value" stroke={alert === "red" ? "#dc2626" : alert === "orange" ? "#d97706" : "#0f9488"} strokeWidth={2} dot={false} isAnimationActive />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className={`mt-3 font-semibold text-ink ${valueClass}`}>
        {typeof value === "number" ? <CountUp end={Number.isFinite(value) ? value : 0} duration={1.5} formattingFn={formatter} /> : value}
      </div>
      {typeof trend === "number" ? (
        <div className={`mt-3 flex items-center gap-1 text-xs font-medium ${trendClass}`}>
          <TrendIcon className="h-4 w-4" />
          {Math.abs(trend).toFixed(1)}{trendUnit} vs same period
        </div>
      ) : null}
    </motion.div>
  );
}
