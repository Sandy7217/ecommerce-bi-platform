import { RefreshCw } from "lucide-react";

export function ErrorState({ message = "API request failed.", onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <div className="rounded-lg border border-danger/30 bg-white p-5 text-sm shadow-soft">
      <div className="font-semibold text-ink">Unable to load data</div>
      <div className="mt-1 text-muted">{message}</div>
      <button className="mt-4 inline-flex items-center gap-2 rounded bg-ink px-3 py-2 text-white transition duration-200 ease-in-out hover:scale-[1.02]" onClick={onRetry} type="button">
        <RefreshCw className="h-4 w-4" />
        Retry
      </button>
    </div>
  );
}
