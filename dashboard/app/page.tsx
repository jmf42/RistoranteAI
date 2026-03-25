"use client";

import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { StatCard } from "@/components/stat-card";
import { TrendChart } from "@/components/trend-chart";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch, queryString } from "@/lib/api";
import { formatDateTime, formatPercent } from "@/lib/format";
import { AnalyticsOverview, TrendBundle } from "@/lib/types";

export default function HomePage() {
  const { restaurant, activeRestaurantId } = useWorkspace();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [trends, setTrends] = useState<TrendBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeRestaurantId) {
      return;
    }

    let ignore = false;
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch<AnalyticsOverview>(
        `/api/analytics/overview${queryString({ restaurant_id: activeRestaurantId })}`
      ),
      apiFetch<TrendBundle>(
        `/api/analytics/trends${queryString({ restaurant_id: activeRestaurantId, days: 14 })}`
      )
    ])
      .then(([overviewPayload, trendPayload]) => {
        if (ignore) return;
        setOverview(overviewPayload);
        setTrends(trendPayload);
      })
      .catch((fetchError: unknown) => {
        if (ignore) return;
        const message = fetchError instanceof ApiError ? fetchError.message : "Impossibile caricare i dati.";
        setError(message);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [activeRestaurantId]);

  return (
    <DashboardShell
      title="Panoramica operativa"
      subtitle="Le metriche che contano oggi, i segnali di domanda e il ritmo del servizio nella fascia serale."
    >
      {error ? (
        <p className="rounded-[1.45rem] border border-terracotta/30 bg-terracotta/10 px-4 py-4 text-sm text-terracotta">
          {error}
        </p>
      ) : loading || !overview || !trends ? (
        <div className="grid gap-6 xl:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-56 animate-pulse rounded-[2rem] bg-white/70" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-3">
            <StatCard
              label="Chiamate oggi"
              value={overview.calls_today.value.toFixed(0)}
              detail="Traffico telefonico in tempo reale"
              delta={overview.calls_today.delta_vs_yesterday}
              tone="terracotta"
            />
            <StatCard
              label="Prenotazioni create"
              value={overview.bookings_today.value.toFixed(0)}
              detail="AI + dashboard + walk-in"
              delta={overview.bookings_today.delta_vs_yesterday}
              tone="olive"
            />
            <StatCard
              label="Booking rate"
              value={formatPercent(overview.booking_rate_today.value)}
              detail="Conversione chiamate in tavoli"
              delta={overview.booking_rate_today.delta_vs_yesterday}
              tone="gold"
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
            <SectionCard
              title="Trend ultimi 14 giorni"
              kicker={restaurant?.name ?? "Trend"}
            >
              <TrendChart points={trends.points} />
            </SectionCard>
            <SectionCard title="Slot più richiesti ma persi" kicker="Demand gaps">
              <div className="space-y-3">
                {overview.demand_gaps.length ? (
                  overview.demand_gaps.map((gap) => (
                    <article
                      key={gap.label}
                      className="rounded-[1.4rem] border border-stone/80 bg-ivory/70 p-4"
                    >
                      <p className="font-medium text-ink">{gap.label}</p>
                      <p className="mt-2 text-sm text-ink/60">
                        {gap.total_requests} richieste recenti senza conversione.
                      </p>
                    </article>
                  ))
                ) : (
                  <p className="rounded-[1.4rem] border border-dashed border-stone px-4 py-8 text-sm text-ink/55">
                    Nessun gap registrato nei dati demo. Appena arrivano più chiamate, questa sezione
                    evidenzia gli orari più richiesti ma non disponibili.
                  </p>
                )}
              </div>
            </SectionCard>
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
            <SectionCard title="Attività recente" kicker="Live feed">
              <div className="space-y-3">
                {overview.recent_activity.map((item) => (
                  <article
                    key={item.id}
                    className="rounded-[1.35rem] border border-stone/75 bg-white/70 p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-semibold text-ink">{item.title}</p>
                        <p className="mt-2 text-sm leading-6 text-ink/65">{item.detail}</p>
                      </div>
                      <p className="text-xs uppercase tracking-[0.2em] text-ink/40">
                        {formatDateTime(item.created_at)}
                      </p>
                    </div>
                  </article>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Lettura rapida del giorno" kicker="Front of house">
              <div className="grid gap-4 sm:grid-cols-2">
                <article className="rounded-[1.5rem] border border-stone/80 bg-ivory/70 p-5">
                  <p className="text-xs uppercase tracking-[0.28em] text-terracotta/70">
                    Stato conversione
                  </p>
                  <p className="mt-4 font-display text-5xl text-ink">
                    {overview.booking_rate_today.status === "good" ? "Solido" : "Attenzione"}
                  </p>
                  <p className="mt-3 text-sm leading-7 text-ink/65">
                    La conversione di oggi è {formatPercent(overview.booking_rate_today.value)} con una
                    variazione di {overview.booking_rate_today.delta_vs_7d_avg.toFixed(1)} punti sulla media
                    settimanale.
                  </p>
                </article>
                <article className="rounded-[1.5rem] border border-stone/80 bg-ink p-5 text-ivory">
                  <p className="text-xs uppercase tracking-[0.28em] text-gold/75">
                    Turno da sorvegliare
                  </p>
                  <p className="mt-4 font-display text-5xl">
                    {trends.escalations.length ? trends.escalations[0].outcome.replaceAll("_", " ") : "nessuno"}
                  </p>
                  <p className="mt-3 text-sm leading-7 text-ivory/70">
                    I dati demo mostrano dove l’AI ha avuto bisogno di aiuto umano. In produzione questa area
                    serve per tarare prompt, regole e staffing.
                  </p>
                </article>
              </div>
            </SectionCard>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
