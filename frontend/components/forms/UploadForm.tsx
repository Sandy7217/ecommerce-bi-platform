"use client";

import { useRef, useState } from "react";
import { Loader2, Upload } from "lucide-react";
import toast from "react-hot-toast";

import { DIRECT_API_ROOT } from "@/lib/api";
import { formatNumber } from "@/lib/formatters";

type UploadFormProps = {
  label: string;
  endpoint?: string;
  description?: string;
  lastUpload?: string | null;
  rowsProcessed?: number;
  cadence?: "daily" | "weekly" | "one_time";
  statusText?: string;
  fileFields?: { name: string; label: string }[];
};

function lastUploadedText(value?: string | null) {
  if (!value) return "Never";
  const date = new Date(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return `Today ${new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" }).format(date)}`;
  }
  const diffDays = Math.max(1, Math.floor((now.getTime() - date.getTime()) / 86400000));
  if (diffDays === 1) return "Yesterday";
  return `${diffDays} days ago`;
}

function uploadedToday(value?: string | null) {
  return value ? new Date(value).toDateString() === new Date().toDateString() : false;
}

function statusFor(cadence: UploadFormProps["cadence"], lastUpload?: string | null) {
  if (cadence === "daily") {
    return uploadedToday(lastUpload)
      ? { dotClassName: "bg-teal", text: "Uploaded today", className: "bg-teal/10 text-teal" }
      : { dotClassName: "bg-danger", text: "Pending today", className: "bg-danger/10 text-danger" };
  }
  return { dotClassName: "bg-slate-400", text: cadence === "weekly" ? "Weekly upload" : "One-time / monthly", className: "bg-slate-100 text-muted" };
}

export function UploadForm({
  label,
  endpoint,
  description,
  lastUpload,
  rowsProcessed = 0,
  cadence = "daily",
  statusText,
  fileFields,
}: UploadFormProps) {
  const [processing, setProcessing] = useState(false);
  const fields = fileFields ?? [{ name: "file", label: "File" }];
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [summary, setSummary] = useState<string | null>(null);
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const status = statusFor(cadence, lastUpload);

  async function getAccessToken() {
    const response = await fetch("/api/auth/token", { cache: "no-store" });
    if (!response.ok) throw new Error("Authentication required");
    const payload = (await response.json()) as { access_token?: string };
    if (!payload.access_token) throw new Error("Authentication required");
    return payload.access_token;
  }

  async function submitUpload(nextFiles = files) {
    if (!endpoint) return;
    const missingField = fields.find((field) => !nextFiles[field.name]);
    if (missingField) {
      inputRefs.current[missingField.name]?.click();
      return;
    }
    setProcessing(true);
    setSummary(null);
    try {
      const formData = new FormData();
      fields.forEach((field) => {
        const file = nextFiles[field.name];
        if (file) formData.append(field.name, file);
      });
      const accessToken = await getAccessToken();
      const response = await fetch(`${DIRECT_API_ROOT}${endpoint}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json();
      const inserted = Number(result.rows_inserted ?? result.rows_updated ?? 0);
      const processed = Number(result.rows_processed ?? 0);
      setSummary(`Processed ${formatNumber(processed)}, inserted ${formatNumber(inserted)}`);
      toast.success(`${label} uploaded: ${formatNumber(inserted)} rows inserted`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <form className="rounded-lg border border-line bg-white p-4 shadow-soft transition duration-200 ease-in-out hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ink">{label}</div>
          {description ? <div className="mt-1 max-w-xl text-xs leading-5 text-muted">{description}</div> : null}
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium ${status.className}`}>
            <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${status.dotClassName}`} />
            {statusText || status.text}
          </div>
          <div className="rounded border border-line bg-slate-50 px-2 py-1 text-[11px] text-muted">Last uploaded: {lastUploadedText(lastUpload)}</div>
          <div className="rounded border border-line bg-slate-50 px-2 py-1 text-[11px] text-muted">Rows processed: {formatNumber(rowsProcessed)}</div>
        </div>
      </div>

      <div className="mt-4 grid gap-2">
        {fields.map((field) => (
          <div className="flex items-center justify-between gap-3 rounded border border-line bg-slate-50 px-3 py-2 text-xs" key={field.name}>
            <div>
              <div className="font-medium text-ink">{field.label}</div>
              <div className="mt-0.5 text-muted">{files[field.name]?.name || "No file selected"}</div>
            </div>
            <button
              className="rounded border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink transition duration-200 ease-in-out hover:scale-[1.02]"
              onClick={() => inputRefs.current[field.name]?.click()}
              type="button"
            >
              Choose
            </button>
            <input
              ref={(element) => {
                inputRefs.current[field.name] = element;
              }}
              className="hidden"
              type="file"
              onChange={(event) => {
                const selected = event.target.files?.[0] ?? null;
                const nextFiles = { ...files, [field.name]: selected };
                setFiles(nextFiles);
                if (fields.length === 1 && selected) {
                  void submitUpload(nextFiles);
                }
              }}
            />
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        {processing ? (
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full w-2/3 animate-pulse rounded-full bg-teal" />
          </div>
        ) : (
          <div className="text-xs text-muted">{fields.length === 1 ? "Upload starts after file selection." : "Select both files before uploading."}</div>
        )}
        <button
          className="inline-flex items-center gap-2 rounded bg-ink px-4 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02] disabled:opacity-60"
          disabled={processing}
          onClick={() => submitUpload()}
          type="button"
        >
          {processing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          {processing ? "Uploading" : fields.length === 1 && !files[fields[0].name] ? "Upload" : "Upload selected"}
        </button>
      </div>
      {summary ? <div className="mt-3 rounded border border-line bg-slate-50 px-3 py-2 text-xs text-muted">{summary}</div> : null}
    </form>
  );
}
