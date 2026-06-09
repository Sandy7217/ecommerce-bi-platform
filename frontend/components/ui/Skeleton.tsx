export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-slate-200/70 ${className}`} />;
}

export function CardSkeleton() {
  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-soft">
      <Skeleton className="h-3 w-28" />
      <Skeleton className="mt-4 h-8 w-32" />
      <Skeleton className="mt-4 h-3 w-24" />
    </div>
  );
}
