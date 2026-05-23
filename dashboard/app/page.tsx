"use client";

import Link from "next/link";
import { CalendarDays, PhoneCall, TriangleAlert } from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch, queryString } from "@/lib/api";
import { OwnerAgendaDay, OwnerAgendaResponse, OwnerAgendaTurno } from "@/lib/types";

const fullnessBar: Record<OwnerAgendaTurno["fullness"], string> = {
  low: "bg-olive/50",
  healthy: "bg-olive",
  full: "bg-gold",
  "overbooked-risk": "bg-terracotta",
};

const fullnessLabel: Record<OwnerAgendaTurno["fullness"], string> = {
  low: "Spazio",
  healthy: "Buon ritmo",
  full: "Quasi pieno",
  "overbooked-risk": "Da controllare",
};

const fullnessColor: Record<OwnerAgendaTurno["fullness"], string> = {
  low: "text-olive/70",
  healthy: "text-olive",
  full: "text-gold",
  "overbooked-risk": "text-terracotta",
};

export default function HomePage() {
  const { activeRestaurantId } = useWorkspace();
  const [agenda, setAgenda] = useState<OwnerAgendaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeRestaurantId) return;
    let ignore = false;
    setLoading(true);
    setError(null);

    void apiFetch<OwnerAgendaResponse>(
      `/api/owner/agenda${queryString({ restaurant_id: activeRestaurantId, days: 7 })}`,
    )
      .then((payload) => { if (!ignore) setAgenda(payload); })
      .catch((caught: unknown) => {
        if (!ignore) {
          setAgenda(null);
          setError(caught instanceof ApiError ? caught.message : "Non riesco a caricare l'agenda.");
        }
      })
      .finally(() => { if (!ignore) setLoading(false); });

    return () => { ignore = true; };
  }, [activeRestaurantId]);

  const alertDays = useMemo(
    () => agenda?.days.filter((d) => d.turni.some((t) => t.fullness === "overbooked-risk")).length ?? 0,
    [agenda?.days],
  );

  const quickServices = useMemo(() => {
    if (!agenda) {
      return [];
    }

    return agenda.days
      .flatMap((day) =>
        day.turni
          .filter((turno) => turno.booking_count > 0)
          .map((turno) => ({
            date: day.date,
            weekdayLabel: day.weekday_label,
            isToday: day.is_today,
            turno,
          })),
      )
      .slice(0, 4);
  }, [agenda]);

  return (
    <DashboardShell
      title="Agenda"
      subtitle="La settimana del tuo ristorante."
    >
      {error ? (
        <p className="rounded-[1.45rem] border border-terracotta/30 bg-terracotta/10 px-4 py-4 text-sm text-terracotta">
          {error}
        </p>
      ) : loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-[1.5rem] bg-white/70" />
          ))}
        </div>
      ) : agenda ? (
        <div className="space-y-4">
          <section className="grid gap-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
            <article className="ui-soft-surface rounded-[1.75rem] p-5 sm:p-6">
              <p className="ui-kicker text-xs font-semibold uppercase text-terracotta/72 sm:text-[11px]">
                Apri un servizio
              </p>
              <h3 className="mt-3 max-w-[760px] font-display text-[2rem] leading-[0.98] text-ink sm:text-[2.55rem]">
                Vai subito alla lista ospiti.
              </h3>
              <p className="mt-2 max-w-2xl text-sm leading-7 text-ink/62">
                Tocca un turno con prenotazioni per vedere subito nome, telefono e coperti del servizio.
              </p>

              <div className="ui-snap-row -mx-1 mt-5 flex gap-3 overflow-x-auto px-1 pb-1 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0">
                {quickServices.length ? (
                  quickServices.map((service) => (
                    <Link
                      key={`${service.date}-${service.turno.turno}`}
                      href={`/bookings?date=${service.date}&turno=${encodeURIComponent(service.turno.turno)}`}
                      className="min-w-[250px] rounded-[1.35rem] border border-stone/62 bg-white/82 p-4 transition hover:-translate-y-0.5 hover:border-gold/70 hover:bg-white hover:shadow-[0_14px_28px_-24px_rgba(29,22,18,0.28)] sm:min-w-0"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="ui-kicker text-[11px] font-semibold uppercase text-terracotta/62">
                            {service.isToday ? "Oggi" : service.weekdayLabel}
                          </p>
                          <p className="mt-2 font-display text-2xl text-ink">
                            {formatTurnoName(service.turno.turno)}
                          </p>
                          <p className="mt-1 text-sm text-ink/55">
                            {service.turno.start} - {service.turno.end}
                          </p>
                        </div>
                        <span className={`text-[11px] font-semibold ${fullnessColor[service.turno.fullness]}`}>
                          {fullnessLabel[service.turno.fullness]}
                        </span>
                      </div>
                      <div className="mt-4 flex items-center gap-2 text-sm text-ink/65">
                        <span className="font-semibold text-ink">{service.turno.booking_count}</span>
                        <span>{service.turno.booking_count === 1 ? "prenotazione" : "prenotazioni"}</span>
                        <span className="text-ink/30">•</span>
                        <span className="font-semibold text-ink">{service.turno.booked_covers}</span>
                        <span>{service.turno.booked_covers === 1 ? "coperto" : "coperti"}</span>
                      </div>
                    </Link>
                  ))
                ) : (
                  <div className="rounded-[1.5rem] border border-dashed border-stone/80 bg-white/60 p-5 text-sm text-ink/58 sm:col-span-2">
                    Nessun turno con prenotazioni nei prossimi giorni.
                  </div>
                )}
              </div>
            </article>

            <div className="ui-snap-row -mx-1 flex gap-3 overflow-x-auto px-1 pb-1 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0 xl:grid-cols-1">
              <KPI
                label="Coperti oggi"
                value={String(agenda.summary.today_booked_covers)}
                icon={<CalendarDays size={16} />}
              />
              <KPI
                label="Chiamate oggi"
                value={String(agenda.summary.today_calls)}
                icon={<PhoneCall size={16} />}
              />
              <KPI
                label="Da seguire"
                value={String(agenda.summary.today_unresolved_calls)}
                icon={<TriangleAlert size={16} />}
                tone={agenda.summary.today_unresolved_calls > 0 ? "alert" : alertDays > 0 ? "warn" : "calm"}
                sub={
                  agenda.summary.today_unresolved_calls > 0
                    ? "Chiamate con problemi"
                    : alertDays > 0
                    ? `${alertDays} giorni da rivedere`
                    : "Tutto in ordine"
                }
              />
            </div>
          </section>

          <div className="space-y-2">
            {agenda.days.map((day) => <DayRow key={day.date} day={day} />)}
          </div>

          <div className="flex flex-wrap justify-center gap-2 pt-1">
            <Link
              href="/bookings"
              className="inline-block rounded-full border border-stone bg-white/80 px-5 py-2.5 text-xs font-semibold uppercase tracking-[0.18em] text-ink/60 transition hover:border-gold hover:text-ink"
            >
              Vai alle prenotazioni
            </Link>
            <Link
              href="/calls"
              className="inline-block rounded-full border border-stone bg-white/80 px-5 py-2.5 text-xs font-semibold uppercase tracking-[0.18em] text-ink/60 transition hover:border-gold hover:text-ink"
            >
              Vai alle chiamate
            </Link>
          </div>
        </div>
      ) : null}
    </DashboardShell>
  );
}

