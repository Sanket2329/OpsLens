export function ConfidenceGauge({ value, size = 160 }: { value: number; size?: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const color = pct >= 80 ? "var(--success)" : pct >= 50 ? "var(--warning)" : "var(--danger)";
  const radius = size / 2 - 10;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (pct / 100) * circ;
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="var(--border)" strokeWidth={8} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={8}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 600ms ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tabular-nums" style={{ color }}>
          {pct.toFixed(0)}%
        </span>
        <span className="text-xs text-muted-foreground">Confidence</span>
      </div>
    </div>
  );
}

export function SimilarityBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value <= 1 ? value * 100 : value));
  const color = pct >= 75 ? "var(--success)" : pct >= 50 ? "var(--warning)" : "var(--muted-foreground)";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">{pct.toFixed(0)}%</span>
    </div>
  );
}