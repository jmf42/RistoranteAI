"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { StatCard } from "@/components/stat-card";
import { TrendChart } from "@/components/trend-chart";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch, queryString } from "@/lib/api";
import { getActivityPresentation } from "@/lib/call-presenter";
import { formatDateTime, formatPercent } from "@/lib/format";
import { AnalyticsOverview, TrendBundle } from "@/lib/types";

function isUrgentActivity(item: AnalyticsOverview["recent_activity"][number]) {
  if (item.kind !== "call") {
    return false;
  }
  const presentation = getActivityPresentation(item);
  return presentation.needsAttention;
}

export default function HomePage() {
  const { restaurant, activeRestaurantId } = useWorkspace();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [trends, setTrends] = useState<TrendBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const unresolvedCalls = overview
    ? Math.max(Math.round(overview.calls_today.value - overview.bookings_today.value), 0)
    : 0;
  const conversionHeadline =
    overview?.booking_rate_today.status === "good" ? "Bene" : overview?.booking_rate_today.value ? "Da seguire" : "Partenza lenta";
  const priorityItems = overview ? overview.recent_activity.filter(isUrgentActivity).slice(0, 3) : [];
  const recentItems = overview
    ? overview.recent_activity
        .filter((item) => item.kind !== "call")
        .slice(0, 2)
    : [];

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
      subtitle="In due minuti capisci volume, conversione e chiamate che richiedono ancora attenzione."
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
          <div className="ui-snap-row -mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-1 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 lg:grid-cols-3">
            <div className="min-w-[78vw] snap-start sm:min-w-0">
              <StatCard
                label="Chiamate oggi"
                value={overview.calls_today.value.toFixed(0)}
                detail="Traffico telefonico in tempo reale"
                delta={overview.calls_today.delta_vs_yesterday}
                tone="terracotta"
              />
            </div>
            <div className="min-w-[78vw] snap-start sm:min-w-0">
              <StatCard
                label="Prenotazioni create"
                value={overview.bookings_today.value.toFixed(0)}
                detail="AI + dashboard + walk-in"
                delta={overview.bookings_today.delta_vs_yesterday}
                tone="olive"
              />
            </div>
            <div className="min-w-[78vw] snap-start sm:col-span-2 sm:min-w-0 lg:col-span-1">
              <StatCard
                label="Booking rate"
                value={formatPercent(overview.booking_rate_today.value)}
                detail="Conversione chiamate in tavoli"
                delta={overview.booking_rate_today.delta_vs_yesterday}
                tone="gold"
              />
            </div>
          </div>

          <div className="order-2 grid gap-6 xl:order-1 xl:grid-cols-[1.3fr_0.7fr]">
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
                    Nessun orario critico emerso nel periodo selezionato. Quando iniziano a concentrarsi
                    richieste senza esito, qui vedrai subito le fasce più richieste da proteggere.
                  </p>
                )}
              </div>
            </SectionCard>
          </div>

          <div className="order-1 grid gap-6 xl:order-2 xl:grid-cols-[0.95fr_1.05fr]">
            <SectionCard
              title="Cosa guardare adesso"
              kicker="Priorità del giorno"
              action={
                <Link
                  href="/calls"
                  className="inline-flex w-full items-center justify-center rounded-full border border-stone px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink sm:w-auto"
                >
                  Apri chiamate
                </Link>
              }
            >
              <div className="space-y-3">
                {priorityItems.length === 0 && recentItems.length === 0 ? (
                  <p className="rounded-[1.4rem] border border-dashed border-stone px-4 py-8 text-sm text-ink/55">
                    Nessun segnale urgente nel periodo recente. Qui vedrai solo prenotazioni appena chiuse o chiamate da seguire.
                  </p>
                ) : null}
                {priorityItems.map((item) => {
                  const presentation = getActivityPresentation(item);
                  return (
                  <article
                    key={item.id}
                    className={`rounded-[1.35rem] border p-4 ${
                      presentation.needsAttention
                        ? "border-terracotta/25 bg-terracotta/5"
                        : "border-stone/75 bg-white/70"
                    }`}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                          {presentation.eyebrow}
                        </p>
                        <p className="mt-2 font-semibold text-ink">{presentation.headline}</p>
                        <p className="mt-2 text-sm leading-6 text-ink/65">{presentation.preview}</p>
                      </div>
                      <p className="text-xs uppercase tracking-[0.2em] text-ink/40 sm:text-right">
                        {formatDateTime(item.created_at)}
                      </p>
                    </div>
                  </article>
                )})}
                {recentItems.map((item) => {
                  const presentation = getActivityPresentation(item);
                  return (
                  <article
                    key={item.id}
                    className="rounded-[1.35rem] border border-stone/75 bg-white/70 p-4"
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                          {presentation.eyebrow}
                        </p>
                        <p className="mt-2 font-semibold text-ink">{presentation.headline}</p>
                        <p className="mt-2 text-sm leading-6 text-ink/65">{presentation.preview}</p>
                      </div>
                      <p className="text-xs uppercase tracking-[0.2em] text-ink/40 sm:text-right">
                        {formatDateTime(item.created_at)}
                      </p>
                    </div>
                  </article>
                )})}
              </div>
            </SectionCard>

            <SectionCard title="Lettura rapida del giorno" kicker="Quadro rapido">
              <div className="grid gap-4 sm:grid-cols-2">
                <article className="min-w-0 rounded-[1.5rem] border border-stone/80 bg-ivory/70 p-5">
                  <p className="ui-kicker text-xs uppercase tracking-[0.22em] text-terracotta/70 sm:tracking-[0.28em]">
                    Stato conversione
                  </p>
                  <p className="ui-display-card-value mt-4 font-display text-ink">
                    {conversionHeadline}
                  </p>
                  <p className="mt-3 text-sm leading-7 text-ink/65">
                    Oggi l’AI sta convertendo il {formatPercent(overview.booking_rate_today.value)} delle
                    chiamate in tavoli. Rispetto alla media settimanale sei a{" "}
                    {overview.booking_rate_today.delta_vs_7d_avg >= 0 ? "+" : ""}
                    {overview.booking_rate_today.delta_vs_7d_avg.toFixed(1)} punti.
                  </p>
                </article>
                <article className="min-w-0 rounded-[1.5rem] border border-stone/80 bg-ink p-5 text-ivory">
                  <p className="ui-kicker text-xs uppercase tracking-[0.22em] text-gold/75 sm:tracking-[0.28em]">
                    Da seguire
                  </p>
                  <p className="ui-display-card-value mt-4 font-display">
                    {unresolvedCalls > 0 ? unresolvedCalls.toFixed(0) : "nessuna"}
                  </p>
                  <p className="mt-3 text-sm leading-7 text-ivory/70">
                    Chiamate di oggi senza prenotazione chiusa. Apri la sezione Chiamate per capire se serve
                    un richiamo, un controllo disponibilità o un aggiustamento del flusso AI.
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