function KPI({
  label,
  value,
  icon,
  sub,
  tone = "default",
}: {
  label: string;
  value: string;
  icon: ReactNode;
  sub?: string;
  tone?: "default" | "calm" | "warn" | "alert";
}) {
  const bg =
    tone === "alert" ? "from-terracotta/14 via-white/88 to-[#f4e4df]" :
    tone === "warn" ? "from-gold/16 via-white/88 to-[#f4eddd]" :
    tone === "calm" ? "from-olive/12 via-white/88 to-[#edf0eb]" :
    "from-white/88 via-white/78 to-[#f4ecdf]";

  return (
    <article className={`ui-soft-surface flex min-h-[8.35rem] min-w-[210px] items-center gap-4 rounded-[1.35rem] bg-gradient-to-br p-4 sm:min-w-0 ${bg}`}>
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/60 bg-white/72 text-ink/48 shadow-[0_12px_28px_-20px_rgba(28,22,18,0.45)]">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="ui-kicker text-[11px] font-semibold uppercase text-ink/42">{label}</p>
        <p className="mt-0.5 font-display text-[2rem] leading-none text-ink">{value}</p>
        {sub ? <p className="mt-0.5 truncate text-xs text-ink/48">{sub}</p> : null}
      </div>
    </article>
  );
}

