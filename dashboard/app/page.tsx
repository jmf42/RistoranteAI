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
        <div className="space-y-5">
          {/* KPI strip */}
          <div className="grid gap-3 sm:grid-cols-3">
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
                  ? `${alertDays} servizi da controllare`
                  : "Tutto ok"
              }
            />
          </div>

          {/* Week */}
          <div className="space-y-2">
            {agenda.days.map((day) => <DayRow key={day.date} day={day} />)}
          </div>

          <div className="pt-1 text-center">
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
    tone === "alert" ? "border-terracotta/25 bg-terracotta/8" :
    tone === "warn"  ? "border-gold/30 bg-gold/8" :
    tone === "calm"  ? "border-olive/25 bg-olive/8" :
    "border-stone/80 bg-white/80";

  return (
    <article className={`flex items-center gap-4 rounded-[1.5rem] border p-4 shadow-card ${bg}`}>
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ivory text-ink/50">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/42">{label}</p>
        <p className="mt-0.5 font-display text-3xl text-ink">{value}</p>
        {sub ? <p className="mt-0.5 truncate text-xs text-ink/48">{sub}</p> : null}
      </div>
    </article>
  );
}

function DayRow({ day }: { day: OwnerAgendaDay }) {
  const isAlert = day.turni.some((t) => t.fullness === "overbooked-risk");

  return (
    <article
      className={`overflow-hidden rounded-[1.5rem] border transition-shadow ${
        day.is_today
          ? "border-gold/45 bg-[linear-gradient(150deg,rgba(255,253,248,0.98),rgba(250,240,218,0.95))] shadow-card"
          : isAlert
          ? "border-terracotta/30 bg-white/85"
          : "border-stone/70 bg-white/82"
      }`}
    >
      <div
        className={`flex items-center justify-between gap-4 px-5 py-4 ${
          day.is_today ? "border-b border-gold/25" :
          day.is_closed || !day.turni.length ? "" :
          "border-b border-stone/55"
        }`}
      >
        <div className="flex items-center gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-terracotta/55">
              {day.weekday_label}
            </p>
            <p className={`font-display text-xl ${day.is_today ? "text-ink" : "text-ink/80"}`}>
              {formatShortDate(day.date)}
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
      className="flex min-w-[160px] flex-1 flex-col gap-2.5 rounded-[1.2rem] border border-stone/65 bg-ivory/55 px-4 py-3 transition hover:border-gold hover:bg-white"
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
          {turno.booked_covers}
          <span className="font-normal text-ink/42">/{turno.max_covers}</span>
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
