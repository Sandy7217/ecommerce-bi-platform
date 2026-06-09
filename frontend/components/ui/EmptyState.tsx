import { Inbox } from "lucide-react";

export function EmptyState({ title = "No data available", body = "Upload or refresh data to populate this section." }: { title?: string; body?: string }) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center rounded-lg border border-dashed border-line bg-white p-8 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-muted">
        <Inbox className="h-7 w-7" />
      </div>
      <div className="mt-4 text-sm font-semibold text-ink">{title}</div>
      <div className="mt-1 max-w-sm text-sm text-muted">{body}</div>
    </div>
  );
}
