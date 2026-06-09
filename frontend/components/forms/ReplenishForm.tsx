"use client";

export function ReplenishForm() {
  return (
    <form className="grid gap-3 rounded-lg border border-line bg-white p-4 shadow-soft md:grid-cols-[1fr_160px_auto]">
      <input className="rounded border border-line px-3 py-2 text-sm" placeholder="style_color" />
      <input className="rounded border border-line px-3 py-2 text-sm" placeholder="Qty" type="number" />
      <button className="rounded bg-ink px-4 py-2 text-sm font-medium text-white" type="button">Plan</button>
    </form>
  );
}
