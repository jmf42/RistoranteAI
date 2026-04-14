"use client";

import {
  Activity,
  Calendar,
  CheckCircle2,
  Clock,
  Info,
  Phone,
  Search,
  Users,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { StatusBadge } from "@/components/status-badge";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiDownload, apiFetch, queryString } from "@/lib/api";
import {
  formatCallOutcomeLabel,
  formatCallStatusLabel,
  getCallOperationalStatusLabel,
  getCallPresentation,
  isFollowUpCall,
} from "@/lib/call-presenter";
import { formatDateTime } from "@/lib/format";
import { CallLog, TranscriptResponse } from "@/lib/types";

const callOutcomes = [
  { value: "", label: "Tutti" },
  { value: "booking_created", label: "Prenotate" },
  { value: "booking_modified", label: "Modificate" },
  { value: "booking_cancelled", label: "Cancellate" },
  { value: "info_provided", label: "Info" },
  { value: "escalated", label: "Passate al ristorante" },
  { value: "abandoned", label: "Interrotte" },
  { value: "tool_error", label: "Errori" },
];

const toolLabels: Record<string, string> = {
  check_availability: "Verifica disponibilità",
  find_booking: "Ricerca prenotazione",
  create_booking: "Creazione prenotazione",
  modify_booking: "Modifica prenotazione",
  cancel_booking: "Cancellazione prenotazione",
  escalate_to_human: "Trasferimento al ristorante",
};

