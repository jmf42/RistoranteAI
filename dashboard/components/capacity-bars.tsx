import { CapacitySlot } from "@/lib/types";

export function CapacityBars({ slots }: { slots: CapacitySlot[] }) {
  return (
    <div className="space-y-4">
      {slots.map((slot) => (
        <div key={slot.turno} className="rounded-[1.4rem] border border-stone/80 bg-ivory/65 p-4">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-display text-xl capitalize text-ink">{slot.turno}</p>
              <p className="text-sm text-ink/55">
                {slot.start} - {slot.end}
              </p>
            </div>
            <div className="text-sm text-ink/65 sm:text-right">
              <p>{slot.booked_covers} coperti prenotati</p>
              <p>{slot.remaining_covers} disponibili</p>
            </div>
          </div>
          <div className="h-4 overflow-hidden rounded-full bg-stone/70">
            <div
              className="h-full rounded-full bg-gradient-to-r from-olive to-gold"
              style={{ width: `${Math.min(slot.occupancy_ratio * 100, 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
