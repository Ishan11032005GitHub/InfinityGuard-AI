export function Card({ title, value, helper, children }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      {title && <div className="text-sm font-medium text-steel">{title}</div>}
      {value && <div className="mt-2 text-2xl font-semibold tracking-normal">{value}</div>}
      {helper && <div className="mt-1 text-sm text-steel">{helper}</div>}
      {children}
    </section>
  );
}

export function Skeleton() {
  return <div className="h-36 animate-pulse rounded-lg bg-slate-200" />;
}