function DayRow({ day }: { day: OwnerAgendaDay }) {
  const isAlert = day.turni.some((t) => t.fullness === "overbooked-risk");

  return (
    <article
      className={`ui-soft-surface overflow-hidden rounded-[1.35rem] transition-shadow ${
        day.is_today
          ? "bg-[linear-gradient(150deg,rgba(255,253,248,0.98),rgba(251,243,228,0.95))] shadow-card"
          : isAlert
          ? "bg-[linear-gradient(150deg,rgba(255,250,247,0.96),rgba(248,239,234,0.9))]"
          : "bg-[linear-gradient(150deg,rgba(255,252,248,0.92),rgba(244,236,226,0.86))]"
      }`}
    >
      <div
        className={`flex items-center justify-between gap-4 px-5 py-3.5 ${
          day.is_today ? "border-b border-gold/25" :
          day.is_closed || !day.turni.length ? "" :
          "border-b border-stone/45"
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-white/60 bg-white/68 text-center shadow-[0_14px_32px_-24px_rgba(28,22,18,0.5)]">
            <span className="font-display text-lg leading-none text-ink">{formatDayNumber(day.date)}</span>
          </div>
          <div>
            <p className="ui-kicker text-[11px] font-semibold uppercase text-terracotta/58">
              {day.weekday_label}
            </p>
            <p className={`font-display text-xl ${day.is_today ? "text-ink" : "text-ink/82"}`}>
              {formatMonthLabel(day.date)}
            </p>
          </div>
          {day.is_today && (
            <span className="rounded-full border border-gold/40 bg-gold/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-ink">
              Oggi
            </span>
          )}
          {day.is_closed && (
            <span className="rounded-full border border-stone/60 bg-ivory/60 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-ink/50">
              {day.closure_label ?? "Chiuso"}
            </span>
          )}
        </div>
        {!day.is_closed && day.total_booked_covers > 0 && (
          <p className="shrink-0 text-sm text-ink/48">
            <span className="font-semibold text-ink">{day.total_booking_count}</span>{" "}
            {day.total_booking_count === 1 ? "prenotazione" : "prenotazioni"} ·{" "}
            <span className="font-semibold text-ink">{day.total_booked_covers}</span> coperti
          </p>
        )}
      </div>

      {!day.is_closed && day.turni.length > 0 && (
        <div className="flex flex-wrap gap-2.5 p-4">
          {day.turni.map((turno) => (
            <TurnoChip key={`${day.date}-${turno.turno}`} date={day.date} turno={turno} />
          ))}
        </div>
      )}
    </article>
  );
}

function TurnoChip({ date, turno }: { date: string; turno: OwnerAgendaTurno }) {
  const pct = Math.min(turno.occupancy_ratio * 100, 100);

  return (
    <Link
      href={`/bookings?date=${date}&turno=${encodeURIComponent(turno.turno)}`}
      className="flex min-w-[170px] flex-1 flex-col gap-2.5 rounded-[1.1rem] border border-stone/55 bg-white/66 px-4 py-3 transition hover:border-gold/70 hover:bg-white hover:shadow-[0_12px_24px_-22px_rgba(29,22,18,0.24)]"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink">{turno.turno}</p>
          <p className="text-[11px] text-ink/45">{turno.start} – {turno.end}</p>
        </div>
        <span className={`text-[11px] font-semibold ${fullnessColor[turno.fullness]}`}>
          {fullnessLabel[turno.fullness]}
        </span>
      </div>
      <div>
        <div className="h-1.5 overflow-hidden rounded-full bg-stone/28">
          <div
            className={`h-full rounded-full ${fullnessBar[turno.fullness]}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="mt-1.5 text-sm font-semibold text-ink">
          {turno.booking_count} {turno.booking_count === 1 ? "prenotazione" : "prenotazioni"}
        </p>
        <p className="text-xs text-ink/48">
          {turno.booked_covers}
          <span className="text-ink/42">/{turno.max_covers} coperti</span>
        </p>
      </div>
    </Link>
  );
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("it-IT", { day: "2-digit", month: "short" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function formatDayNumber(value: string) {
  return new Intl.DateTimeFormat("it-IT", { day: "2-digit" }).format(new Date(`${value}T12:00:00`));
}

function formatMonthLabel(value: string) {
  return new Intl.DateTimeFormat("it-IT", { month: "short" }).format(new Date(`${value}T12:00:00`));
}

function formatTurnoName(value: string) {
  const normalized = value.trim();
  if (!normalized) {
    return "Servizio";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}
