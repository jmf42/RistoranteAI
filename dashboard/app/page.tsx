"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CalendarDays, PhoneCall, TriangleAlert, Users } from "lucide-react";

import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch, queryString } from "@/lib/api";
import { formatDate, toLocalDateInputValue } from "@/lib/format";
import { AnalyticsOverview, Booking, CapacitySnapshot } from "@/lib/types";

const activeStatuses = new Set(["confirmed", "modified"]);

export default function HomePage() {
  const { restaurant, activeRestaurantId } = useWorkspace();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [bookingsToday, setBookingsToday] = useState<Booking[]>([]);
  const [capacityToday, setCapacityToday] = useState<CapacitySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const today = toLocalDateInputValue();

  useEffect(() => {
    if (!activeRestaurantId) {
      return;
    }

    let ignore = false;
    setLoading(true);
    setError(null);

    Promise.all([
      apiFetch<AnalyticsOverview>(`/api/analytics/overview${queryString({ restaurant_id: activeRestaurantId })}`),
      apiFetch<Booking[]>(
        `/api/bookings${queryString({
          restaurant_id: activeRestaurantId,
          date_from: today,
          date_to: today,
        })}`,
      ),
      apiFetch<CapacitySnapshot>(
        `/api/analytics/capacity${queryString({
          restaurant_id: activeRestaurantId,
          date: today,
        })}`,
      ),
    ])
      .then(([overviewPayload, bookingsPayload, capacityPayload]) => {
        if (ignore) {
          return;
        }
        setOverview(overviewPayload);
        setBookingsToday(bookingsPayload);
        setCapacityToday(capacityPayload);
      })
      .catch((caught: unknown) => {
        if (ignore) {
          return;
        }
        setError(caught instanceof ApiError ? caught.message : "Impossibile caricare il quadro del giorno.");
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [activeRestaurantId, today]);

  const activeBookings = useMemo(
    () =>
      bookingsToday
        .filter((booking) => activeStatuses.has(booking.status))
        .sort((left, right) => `${left.date}${left.time}`.localeCompare(`${right.date}${right.time}`)),
    [bookingsToday],
  );

  const slots = useMemo(() => {
    if (capacityToday?.slots.length) {
      return capacityToday.slots;
    }
    return (restaurant?.turni ?? []).map((turno) => ({
      turno: turno.name,
      start: turno.start,
      end: turno.end,
      booked_covers: 0,
      max_covers: turno.max_covers,
      remaining_covers: turno.max_covers,
      occupancy_ratio: 0,
    }));
  }, [capacityToday?.slots, restaurant?.turni]);

  const totalReserved = slots.reduce((sum, slot) => sum + slot.booked_covers, 0);
  const totalCapacity = slots.reduce((sum, slot) => sum + slot.max_covers, 0);
  const unresolvedCalls = overview
    ? Math.max(Math.round(overview.calls_today.value - overview.bookings_today.value), 0)
    : 0;
  const biggestGap = overview?.demand_gaps[0] ?? null;
  const upcomingGuests = activeBookings.slice(0, 6);
  const issues = [
    unresolvedCalls > 0
      ? {
          title: `${unresolvedCalls} telefonate da rivedere`,
          detail: "C'è richiesta senza tavolo chiuso. Vale la pena controllare o richiamare.",
          href: "/calls",
          cta: "Apri chiamate",
          tone: "danger" as const,
        }
      : null,
    biggestGap
      ? {
          title: `Attenzione su ${biggestGap.label}`,
          detail: `${biggestGap.total_requests} ${biggestGap.total_requests === 1 ? "richiesta" : "richieste"} senza conversione.`,
          href: `/bookings?date=${today}`,
          cta: "Apri prenotazioni",
          tone: "warn" as const,
        }
      : null,
    restaurant && !(restaurant.twilio_phone && restaurant.elevenlabs_agent_id && restaurant.escalation_phone)
      ? {
          title: "Setup telefono da completare",
          detail: "Serve allineare linea AI o backup umano prima del rush.",
          href: "/settings",
          cta: "Apri impostazioni",
          tone: "warn" as const,
        }
      : null,
  ].filter(Boolean) as Array<{
    title: string;
    detail: string;
    href: string;
    cta: string;
    tone: "warn" | "danger";
  }>;

  return (
    <DashboardShell
      title="Oggi in sala"
      subtitle="Apri un servizio e vedi subito coperti prenotati, posti ancora liberi e lista ospiti."
    >
      {error ? (
        <p className="rounded-[1.45rem] border border-terracotta/30 bg-terracotta/10 px-4 py-4 text-sm text-terracotta">
          {error}
        </p>
      ) : loading ? (
        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="h-80 animate-pulse rounded-[2rem] bg-white/70" />
          <div className="h-80 animate-pulse rounded-[2rem] bg-white/70" />
        </div>
      ) : (
        <div className="space-y-6">
          <SectionCard title="Servizi di oggi" kicker="Vista owner">
            <div className="space-y-5">
              <div className="flex flex-col gap-3 rounded-[1.6rem] border border-stone/80 bg-ivory/55 p-5 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                    Quadro rapido
                  </p>
                  <p className="mt-3 font-display text-4xl text-ink">
                    {totalReserved} coperti prenotati
                  </p>
                  <p className="mt-2 text-sm leading-7 text-ink/65">
                    Oggi hai {activeBookings.length} {activeBookings.length === 1 ? "prenotazione confermata o modificata" : "prenotazioni confermate o modificate"} su {totalCapacity} coperti
                    totali disponibili.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge tone="good">{slots.length} servizi configurati</StatusBadge>
                  <StatusBadge tone={unresolvedCalls > 0 ? "warn" : "neutral"}>
                    {unresolvedCalls > 0 ? `${unresolvedCalls} da seguire` : "Nessun blocco urgente"}
                  </StatusBadge>
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                {slots.map((slot) => {
                  const reservations = activeBookings.filter((booking) => booking.turno === slot.turno);
                  return (
                    <article
                      key={slot.turno}
                      className="rounded-[1.6rem] border border-stone/80 bg-white/80 p-5 shadow-card"
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-display text-3xl text-ink">{formatTurnoName(slot.turno)}</p>
                            <StatusBadge tone={slot.occupancy_ratio >= 0.75 ? "warn" : "good"}>
                              {getServiceBadge(slot.occupancy_ratio)}
                            </StatusBadge>
                          </div>
                          <p className="mt-2 text-sm text-ink/58">
                            {slot.start.slice(0, 5)} - {slot.end.slice(0, 5)}
                          </p>
                        </div>
                        <Link
                          href={`/bookings?date=${today}&turno=${encodeURIComponent(slot.turno)}`}
                          className="inline-flex items-center gap-2 rounded-full border border-stone px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/68 transition hover:border-gold hover:text-ink"
                        >
                          Apri lista
                          <ArrowRight size={14} />
                        </Link>
                      </div>

                      <div className="mt-5 grid gap-4 sm:grid-cols-3">
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Coperti prenotati</p>
                          <p className="mt-2 font-display text-4xl text-ink">{slot.booked_covers}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Posti ancora liberi</p>
                          <p className="mt-2 font-display text-4xl text-ink">{slot.remaining_covers}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Prenotazioni</p>
                          <p className="mt-2 font-display text-4xl text-ink">{reservations.length}</p>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </div>
          </SectionCard>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <SectionCard
              title="Prossimi ospiti"
              kicker="Lista del giorno"
              action={
                <Link
                  href={`/bookings?date=${today}`}
                  className="inline-flex items-center justify-center rounded-full border border-stone px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
                >
                  Apri prenotazioni
                </Link>
              }
            >
              {upcomingGuests.length ? (
                <div className="space-y-3">
                  {upcomingGuests.map((booking) => (
                    <article
                      key={booking.id}
                      className="flex flex-col gap-3 rounded-[1.35rem] border border-stone/80 bg-white/75 p-4 sm:flex-row sm:items-start sm:justify-between"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-ink">{booking.customer_name}</p>
                          <StatusBadge tone="neutral">{formatTurnoName(booking.turno)}</StatusBadge>
                        </div>
                        <p className="mt-2 text-sm text-ink/62">
                          {formatDate(booking.date)} · {booking.time.slice(0, 5)} · {booking.party_size}{" "}
                          {booking.party_size === 1 ? "persona" : "persone"}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-ink/55">
                          {booking.special_requests || "Nessuna nota speciale"}
                        </p>
                      </div>
                      <p className="text-sm font-semibold text-ink/58">{booking.confirmation_code}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="rounded-[1.4rem] border border-dashed border-stone px-4 py-10 text-sm text-ink/55">
                  Nessuna prenotazione confermata per oggi. Se vuoi controllare domani o un servizio specifico,
                  apri Prenotazioni.
                </p>
              )}
            </SectionCard>

            <SectionCard title="Cose da controllare" kicker="Solo l'essenziale">
              {issues.length ? (
                <div className="space-y-3">
                  {issues.map((item) => (
                    <article
                      key={item.title}
                      className={`rounded-[1.4rem] border p-4 ${
                        item.tone === "danger"
                          ? "border-terracotta/20 bg-terracotta/6"
                          : "border-gold/25 bg-gold/8"
                      }`}
                    >
                      <p className="font-semibold text-ink">{item.title}</p>
                      <p className="mt-2 text-sm leading-6 text-ink/62">{item.detail}</p>
                      <Link
                        href={item.href}
                        className="mt-4 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:text-ink"
                      >
                        {item.cta}
                        <ArrowRight size={14} />
                      </Link>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="rounded-[1.45rem] border border-stone/80 bg-ivory/55 p-5">
                  <p className="font-semibold text-ink">Tutto sotto controllo</p>
                  <p className="mt-2 text-sm leading-7 text-ink/62">
                    Nessun blocco urgente emerso oggi. Se vuoi vedere tutti i dettagli del servizio,
                    apri direttamente Prenotazioni.
                  </p>
                </div>
              )}

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <Link
                  href={`/bookings?date=${today}`}
                  className="rounded-[1.35rem] border border-stone/80 bg-white/75 p-4 transition hover:border-gold"
                >
                  <div className="flex items-center gap-3">
                    <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-ivory text-ink/70">
                      <Users size={18} />
                    </div>
                    <div>
                      <p className="font-semibold text-ink">Lista completa del giorno</p>
                      <p className="mt-1 text-sm text-ink/58">Coperti, ospiti e note servizio</p>
                    </div>
                  </div>
                </Link>
                <Link
                  href="/calls"
                  className="rounded-[1.35rem] border border-stone/80 bg-white/75 p-4 transition hover:border-gold"
                >
                  <div className="flex items-center gap-3">
                    <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-ivory text-ink/70">
                      <PhoneCall size={18} />
                    </div>
                    <div>
                      <p className="font-semibold text-ink">Telefonate da seguire</p>
                      <p className="mt-1 text-sm text-ink/58">Richieste rimaste aperte o da capire</p>
                    </div>
                  </div>
                </Link>
              </div>
            </SectionCard>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}

function formatTurnoName(value: string) {
  const normalized = value.trim();
  if (!normalized) {
    return "Servizio";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function getServiceBadge(occupancyRatio: number) {
  if (occupancyRatio >= 0.9) {
    return "Quasi pieno";
  }
  if (occupancyRatio >= 0.6) {
    return "Buon ritmo";
  }
  return "Ancora margine";
}
