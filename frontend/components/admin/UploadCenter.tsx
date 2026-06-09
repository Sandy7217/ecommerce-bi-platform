"use client";

import { UploadForm } from "@/components/forms/UploadForm";

export type UploadRow = {
  file_name?: string;
  file_type?: string;
  upload_type?: string;
  rows_processed?: number;
  rows_inserted?: number;
  status?: string;
  created_at?: string;
};

type UploadItem = {
  label: string;
  description: string;
  endpoint: string;
  type: string;
  cadence: "daily" | "weekly" | "one_time";
  fileFields?: { name: string; label: string }[];
};

type UploadGroup = {
  title: string;
  note: string;
  items: UploadItem[];
};

const uploadGroups: UploadGroup[] = [
  {
    title: "Daily uploads",
    note: "Refresh these files every day before reviewing dashboard actions.",
    items: [
      {
        label: "Myntra Orders",
        description: "Seller orders report from Myntra.",
        endpoint: "/upload/auto_detect",
        type: "myntra_orders",
        cadence: "daily",
      },
      {
        label: "Unicommerce Sales",
        description: "Current Unicommerce sale orders. Myntra channel rows are excluded from sales calculations.",
        endpoint: "/upload/auto_detect",
        type: "unicommerce",
        cadence: "daily",
      },
      {
        label: "Inventory Snapshot",
        description: "Long-format inventory snapshot with SKU, size, color, and inventory quantity.",
        endpoint: "/upload/auto_detect",
        type: "inventory",
        cadence: "daily",
      },
      {
        label: "Returns",
        description: "Returns report for current return tracking and date-range return percentage.",
        endpoint: "/upload/auto_detect",
        type: "returns",
        cadence: "daily",
      },
    ],
  },
  {
    title: "Weekly uploads",
    note: "Refresh weekly or whenever new marketplace reports are available.",
    items: [
      {
        label: "PLA Report",
        description: "Myntra PLA performance report with spend, clicks, revenue, and ROI metrics.",
        endpoint: "/upload/auto_detect",
        type: "pla",
        cadence: "weekly",
      },
      {
        label: "Visibility Report",
        description: "Visibility and conversion report for list page, PDP, ROS, and return-rate analysis.",
        endpoint: "/upload/auto_detect",
        type: "visibility",
        cadence: "weekly",
      },
    ],
  },
  {
    title: "One-time / monthly uploads",
    note: "Use when mappings or grade master files change.",
    items: [
      {
        label: "SKU Mapping",
        description: "Two-file mapping upload. Requires seller listings plus channel item type report.",
        endpoint: "/upload/sku_mapping",
        type: "sku_mapping",
        cadence: "one_time",
        fileFields: [
          { name: "listing_file", label: "Seller listings report" },
          { name: "channel_item_file", label: "Channel item type report" },
        ],
      },
      {
        label: "Sale Grade Master",
        description: "Monthly sale-grade refresh. Updates sale_grade_old and rebuilds categories.",
        endpoint: "/upload/auto_detect",
        type: "sale_grade_master",
        cadence: "one_time",
      },
      {
        label: "Manual Replenishment",
        description: "Manual replenishment sheet with SKU and Manual Replenishment Qty columns.",
        endpoint: "/upload/replenishment",
        type: "replenishment",
        cadence: "one_time",
      },
    ],
  },
];

export function UploadCenter({ uploadLog }: { uploadLog: UploadRow[] }) {
  const lastByType = new Map<string, UploadRow>();
  [...uploadLog]
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .forEach((row) => {
      const type = row.file_type || row.upload_type;
      if (type && row.created_at && !lastByType.has(type)) {
        lastByType.set(type, row);
      }
    });

  return (
    <section className="space-y-4">
      <div>
        <div className="text-sm font-semibold text-ink">Upload Center</div>
        <div className="mt-1 text-xs text-muted">Daily, weekly, and mapping inputs for dashboard refresh.</div>
      </div>
      {uploadGroups.map((group) => (
        <div className="rounded-lg border border-line bg-white p-4 shadow-soft" key={group.title}>
          <div className="mb-4">
            <div className="text-sm font-semibold text-ink">{group.title}</div>
            <div className="mt-1 text-xs text-muted">{group.note}</div>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            {group.items.map((upload) => {
              const lastUpload = lastByType.get(upload.type);
              return (
                <UploadForm
                  key={upload.label}
                  label={upload.label}
                  endpoint={upload.endpoint}
                  description={upload.description}
                  lastUpload={lastUpload?.created_at}
                  rowsProcessed={Number(lastUpload?.rows_processed || 0)}
                  cadence={upload.cadence}
                  fileFields={upload.fileFields}
                />
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}
