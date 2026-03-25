"use client";

import { useEffect, useState } from "react";

import { CapacityBars } from "@/components/capacity-bars";
import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch, queryString } from "@/lib/api";
import { CapacitySnapshot } from "@/lib/types";

export default function CapacityPage() {
  const { activeRestaurantId } = useWorkspace();
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10));
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

  return (
    <DashboardShell
      title="Capienza"
      subtitle="Leggi l’occupazione per turno, capisci quanto margine resta e anticipa le fasce che rischiano di saturarsi."
      actions={
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              const d = new Date(selectedDate);
              d.setDate(d.getDate() - 1);
              setSelectedDate(d.toISOString().slice(0, 10));
            }}
            className="rounded-full border border-stone px-3 py-2 text-sm text-ink/60 transition hover:border-gold hover:text-ink"
          >
            ←
          </button>
          <input
            type="date"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
            className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-sm text-ink outline-none transition focus:border-gold"
          />
          <button
            type="button"
            onClick={() => {
              const d = new Date(selectedDate);
              d.setDate(d.getDate() + 1);
              setSelectedDate(d.toISOString().slice(0, 10));
            }}
            className="rounded-full border border-stone px-3 py-2 text-sm text-ink/60 transition hover:border-gold hover:text-ink"
          >
            →
          </button>
        </div>
      }
    >
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
            <p className="rounded-[1.4rem] border border-stone/80 bg-ivory/70 p-4">
              Usa questa vista per calibrare staffing e promesse telefoniche. Il sistema ragiona per turno,
              quindi tutta la disponibilità mostrata qui è coerente con la logica dei tool voce.
            </p>
            <p className="rounded-[1.4rem] border border-stone/80 bg-white/80 p-4">
              Se devi ridurre coperti per un evento privato o per carenza di staff, aggiorna i turni in
              Impostazioni e il motore di prenotazione si riallinea subito.
            </p>
          </div>
        </SectionCard>
      </div>
    </DashboardShell>
  );
}
