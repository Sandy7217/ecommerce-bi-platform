export default function SettingsPage() {
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="text-sm font-semibold text-ink">Alert thresholds</div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <label className="text-sm text-muted">Lead time days<input className="mt-1 w-full rounded border border-line px-3 py-2 text-ink" defaultValue={45} /></label>
        <label className="text-sm text-muted">RTO spike %<input className="mt-1 w-full rounded border border-line px-3 py-2 text-ink" defaultValue={20} /></label>
        <label className="text-sm text-muted">Daily brief time<input className="mt-1 w-full rounded border border-line px-3 py-2 text-ink" defaultValue="09:00" /></label>
      </div>
    </section>
  );
}
