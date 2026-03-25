import { HeatmapCell } from "@/lib/types";
import { weekdayLabel } from "@/lib/format";

function intensityColor(value: number, max: number): string {
  if (!value) {
    return "bg-white/70";
  }
  const ratio = value / Math.max(max, 1);
  if (ratio > 0.75) return "bg-terracotta/90";
  if (ratio > 0.5) return "bg-terracotta/65";
  if (ratio > 0.25) return "bg-gold/70";
  return "bg-olive/55";
}

export function Heatmap({ cells }: { cells: HeatmapCell[] }) {
  const cellMap = new Map(cells.map((cell) => [`${cell.weekday}-${cell.hour}`, cell.calls]));
  const max = Math.max(...cells.map((cell) => cell.calls), 0);

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[720px] space-y-2">
        <div className="grid grid-cols-[70px_repeat(24,minmax(0,1fr))] gap-1 text-[11px] uppercase tracking-[0.22em] text-ink/45">
          <span />
          {Array.from({ length: 24 }).map((_, hour) => (
            <span key={hour} className="text-center">
              {hour.toString().padStart(2, "0")}
            </span>
          ))}
        </div>
        {Array.from({ length: 7 }).map((_, weekday) => (
          <div key={weekday} className="grid grid-cols-[70px_repeat(24,minmax(0,1fr))] gap-1">
            <span className="flex items-center text-sm font-medium text-ink/60">{weekdayLabel(weekday)}</span>
            {Array.from({ length: 24 }).map((_, hour) => {
              const value = cellMap.get(`${weekday}-${hour}`) ?? 0;
              return (
                <div
                  key={`${weekday}-${hour}`}
                  className={`h-8 rounded-md border border-white/70 ${intensityColor(value, max)}`}
                  title={`${weekdayLabel(weekday)} ${hour}:00 — ${value} chiamate`}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
