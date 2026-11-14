/* The chance a fire keeps burning as a ring: the arc is the estimate, the faint band behind it is its range.
   Untested shows an empty ring and a dash: no number outside what NASA tested. */
const R = 52, C = 2 * Math.PI * R;

export function Gauge({ p, low, high, label, id }: { p: number | null; low?: number; high?: number; label: string; id?: string }) {
  const arc = (v: number) => `${Math.max(0, Math.min(1, v)) * C} ${C}`;
  return (
    <div className="gauge">
      <svg viewBox="0 0 128 128" aria-hidden="true">
        <defs>
          <linearGradient id="emberArc" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ffc24b" /><stop offset=".5" stopColor="#ff7a3d" /><stop offset="1" stopColor="#ff4d6d" />
          </linearGradient>
        </defs>
        <circle cx="64" cy="64" r={R} className="g-track" />
        {p != null && high != null && low != null && (
          <circle cx="64" cy="64" r={R} className="g-range" strokeDasharray={`${(high - low) * C} ${C}`} strokeDashoffset={-low * C} transform="rotate(-90 64 64)" />
        )}
        {p != null && <circle cx="64" cy="64" r={R} className="g-arc" strokeDasharray={arc(p)} transform="rotate(-90 64 64)" />}
      </svg>
      <div className="g-mid">
        {p != null ? <b id={id}>{Math.round(p * 100)}%</b> : <b className="g-none">—</b>}
        <span>{label}</span>
      </div>
    </div>
  );
}
