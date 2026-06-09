"use client";

import { Check, X } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import type { InventoryStyle } from "@/lib/api";

export function CategoryApproval({ rows = [], onConfirm, onSkip }: { rows?: InventoryStyle[]; onConfirm?: (style: string) => void; onSkip?: (style: string) => void }) {
  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-4 text-sm font-semibold text-ink">Potential NOOS queue</div>
      <div className="space-y-3">
        {rows.map((row) => (
          <div className="flex items-center justify-between rounded border border-line p-3" key={row.style_color}>
            <div>
              <div className="font-medium text-ink">{row.style_color}</div>
              <div className="mt-1 flex gap-2 text-xs text-muted">
                <Badge tone="blue">ROS 7d {(row as any).ros_7d ?? 0}</Badge>
                <Badge tone="green">ROS 30d {row.ros_30d ?? 0}</Badge>
              </div>
            </div>
            <div className="flex gap-2">
              <button className="rounded bg-teal px-3 py-2 text-white transition duration-200 ease-in-out hover:scale-[1.02]" onClick={() => onConfirm?.(row.style_color)} type="button" aria-label="Confirm NOOS">
                <Check className="h-4 w-4" />
              </button>
              <button className="rounded border border-line px-3 py-2 text-muted transition duration-200 ease-in-out hover:scale-[1.02]" onClick={() => onSkip?.(row.style_color)} type="button" aria-label="Reject">
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
