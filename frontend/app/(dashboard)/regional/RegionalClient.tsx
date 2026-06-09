"use client";

import { useMemo, useState } from "react";

import { IndiaMap } from "@/components/charts/IndiaMap";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { KPICard } from "@/components/ui/KPICard";
import { MotionPanel } from "@/components/ui/PageTransition";
import { exactINR, formatINR, formatNumber, pct } from "@/lib/formatters";
import type { RegionalHeatmapState } from "@/lib/api";

export function RegionalClient({ states }: { states: RegionalHeatmapState[] }) {
  const [selectedState, setSelectedState] = useState("all");
  const stateOptions = useMemo(() => Array.from(new Set(states.map((row) => row.state))).sort((a, b) => a.localeCompare(b)), [states]);
  const filteredStates = useMemo(
    () => (selectedState === "all" ? states : states.filter((row) => row.state === selectedState)),
    [selectedState, states],
  );
  const totalSales = filteredStates.reduce((sum, row) => sum + Number(row.sales || 0), 0);
  const totalQty = filteredStates.reduce((sum, row) => sum + Number(row.qty || 0), 0);
  const totalReturns = filteredStates.reduce((sum, row) => sum + Number(row.return_qty || 0), 0);
  const regionalReturnPct = totalQty ? (totalReturns * 100) / totalQty : 0;
  const topState = selectedState === "all" ? states[0]?.state || "NA" : selectedState;

  return (
    <div className="w-full space-y-6">
      <section className="flex flex-wrap items-end justify-between gap-3 rounded-lg border border-line bg-white p-4 shadow-soft">
        <div>
          <div className="text-sm font-semibold text-ink">Regional filter</div>
        </div>
        <label className="flex min-w-[260px] flex-col gap-1 text-xs font-medium uppercase tracking-wide text-muted">
          State
          <select
            className="h-11 rounded border border-line bg-white px-3 text-sm font-medium normal-case tracking-normal text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
            onChange={(event) => setSelectedState(event.target.value)}
            value={selectedState}
          >
            <option value="all">All states</option>
            {stateOptions.map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-5">
        <KPICard title="Regional Sales" value={totalSales} format={formatINR} delay={0} />
        <KPICard title="Regional Qty" value={totalQty} format={formatNumber} delay={0.1} />
        <KPICard title="Return Qty" value={totalReturns} format={formatNumber} alert="orange" delay={0.2} />
        <KPICard title="Top State" value={topState} delay={0.3} />
        <KPICard title="Return %" value={regionalReturnPct} format={pct} alert="red" delay={0.4} />
      </section>

      <section className="grid min-w-0 items-start gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        {filteredStates.length ? <IndiaMap data={filteredStates} /> : <EmptyState title="No regional sales" />}
        <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
          <div className="mb-4 text-sm font-semibold text-ink">State contribution</div>
          <DataTable
            rows={filteredStates}
            rowKey={(row) => row.state}
            empty={<EmptyState title="No state rows" />}
            minWidth="760px"
            columns={[
              { key: "state", label: "State", sortable: true },
              { key: "sales", label: "Sales", sortable: true, align: "right", render: (row) => exactINR(row.sales) },
              { key: "qty", label: "Qty", sortable: true, align: "right", render: (row) => formatNumber(row.qty) },
              { key: "return_qty", label: "Return Qty", sortable: true, align: "right", render: (row) => formatNumber(row.return_qty) },
              { key: "return_pct", label: "Return %", sortable: true, align: "right", render: (row) => pct(row.return_pct) },
              {
                key: "top_styles",
                label: "Top Styles",
                render: (row) => row.top_styles?.slice(0, 2).map((item) => item.style_color).join(", ") || "NA",
              },
            ]}
          />
        </MotionPanel>
      </section>
    </div>
  );
}
