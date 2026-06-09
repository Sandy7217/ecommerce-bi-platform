type AlertProps = {
  title: string;
  body: string;
  level?: "info" | "warning" | "critical";
};

const levelClasses = {
  info: "border-blue/30 bg-blue/5",
  warning: "border-amber/30 bg-amber/5",
  critical: "border-danger/30 bg-danger/5"
};

export function Alert({ title, body, level = "info" }: AlertProps) {
  return (
    <div className={`rounded-lg border p-3 ${levelClasses[level]}`}>
      <div className="text-sm font-semibold text-ink">{title}</div>
      <div className="mt-1 text-sm text-muted">{body}</div>
    </div>
  );
}
