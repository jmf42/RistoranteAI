import { TrendPoint } from "@/lib/types";

function buildPath(values: number[], width: number, height: number): string {
  if (!values.length) {
    return "";
  }
  const max = Math.max(...values, 1);
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - (value / max) * (height - 16) - 8;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

export function TrendChart({ points }: { points: TrendPoint[] }) {
  const width = 420;
  const height = 170;
  const callsPath = buildPath(
    points.map((point) => point.calls),
    width,
    height
  );
  const bookingsPath = buildPath(
    points.map((point) => point.bookings),
    width,
    height
  );

  return (
    <div className="rounded-[1.5rem] border border-stone/80 bg-ivory/70 p-4">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-44 w-full"
        role="img"
        aria-label="Trend chart"
      >
        <defs>
          <linearGradient id="callsGradient" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#b24b34" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#b24b34" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="bookingsGradient" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#5c6650" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#5c6650" stopOpacity="0.2" />
          </linearGradient>
        </defs>
        {Array.from({ length: 4 }).map((_, index) => {
          const y = (height / 4) * index + 12;
          return <line key={y} x1="0" x2={width} y1={y} y2={y} stroke="rgba(28,22,18,0.08)" />;
        })}
        <path d={callsPath} fill="none" stroke="url(#callsGradient)" strokeWidth="4" strokeLinecap="round" />
        <path
          d={bookingsPath}
          fill="none"
          stroke="url(#bookingsGradient)"
          strokeWidth="4"
          strokeLinecap="round"
        />
      </svg>
      <div className="mt-3 flex items-center gap-4 text-sm text-ink/65">
        <span className="inline-flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-terracotta" />
          Chiamate
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-olive" />
          Prenotazioni
        </span>
      </div>
    </div>
  );
}
