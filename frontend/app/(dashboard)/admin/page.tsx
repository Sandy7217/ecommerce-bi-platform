"use client";

import Link from "next/link";

import { UploadCenter, type UploadRow } from "@/components/admin/UploadCenter";
import type { UserRow } from "@/components/admin/UserManagement";
import { RoleGuard } from "@/components/layout/RoleGuard";
import { Badge } from "@/components/ui/Badge";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { KPICard } from "@/components/ui/KPICard";
import { formatDate, formatNumber } from "@/lib/formatters";
import { useApiData } from "@/lib/useApiData";

type PipelineStatus = {
  status: string;
  last_refresh?: string | null;
  uploads: UploadRow[];
};

export default function AdminPage() {
  const users = useApiData<UserRow[]>("/admin/users", []);
  const uploads = useApiData<UploadRow[]>("/admin/upload_log", []);
  const pipeline = useApiData<PipelineStatus>("/admin/pipeline_status", { status: "unknown", last_refresh: null, uploads: [] });
  const error = users.error || uploads.error || pipeline.error;

  const activeUsers = users.data.filter((row) => row.is_active !== false).length;

  if (error) return <ErrorState message={error} onRetry={() => { users.retry(); uploads.retry(); pipeline.retry(); }} />;

  return (
    <RoleGuard access="admin">
      <div className="w-full space-y-6">
        <div className="grid gap-3 md:grid-cols-3">
          <Link className="rounded-lg border border-line bg-ink p-4 text-white shadow-soft transition duration-200 ease-in-out hover:scale-[1.01]" href="/admin/upload">
            <div className="text-sm font-semibold">Upload center</div>
            <div className="mt-1 text-xs text-white/75">Daily, weekly, and mapping data inputs.</div>
          </Link>
          <Link className="rounded-lg border border-line bg-white p-4 text-ink shadow-soft transition duration-200 ease-in-out hover:scale-[1.01]" href="/admin/users">
            <div className="text-sm font-semibold">User management</div>
            <div className="mt-1 text-xs text-muted">Invites, roles, active status, and deletion.</div>
          </Link>
          <Link className="rounded-lg border border-line bg-white p-4 text-ink shadow-soft transition duration-200 ease-in-out hover:scale-[1.01]" href="/admin/settings">
            <div className="text-sm font-semibold">Settings</div>
            <div className="mt-1 text-xs text-muted">Alert thresholds and operational defaults.</div>
          </Link>
        </div>

        <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-5">
          <KPICard title="Users" value={users.data.length} format={formatNumber} delay={0} />
          <KPICard title="Active Users" value={activeUsers} format={formatNumber} delay={0.1} />
          <KPICard title="Uploads" value={uploads.data.length} format={formatNumber} delay={0.2} />
          <KPICard title="Pipeline" value={pipeline.data.status} alert={pipeline.data.status === "ready" ? undefined : "orange"} delay={0.3} />
          <KPICard title="Last Refresh" value={pipeline.data.last_refresh ? formatDate(pipeline.data.last_refresh) : "NA"} delay={0.4} />
        </section>

        <UploadCenter uploadLog={uploads.data} />

        <section className="min-w-0 rounded-lg border border-line bg-white p-4 shadow-soft">
          <div className="mb-4 text-sm font-semibold text-ink">Upload log</div>
          <DataTable
            rows={uploads.data}
            rowKey={(row, index) => `${row.file_name || row.upload_type || "upload"}-${index}`}
            empty={<EmptyState title="No upload log rows" />}
            minWidth="760px"
            columns={[
              { key: "file_name", label: "File", sortable: true, render: (row) => row.file_name || "Upload" },
              { key: "file_type", label: "Type", sortable: true, render: (row) => row.file_type || row.upload_type || "Unknown" },
              { key: "rows_processed", label: "Processed", sortable: true, align: "right", render: (row) => formatNumber(Number(row.rows_processed || 0)) },
              { key: "rows_inserted", label: "Inserted", sortable: true, align: "right", render: (row) => formatNumber(Number(row.rows_inserted || 0)) },
              { key: "status", label: "Status", sortable: true, render: (row) => <Badge tone={row.status === "success" ? "green" : "neutral"}>{row.status || "Unknown"}</Badge> },
            ]}
          />
        </section>
      </div>
    </RoleGuard>
  );
}
