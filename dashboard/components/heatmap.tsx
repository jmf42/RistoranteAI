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
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-[0.2em] text-ink/42">
        Su mobile scorri orizzontalmente: le ore restano leggibili senza schiacciare i dati.
      </p>
      <div className="-mx-1 overflow-x-auto pb-2">
        <div className="min-w-[556px] space-y-2 px-1 sm:min-w-[640px]">
          <div className="grid grid-cols-[52px_repeat(24,minmax(18px,1fr))] gap-1 text-[10px] uppercase tracking-[0.18em] text-ink/45 sm:grid-cols-[62px_repeat(24,minmax(0,1fr))] sm:text-[11px] sm:tracking-[0.22em]">
            <span />
            {Array.from({ length: 24 }).map((_, hour) => (
              <span key={hour} className="text-center">
                {hour.toString().padStart(2, "0")}
              </span>
            ))}
          </div>
          {Array.from({ length: 7 }).map((_, weekday) => (
            <div key={weekday} className="grid grid-cols-[52px_repeat(24,minmax(18px,1fr))] gap-1 sm:grid-cols-[62px_repeat(24,minmax(0,1fr))]">
              <span className="flex items-center text-xs font-medium text-ink/60 sm:text-sm">
                {weekdayLabel(weekday)}
              </span>
              {Array.from({ length: 24 }).map((_, hour) => {
                const value = cellMap.get(`${weekday}-${hour}`) ?? 0;
                const callLabel = value === 1 ? "chiamata" : "chiamate";
                return (
                  <div
                    key={`${weekday}-${hour}`}
                    className={`h-7 rounded-md border border-white/70 sm:h-8 ${intensityColor(value, max)}`}
                    title={`${weekdayLabel(weekday)} ${hour}:00 — ${value} ${callLabel}`}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
