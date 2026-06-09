"use client";

import { X } from "lucide-react";

type ConfirmModalProps = {
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
};

export function ConfirmModal({ open, title, body, confirmLabel, onConfirm, onClose }: ConfirmModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 px-4">
      <div className="w-full max-w-md rounded-lg border border-line bg-white p-5 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-base font-semibold text-ink">{title}</div>
            <div className="mt-2 text-sm text-muted">{body}</div>
          </div>
          <button className="rounded p-1 text-muted transition duration-200 ease-in-out hover:bg-slate-100 hover:text-ink" onClick={onClose} type="button">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button className="rounded border border-line px-4 py-2 text-sm font-medium text-muted transition duration-200 ease-in-out hover:scale-[1.02]" onClick={onClose} type="button">
            Cancel
          </button>
          <button className="rounded bg-ink px-4 py-2 text-sm font-medium text-white transition duration-200 ease-in-out hover:scale-[1.02]" onClick={onConfirm} type="button">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
