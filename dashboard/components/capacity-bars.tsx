import { CapacitySlot } from "@/lib/types";

export function CapacityBars({ slots }: { slots: CapacitySlot[] }) {
  return (
    <div className="space-y-4">
      {slots.map((slot) => {
        const ratio = Math.min(slot.occupancy_ratio * 100, 100);
        const status =
          ratio >= 95
            ? { label: "Saturo", tone: "bg-terracotta/12 text-terracotta", bar: "from-terracotta via-[#d97757] to-terracotta" }
            : ratio >= 75
              ? { label: "Quasi pieno", tone: "bg-gold/15 text-[#8c6a1f]", bar: "from-gold to-terracotta/80" }
              : { label: "Margine buono", tone: "bg-olive/12 text-olive", bar: "from-olive to-gold" };

        return (
          <div key={slot.turno} className="rounded-[1.5rem] border border-stone/80 bg-ivory/65 p-4">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-display text-xl capitalize text-ink">{slot.turno}</p>
                  <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${status.tone}`}>
                    {status.label}
                  </span>
                </div>
                <p className="mt-2 text-sm text-ink/55">
                  {slot.start} - {slot.end}
                </p>
              </div>
              <div className="grid gap-1 text-sm text-ink/65 sm:text-right">
                <p>{slot.booked_covers} coperti prenotati</p>
                <p>{slot.remaining_covers} disponibili</p>
                <p className="font-semibold text-ink/80">{ratio.toFixed(0)}% occupato</p>
              </div>
            </div>
            <div className="h-4 overflow-hidden rounded-full bg-stone/70">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${status.bar}`}
                style={{ width: `${ratio}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
