"use client";

import { useMemo, useState } from "react";
import toast from "react-hot-toast";

import { Badge, statusTone } from "@/components/ui/Badge";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { MotionPanel } from "@/components/ui/PageTransition";
import { apiPost, type InventoryStyle, type Paginated } from "@/lib/api";
import { formatNumber } from "@/lib/formatters";
import { useApiData } from "@/lib/useApiData";

type PotentialNoos = InventoryStyle & {
  category_new?: string;
  ros_7d?: number;
  total_inventory?: number;
  inventory_status?: string;
};

type OverrideRow = {
  style_color: string;
  override_category: string;
  override_by?: string;
  override_date?: string;
  notes?: string;
};

export default function CategoriesPage() {
  const potential = useApiData<Paginated<PotentialNoos>>("/categories/potential_noos?limit=100", { items: [], page: 1, limit: 100, total: 0 });
  const cross = useApiData<Record<string, Record<string, number>>>("/categories/cross_analysis", {});
  const overrides = useApiData<OverrideRow[]>("/categories/overrides", []);
  const styles = useApiData<Paginated<InventoryStyle>>("/inventory/styles?limit=200", { items: [], page: 1, limit: 200, total: 0 });
  const [selected, setSelected] = useState<string[]>([]);
  const [modal, setModal] = useState<{ type: "noos" | "discontinue"; styles: string[] } | null>(null);
  const [search, setSearch] = useState("");
  const error = potential.error || cross.error || overrides.error || styles.error;
  const retry = () => {
    potential.retry();
    cross.retry();
    overrides.retry();
    styles.retry();
  };

  const crossRows = useMemo(() => {
    const newCategories = Array.from(new Set(Object.values(cross.data).flatMap((row) => Object.keys(row)))).sort();
    return {
      columns: [
        { key: "old", label: "Old sale grade", sortable: true },
        ...newCategories.map((category) => ({ key: category, label: category, sortable: true, align: "right" as const })),
      ],
      rows: Object.entries(cross.data).map(([old, values]) => ({ old, ...values })),
    };
  }, [cross.data]);

  const discontinueRows = styles.data.items.filter((row) => !search || row.style_color.toLowerCase().includes(search.toLowerCase())).slice(0, 50);

  const submitOverride = async () => {
    if (!modal?.styles.length) return;
    const path = modal.type === "noos" ? "/categories/approve_noos" : "/categories/mark_discontinue";
    try {
      await apiPost(path, { style_colors: modal.styles, override_by: "MD", notes: "Dashboard action" });
      toast.success(modal.type === "noos" ? "NOOS approval saved" : "Discontinue override saved");
      setSelected([]);
      setModal(null);
      overrides.retry();
      potential.retry();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed");
    }
  };

  if (error) return <ErrorState message={error} onRetry={retry} />;

  return (
    <div className="w-full space-y-6">
      <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm font-semibold text-ink">Potential NOOS approval queue</div>
          <button
            className="rounded bg-teal px-4 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-50"
            disabled={!selected.length}
            onClick={() => setModal({ type: "noos", styles: selected })}
            type="button"
          >
            Approve Selected
          </button>
        </div>
        <DataTable
          rows={potential.data.items}
          rowKey={(row) => row.style_color}
          empty={<EmptyState title="No potential NOOS approvals" />}
          minWidth="920px"
          columns={[
            {
              key: "select",
              label: "",
              render: (row) => (
                <input
                  checked={selected.includes(row.style_color)}
                  onChange={(event) => setSelected((current) => (event.target.checked ? [...current, row.style_color] : current.filter((item) => item !== row.style_color)))}
                  type="checkbox"
                />
              ),
            },
            { key: "style_color", label: "Style Color", sortable: true, copy: true },
            { key: "category_new", label: "Current Category", sortable: true, render: (row) => row.category_new || "Unknown" },
            { key: "ros_30d", label: "ROS 30d", sortable: true, align: "right" },
            { key: "ros_7d", label: "ROS 7d", sortable: true, align: "right", render: (row) => row.ros_7d ?? 0 },
            { key: "total_inventory", label: "Total Inventory", sortable: true, align: "right", render: (row) => formatNumber(row.total_inventory || 0) },
            { key: "inventory_status", label: "Status", sortable: true, render: (row) => <Badge tone={statusTone(row.inventory_status || row.status)}>{row.inventory_status || row.status || "UNKNOWN"}</Badge> },
            {
              key: "actions",
              label: "Actions",
              render: (row) => (
                <div className="flex gap-2">
                  <button className="rounded bg-teal px-3 py-2 text-xs font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02]" onClick={() => setModal({ type: "noos", styles: [row.style_color] })} type="button">
                    Confirm NOOS
                  </button>
                  <button className="rounded border border-line px-3 py-2 text-xs font-medium text-muted transition duration-200 ease-in-out hover:scale-[1.02]" onClick={() => toast.success(`Skipped ${row.style_color}`)} type="button">
                    Skip
                  </button>
                </div>
              ),
            },
          ]}
        />
      </MotionPanel>

      <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
        <div className="mb-4 text-sm font-semibold text-ink">Category cross analysis</div>
        <DataTable rows={crossRows.rows} columns={crossRows.columns} rowKey={(row) => String(row.old)} empty={<EmptyState title="No cross analysis" />} maxHeight="520px" minWidth="780px" />
      </MotionPanel>

      <section className="grid min-w-0 gap-4 xl:grid-cols-[1fr_1fr]">
        <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
          <div className="mb-4 text-sm font-semibold text-ink">Override history log</div>
          <DataTable
            rows={overrides.data}
            rowKey={(row, index) => `${row.style_color}-${index}`}
            empty={<EmptyState title="No override history" />}
            columns={[
              { key: "style_color", label: "Style", sortable: true, copy: true },
              { key: "override_category", label: "Override Category", sortable: true },
              { key: "override_by", label: "Override By", sortable: true },
              { key: "override_date", label: "Date", sortable: true },
              { key: "notes", label: "Notes" },
            ]}
          />
        </MotionPanel>

        <MotionPanel className="min-w-0 w-full rounded-lg border border-line bg-white p-4 shadow-soft">
          <div className="mb-4 text-sm font-semibold text-ink">Discontinue management</div>
          <input className="mb-4 w-full rounded border border-line px-3 py-2 text-sm" onChange={(event) => setSearch(event.target.value)} placeholder="Search styles" value={search} />
          <DataTable
            rows={discontinueRows}
            rowKey={(row) => row.style_color}
            empty={<EmptyState title="No styles found" />}
            minWidth="620px"
            columns={[
              { key: "style_color", label: "Style", sortable: true, copy: true },
              { key: "category_new", label: "Category", sortable: true, render: (row) => row.category_new || "Unknown" },
              { key: "status", label: "Status", sortable: true, render: (row) => <Badge tone={statusTone(row.status || row.inventory_status)}>{row.status || row.inventory_status || "UNKNOWN"}</Badge> },
              {
                key: "action",
                label: "Action",
                render: (row) => (
                  <button className="rounded bg-ink px-3 py-2 text-xs font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02]" onClick={() => setModal({ type: "discontinue", styles: [row.style_color] })} type="button">
                    Mark discontinue
                  </button>
                ),
              },
            ]}
          />
        </MotionPanel>
      </section>

      <ConfirmModal
        open={Boolean(modal)}
        title={modal?.type === "noos" ? "Confirm NOOS approval" : "Mark as discontinue"}
        body={`This will submit ${modal?.styles.length ?? 0} style override${(modal?.styles.length ?? 0) === 1 ? "" : "s"}.`}
        confirmLabel={modal?.type === "noos" ? "Confirm NOOS" : "Mark Discontinue"}
        onClose={() => setModal(null)}
        onConfirm={submitOverride}
      />
    </div>
  );
}
