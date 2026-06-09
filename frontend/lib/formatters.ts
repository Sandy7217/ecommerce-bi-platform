export function formatINR(value: number): string {
  if (value >= 10000000) return `Rs ${(value / 10000000).toFixed(2)} Cr`;
  if (value >= 100000) return `Rs ${(value / 100000).toFixed(2)} L`;
  if (value >= 1000) return `Rs ${(value / 1000).toFixed(1)} K`;
  return `Rs ${value.toFixed(0)}`;
}

export function formatQty(value: number): string {
  if (value >= 100000) return `${(value / 100000).toFixed(2)} L`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)} K`;
  return `${value}`;
}

export function formatDate(value: string | Date): string {
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
}

export function pct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN").format(Math.round(value));
}

export function exactINR(value: number): string {
  return `Rs ${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value)}`;
}