export default function CallsPage() {
  const { activeRestaurantId } = useWorkspace();
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [transcript, setTranscript] = useState<TranscriptResponse | null>(null);
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [days, setDays] = useState(14);
  const [outcome, setOutcome] = useState("");
  const [search, setSearch] = useState("");
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [sort, setSort] = useState("follow_up");
  const [loadingCalls, setLoadingCalls] = useState(true);
  const [loadingTranscript, setLoadingTranscript] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCall = calls.find((call) => call.id === selectedCallId) ?? null;

  useEffect(() => {
    if (!activeRestaurantId) return;

    let ignore = false;
    setLoadingCalls(true);
    setError(null);

    void apiFetch<CallLog[]>(
      `/api/calls${queryString({
        restaurant_id: activeRestaurantId,
        days,
        outcome: outcome || undefined,
        search: search.trim() || undefined,
        attention_only: attentionOnly ? "true" : undefined,
        sort,
      })}`,
    )
      .then((payload) => {
        if (ignore) return;
        setCalls(payload);
        setSelectedCallId((current) => current && payload.some((item) => item.id === current) ? current : payload[0]?.id ?? null);
      })
      .catch((caught: unknown) => {
        if (!ignore) {
          setCalls([]);
          setSelectedCallId(null);
          setError(caught instanceof ApiError ? caught.message : "Impossibile caricare le chiamate.");
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoadingCalls(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [activeRestaurantId, attentionOnly, days, outcome, search, sort]);

  useEffect(() => {
    if (!selectedCallId || !activeRestaurantId) {
      setTranscript(null);
      return;
    }

    let ignore = false;
    setLoadingTranscript(true);
    setError(null);

    void apiFetch<TranscriptResponse>(
      `/api/calls/${selectedCallId}/transcript${queryString({ restaurant_id: activeRestaurantId })}`,
    )
      .then((payload) => {
        if (!ignore) {
          setTranscript(payload);
        }
      })
      .catch((caught: unknown) => {
        if (!ignore) {
          setTranscript(null);
          setError(caught instanceof ApiError ? caught.message : "Impossibile caricare il transcript.");
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoadingTranscript(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [activeRestaurantId, selectedCallId]);

  const followUpCount = useMemo(() => calls.filter((call) => isFollowUpCall(call)).length, [calls]);

  async function exportCalls() {
    if (!activeRestaurantId) return;
    setError(null);
    try {
      await apiDownload(
        `/api/calls/export${queryString({ restaurant_id: activeRestaurantId, days, outcome: outcome || undefined })}`,
        "calls.csv",
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Export non riuscito.");
    }
  }

  return (
    <DashboardShell
      title="Chiamate"
      subtitle="Cosa è successo al telefono e cosa richiede attenzione."
    >
      <div className="space-y-6">
        <div className="grid gap-3 md:grid-cols-[1.5fr_1fr_1fr]">
          <StatCard label="Nel periodo" value={`${calls.length}`} detail="Chiamate filtrate." />
          <StatCard label="Da seguire" value={`${followUpCount}`} detail="Fallite, interrotte o con problemi tecnici." tone={followUpCount > 0 ? "alert" : "calm"} />
          <StatCard
            label="Prenotazioni chiuse"
            value={`${calls.filter((call) => call.outcome === "booking_created").length}`}
            detail="Chiamate concluse con una nuova prenotazione."
          />
        </div>

        <section className="rounded-[2rem] border border-stone/80 bg-white/82 p-5 shadow-card sm:p-6">
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
            <label className="min-w-0">
              <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Cerca</span>
              <div className="flex items-center gap-3 rounded-[1.2rem] border border-stone bg-ivory/70 px-4 py-3">
                <Search size={16} className="shrink-0 text-ink/35" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Riassunto, transcript, riferimento..."
                  className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink/35"
                />
              </div>
            </label>

            <label>
              <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Periodo</span>
              <select
                className="w-full rounded-[1.2rem] border border-stone bg-ivory/70 px-4 py-3 text-sm text-ink outline-none focus:border-gold"
                value={days}
                onChange={(event) => setDays(Number(event.target.value))}
              >
                <option value={7}>7 giorni</option>
                <option value={14}>14 giorni</option>
                <option value={30}>30 giorni</option>
              </select>
            </label>

            <label>
              <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Esito</span>
              <select
                className="w-full rounded-[1.2rem] border border-stone bg-ivory/70 px-4 py-3 text-sm text-ink outline-none focus:border-gold"
                value={outcome}
                onChange={(event) => setOutcome(event.target.value)}
              >
                {callOutcomes.map((item) => (
                  <option key={item.value || "all"} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex flex-col justify-end gap-3 sm:flex-row xl:flex-col">
              <label className="inline-flex items-center gap-3 rounded-[1.2rem] border border-stone bg-ivory/70 px-4 py-3 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={attentionOnly}
                  onChange={(event) => setAttentionOnly(event.target.checked)}
                  className="h-4 w-4 rounded border-stone text-ink focus:ring-gold"
                />
                Solo da seguire
              </label>
              <button
                type="button"
                onClick={() => void exportCalls()}
                className="rounded-[1.2rem] border border-stone px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
              >
                CSV
              </button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {[
              { value: "follow_up", label: "Da seguire prima" },
              { value: "newest", label: "Più recenti" },
              { value: "longest", label: "Più lunghe" },
            ].map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setSort(item.value)}
                className={`rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] transition ${
                  sort === item.value
                    ? "border-gold bg-gold/12 text-ink"
                    : "border-stone bg-white/75 text-ink/55 hover:border-gold"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-[0.54fr_0.46fr]">
          <section className="min-w-0 rounded-[2rem] border border-stone/80 bg-white/82 p-4 shadow-card sm:p-5">
            {loadingCalls ? (
              <div className="space-y-3">
                {[0, 1, 2].map((index) => (
                  <div key={index} className="h-28 animate-pulse rounded-[1.35rem] bg-ivory/70" />
                ))}
              </div>
            ) : calls.length ? (
              <div className="space-y-3">
                {calls.map((call) => (
                  <button
                    key={call.id}
                    type="button"
                    onClick={() => setSelectedCallId(call.id)}
                    className={`w-full rounded-[1.4rem] border p-4 text-left transition ${
                      selectedCallId === call.id
                        ? "border-gold bg-ivory/70"
                        : isFollowUpCall(call)
                          ? "border-terracotta/25 bg-terracotta/6 hover:border-terracotta/40"
                          : "border-stone/80 bg-white/75 hover:border-gold"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <StatusBadge tone={isFollowUpCall(call) ? "danger" : "neutral"}>
                            {formatCallOutcomeLabel(call.outcome)}
                          </StatusBadge>
                          <StatusBadge tone={isFollowUpCall(call) ? "danger" : "good"}>
                            {getCallOperationalStatusLabel(call)}
                          </StatusBadge>
                        </div>
                        <p className="mt-3 font-semibold text-ink">{getCallPresentation(call).headline}</p>
                        <p className="mt-1 line-clamp-2 text-sm leading-6 text-ink/62">
                          {call.summary || "Nessun riassunto disponibile."}
                        </p>
                      </div>
                      <div className="shrink-0 text-right text-xs text-ink/42">
                        <p>{formatDateTime(call.started_at)}</p>
                        <p className="mt-2">{formatDuration(call.duration_seconds)}</p>
                        {call.caller_phone ? <p className="mt-2 font-mono">{call.caller_phone}</p> : null}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="rounded-[1.4rem] border border-dashed border-stone px-4 py-10 text-center text-sm text-ink/50">
                Nessuna chiamata nel periodo selezionato.
              </p>
            )}
          </section>

          <section className="rounded-[2rem] border border-stone/80 bg-[linear-gradient(180deg,rgba(255,252,246,0.96),rgba(245,238,228,0.92))] p-5 shadow-card sm:p-6">
            {error ? (
              <p className="rounded-[1.3rem] border border-terracotta/30 bg-terracotta/10 px-4 py-3 text-sm text-terracotta">
                {error}
              </p>
            ) : null}

            {loadingTranscript ? (
              <div className="h-64 animate-pulse rounded-[1.6rem] bg-white/70" />
            ) : transcript && selectedCall ? (
              <div className="space-y-5">
                <div className="flex flex-wrap gap-2">
                  <StatusBadge tone={selectedCall.call_status === "failed" ? "danger" : "neutral"}>
                    {formatCallOutcomeLabel(selectedCall.outcome)}
                  </StatusBadge>
                  <StatusBadge tone={isFollowUpCall(selectedCall) ? "danger" : "good"}>
                    {getCallOperationalStatusLabel(selectedCall)}
                  </StatusBadge>
                </div>

                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Riassunto</p>
                  <p className="mt-3 text-base leading-7 text-ink/74">{transcript.summary}</p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <MetaBlock icon={<Calendar size={14} />} label="Quando (Chiamata)" value={formatDateTime(selectedCall.started_at)} />
                  <MetaBlock icon={<Clock size={14} />} label="Durata" value={formatDuration(selectedCall.duration_seconds)} />
                  <MetaBlock icon={<Phone size={14} />} label="Chiamante" value={selectedCall.caller_phone || "—"} />
                  <MetaBlock icon={<Users size={14} />} label="Persona" value={selectedCall.customer_name || "—"} />
                  <MetaBlock icon={<Users size={14} />} label="Coperti richiesti" value={selectedCall.party_size ? String(selectedCall.party_size) : "—"} />
                  <MetaBlock icon={<Calendar size={14} />} label="Giorno richiesto" value={selectedCall.requested_date || "—"} />
                  <MetaBlock icon={<Clock size={14} />} label="Orario richiesto" value={selectedCall.requested_time || "—"} />
                  <MetaBlock icon={<Info size={14} />} label="Esito tecnico" value={formatCallStatusLabel(selectedCall.call_status)} />
                  <MetaBlock icon={<CheckCircle2 size={14} />} label="Booking linked" value={selectedCall.booking_id || "Nessuna"} />
                </div>

                <div className="rounded-[1.45rem] border border-stone/80 bg-white/82 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Prossimo passo</p>
                  <p className="mt-2 text-sm leading-6 text-ink/68">{getCallPresentation(selectedCall).nextStep}</p>
                </div>

                <details className="rounded-[1.45rem] border border-stone/80 bg-white/82 p-4">
                  <summary className="cursor-pointer text-sm font-semibold text-ink">Trascrizione completa</summary>
                  <pre className="mt-4 whitespace-pre-wrap text-sm leading-7 text-ink/66">
                    {transcript.transcript ?? "Nessuna trascrizione disponibile."}
                  </pre>
                </details>

                {transcript.metadata.tool_events &&
                Array.isArray(transcript.metadata.tool_events) &&
                transcript.metadata.tool_events.length > 0 ? (
                  <details className="rounded-[1.45rem] border border-stone/80 bg-white/82 p-4">
                    <summary className="cursor-pointer text-sm font-semibold text-ink">
                      Attività tecnica dell&apos;agente
                    </summary>
                    <div className="mt-4 space-y-4">
                      {(transcript.metadata.tool_events as any[]).map((event, idx) => (
                        <div
                          key={idx}
                          className="rounded-[1.1rem] border border-stone/40 bg-ivory/30 p-3"
                        >
                          <div className="flex items-center gap-2">
                            <div
                              className={`rounded-full p-1.5 ${
                                event.result?.success === false || event.result?.available === false
                                  ? "bg-terracotta/10 text-terracotta"
                                  : "bg-olive/10 text-olive"
                              }`}
                            >
                              <Activity size={12} />
                            </div>
                            <span className="text-xs font-bold uppercase tracking-wider text-ink/70">
                              {toolLabels[event.tool] || event.tool}
                            </span>
                          </div>

                          <div className="mt-2 grid gap-2 text-xs text-ink/60 sm:grid-cols-2">
                            <div className="space-y-1">
                              <p className="font-semibold text-ink/40 uppercase tracking-tighter">Richiesta</p>
                              {event.arguments &&
                                Object.entries(event.arguments).map(([k, v]) => (
                                  <p key={k}>
                                    <span className="capitalize">{k}</span>:{" "}
                                    <span className="font-medium text-ink/80">{String(v)}</span>
                                  </p>
                                ))}
                            </div>
                            <div className="space-y-1">
                              <p className="font-semibold text-ink/40 uppercase tracking-tighter">Risultato</p>
                              {event.result && (
                                <>
                                  <p>
                                    Stato:{" "}
                                    <span
                                      className={`font-medium ${
                                        event.result.success === false ||
                                        event.result.available === false
                                          ? "text-terracotta"
                                          : "text-olive"
                                      }`}
                                    >
                                      {event.result.success === false ||
                                      event.result.available === false
                                        ? "Fallito / Non disponibile"
                                        : "Successo / Disponibile"}
                                    </span>
                                  </p>
                                  {event.result.reason && (
                                    <p className="italic text-terracotta/80">{event.result.reason}</p>
                                  )}
                                  {event.result.confirmation_code && (
                                    <p>
                                      Codice:{" "}
                                      <span className="font-mono font-bold text-ink">
                                        {event.result.confirmation_code}
                                      </span>
                                    </p>
                                  )}
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}
              </div>
            ) : (
              <div className="rounded-[1.45rem] border border-dashed border-stone px-4 py-12 text-center text-sm text-ink/50">
                Seleziona una chiamata per leggere riassunto e transcript.
              </div>
            )}
          </section>
        </div>
      </div>
    </DashboardShell>
  );
}

function StatCard({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "default" | "calm" | "alert";
}) {
  const toneStyles =
    tone === "alert"
      ? "border-terracotta/25 bg-terracotta/8"
      : tone === "calm"
        ? "border-olive/25 bg-olive/8"
        : "border-stone/80 bg-white/80";

  return (
    <article className={`rounded-[1.5rem] border p-5 shadow-card ${toneStyles}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{label}</p>
      <p className="mt-3 font-display text-4xl text-ink">{value}</p>
      <p className="mt-2 text-sm leading-6 text-ink/60">{detail}</p>
    </article>
  );
}

function MetaBlock({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-[1.25rem] border border-stone/75 bg-white/82 p-4">
      <div className="flex items-center gap-2">
        {icon && <span className="text-ink/35">{icon}</span>}
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/42">{label}</p>
      </div>
      <p className="mt-2 text-sm font-medium text-ink/72">{value}</p>
    </div>
  );
}

function formatDuration(durationSeconds: number) {
  return `${Math.floor(durationSeconds / 60)}:${String(durationSeconds % 60).padStart(2, "0")}`;
}
