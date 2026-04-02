"use client";

import { useEffect, useState } from "react";
import { CalendarClock, UsersRound, UtensilsCrossed } from "lucide-react";

import { CapacityBars } from "@/components/capacity-bars";
import { DashboardShell } from "@/components/dashboard-shell";
import { MetricPanel } from "@/components/metric-panel";
import { SectionCard } from "@/components/section-card";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch, queryString } from "@/lib/api";
import { shiftLocalDateInputValue, toLocalDateInputValue } from "@/lib/format";
import { CapacitySnapshot } from "@/lib/types";

export default function CapacityPage() {
  const { activeRestaurantId } = useWorkspace();
  const [selectedDate, setSelectedDate] = useState(toLocalDateInputValue());
  const [snapshot, setSnapshot] = useState<CapacitySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeRestaurantId) return;
    setLoading(true);
    setError(null);
    apiFetch<CapacitySnapshot>(
      `/api/analytics/capacity${queryString({
        restaurant_id: activeRestaurantId,
        date: selectedDate
      })}`
    )
      .then(setSnapshot)
      .catch((fetchError: unknown) => {
        const message = fetchError instanceof ApiError ? fetchError.message : "Impossibile caricare la capienza.";
        setError(message);
      })
      .finally(() => setLoading(false));
  }, [activeRestaurantId, selectedDate]);

  const totalCovers = snapshot?.slots.reduce((sum, slot) => sum + slot.max_covers, 0) ?? 0;
  const totalBooked = snapshot?.slots.reduce((sum, slot) => sum + slot.booked_covers, 0) ?? 0;
  const totalRemaining = snapshot?.slots.reduce((sum, slot) => sum + slot.remaining_covers, 0) ?? 0;
  const nearFull = snapshot?.slots.filter((slot) => slot.occupancy_ratio >= 0.75).length ?? 0;
  const occupancy = totalCovers > 0 ? Math.round((totalBooked / totalCovers) * 100) : 0;

  return (
    <DashboardShell
      title="Capienza"
      subtitle="Leggi l’occupazione per turno, capisci quanto margine resta e anticipa le fasce che rischiano di saturarsi."
      actions={
        <div className="flex w-full flex-col gap-2 sm:w-auto">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSelectedDate(toLocalDateInputValue())}
              className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
            >
              Oggi
            </button>
            <button
              type="button"
              onClick={() => setSelectedDate(shiftLocalDateInputValue(toLocalDateInputValue(), 1))}
              className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
            >
              Domani
            </button>
          </div>
          <div className="flex w-full items-center gap-2 sm:w-auto">
          <button
            type="button"
            onClick={() => setSelectedDate(shiftLocalDateInputValue(selectedDate, -1))}
            className="rounded-full border border-stone px-3 py-2 text-sm text-ink/60 transition hover:border-gold hover:text-ink"
          >
            ←
          </button>
          <input
            type="date"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
            className="min-w-0 flex-1 rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-sm text-ink outline-none transition focus:border-gold sm:min-w-[210px] sm:flex-none"
          />
          <button
            type="button"
            onClick={() => setSelectedDate(shiftLocalDateInputValue(selectedDate, 1))}
            className="rounded-full border border-stone px-3 py-2 text-sm text-ink/60 transition hover:border-gold hover:text-ink"
          >
            →
          </button>
          </div>
        </div>
      }
    >
      <div className="space-y-6">
        <div className="grid gap-4 lg:grid-cols-4">
          <MetricPanel
            label="Occupazione totale"
            value={`${occupancy}%`}
            detail="Quota coperti già impegnata nella giornata selezionata."
            badge={{
              label: occupancy >= 75 ? "Sotto pressione" : occupancy > 0 ? "Gestibile" : "Ancora vuoto",
              tone: occupancy >= 75 ? "warn" : occupancy > 0 ? "good" : "neutral",
            }}
            tone="gold"
            icon={<CalendarClock size={18} />}
          />
          <MetricPanel
            label="Coperti prenotati"
            value={totalBooked.toFixed(0)}
            detail="Somma di tutti i coperti già bloccati sui turni del giorno."
            tone="olive"
            icon={<UsersRound size={18} />}
          />
          <MetricPanel
            label="Coperti ancora liberi"
            value={totalRemaining.toFixed(0)}
            detail="Margine residuo che il telefono può ancora promettere con serenità."
            tone="terracotta"
            icon={<UtensilsCrossed size={18} />}
          />
          <MetricPanel
            label="Turni quasi pieni"
            value={nearFull.toFixed(0)}
            detail="Turni oltre il 75%: utili da monitorare prima del picco chiamate."
            tone="ink"
            icon={<CalendarClock size={18} />}
          />
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.66fr_0.34fr]">
        <SectionCard title="Capacità per turno" kicker="Occupazione live">
          {error ? (
            <p className="rounded-[1.45rem] border border-terracotta/30 bg-terracotta/10 px-4 py-4 text-sm text-terracotta">
              {error}
            </p>
          ) : loading ? (
            <div className="h-64 animate-pulse rounded-[1.8rem] bg-ivory/70" />
          ) : snapshot && snapshot.slots.length > 0 ? (
            <CapacityBars slots={snapshot.slots} />
          ) : (
            <p className="rounded-[1.45rem] border border-dashed border-stone px-4 py-10 text-sm text-ink/55">
              Nessun turno configurato per questa data. Configura i turni in Impostazioni.
            </p>
          )}
        </SectionCard>

        <SectionCard title="Indicazioni operative" kicker="Floor management">
          <div className="space-y-4 text-sm leading-7 text-ink/68">
            <div className="rounded-[1.4rem] border border-stone/80 bg-ivory/70 p-4">
              <p className="font-semibold text-ink">Cosa mantenere</p>
              <p className="mt-2">
                La vista per turno è corretta: riflette esattamente la logica usata dal telefono AI, quindi
                il banco e l’agente parlano la stessa lingua.
              </p>
            </div>
            <div className="rounded-[1.4rem] border border-stone/80 bg-white/80 p-4">
              <p className="font-semibold text-ink">Cosa migliorare</p>
              <p className="mt-2">
                Quando un turno entra in zona gialla o rossa, conviene rivedere staffing, tavoli grandi e
                promesse telefoniche. Se devi stringere la capienza, fallo in Impostazioni prima del rush.
              </p>
            </div>
            <div className="rounded-[1.4rem] border border-terracotta/15 bg-terracotta/6 p-4">
              <p className="font-semibold text-ink">Quando intervenire</p>
              <p className="mt-2">
                Se i turni quasi pieni aumentano ma le chiamate non convertono, il rischio non è solo saturazione:
                è lasciare richieste sul tavolo. In quel caso apri subito Panoramica e Chiamate.
              </p>
            </div>
          </div>
        </SectionCard>
      </div>
      </div>
    </DashboardShell>
  );
}
