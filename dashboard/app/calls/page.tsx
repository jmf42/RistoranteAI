"use client";

import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Heatmap } from "@/components/heatmap";
import { SectionCard } from "@/components/section-card";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiDownload, apiFetch, queryString } from "@/lib/api";
import {
  formatCallOutcomeLabel,
  formatCallStatusLabel,
  getCallPresentation,
} from "@/lib/call-presenter";
import { formatDateTime } from "@/lib/format";
import { CallLog, TranscriptResponse, TrendBundle } from "@/lib/types";

const callOutcomes = [
  { value: "", label: "Tutti gli esiti" },
  { value: "booking_created", label: "Prenotazione creata" },
  { value: "booking_modified", label: "Prenotazione modificata" },
  { value: "booking_cancelled", label: "Prenotazione cancellata" },
  { value: "info_provided", label: "Info fornite" },
  { value: "escalated", label: "Trasferita a umano" },
  { value: "abandoned", label: "Abbandonata" },
  { value: "tool_error", label: "Errore tecnico" }
];

export default function CallsPage() {
  const { activeRestaurantId } = useWorkspace();
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [trends, setTrends] = useState<TrendBundle | null>(null);
  const [transcript, setTranscript] = useState<TranscriptResponse | null>(null);
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [days, setDays] = useState(14);
  const [outcome, setOutcome] = useState("");
  const [loadingCalls, setLoadingCalls] = useState(true);
  const [loadingTranscript, setLoadingTranscript] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedCall = calls.find((call) => call.id === selectedCallId) ?? null;
  const followUpCount = calls.filter(
    (call) => call.call_status === "failed" || call.outcome === "tool_error" || call.outcome === "abandoned",
  ).length;
  const createdCount = calls.filter((call) => call.outcome === "booking_created").length;

  useEffect(() => {
    if (!activeRestaurantId) return;
    let ignore = false;
    setLoadingCalls(true);
    setError(null);
    Promise.all([
      apiFetch<CallLog[]>(
        `/api/calls${queryString({ restaurant_id: activeRestaurantId, days, outcome: outcome || undefined })}`
      ),
      apiFetch<TrendBundle>(
        `/api/analytics/trends${queryString({ restaurant_id: activeRestaurantId, days })}`
      )
    ]).then(([callsPayload, trendPayload]) => {
      if (ignore) return;
      setCalls(callsPayload);
      setTrends(trendPayload);
      setSelectedCallId((current) =>
        current && !callsPayload.some((call) => call.id === current) ? null : current
      );
      setTranscript((current) =>
        current && !callsPayload.some((call) => call.id === current.call_id) ? null : current
      );
    }).catch((fetchError: unknown) => {
      if (ignore) return;
      const message = fetchError instanceof ApiError ? fetchError.message : "Impossibile caricare le chiamate.";
      setError(message);
    }).finally(() => {
      if (!ignore) {
        setLoadingCalls(false);
      }
    });
    return () => {
      ignore = true;
    };
  }, [activeRestaurantId, days, outcome]);

  async function loadTranscript(callId: string) {
    if (!activeRestaurantId) {
      return;
    }
    setSelectedCallId(callId);
    setLoadingTranscript(true);
    setError(null);
    try {
      const payload = await apiFetch<TranscriptResponse>(
        `/api/calls/${callId}/transcript${queryString({ restaurant_id: activeRestaurantId })}`
      );
      setTranscript(payload);
    } catch (fetchError) {
      const message =
        fetchError instanceof ApiError ? fetchError.message : "Impossibile caricare il transcript.";
      setError(message);
      setTranscript(null);
    } finally {
      setLoadingTranscript(false);
    }
  }

  async function exportCalls() {
    if (!activeRestaurantId) {
      return;
    }
    setError(null);
    try {
      await apiDownload(
        `/api/calls/export${queryString({
          restaurant_id: activeRestaurantId,
          days,
          outcome: outcome || undefined,
        })}`,
        "calls.csv",
      );
    } catch (fetchError) {
      const message =
        fetchError instanceof ApiError ? fetchError.message : "Export chiamate non riuscito.";
      setError(message);
    }
  }

  return (
    <DashboardShell
      title="Chiamate"
      subtitle="Vedi subito cosa è andato bene, cosa richiede follow-up e apri il dettaglio solo quando serve."
    >
      <div className="grid gap-6 xl:grid-cols-[0.58fr_0.42fr]">
        <div className="min-w-0 space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-[1.45rem] border border-stone/80 bg-white/80 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                Chiamate nel periodo
              </p>
              <p className="mt-3 font-display text-4xl text-ink">{calls.length}</p>
            </div>
            <div className="rounded-[1.45rem] border border-stone/80 bg-white/80 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                Prenotazioni chiuse
              </p>
              <p className="mt-3 font-display text-4xl text-ink">{createdCount}</p>
            </div>
            <div className="rounded-[1.45rem] border border-stone/80 bg-white/80 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                Da seguire
              </p>
              <p className="mt-3 font-display text-4xl text-ink">{followUpCount}</p>
            </div>
          </div>

          <SectionCard title="Registro chiamate" kicker={`Ultimi ${days} giorni`}>
            <div className="mb-5 grid gap-4 sm:grid-cols-2">
              <label className="grid gap-2 text-sm text-ink/65">
                Finestra dati
                <select
                  className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                  value={days}
                  onChange={(event) => setDays(Number(event.target.value))}
                >
                  <option value={7}>Ultimi 7 giorni</option>
                  <option value={14}>Ultimi 14 giorni</option>
                  <option value={30}>Ultimi 30 giorni</option>
                </select>
              </label>

              <label className="grid gap-2 text-sm text-ink/65">
                Esito
                <select
                  className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
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
            </div>
            <div className="mb-5 flex justify-stretch sm:justify-end">
              <button
                type="button"
                onClick={() => void exportCalls()}
                className="w-full rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-ink/70 sm:w-auto"
              >
                Export CSV
              </button>
            </div>

            {loadingCalls ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="h-28 animate-pulse rounded-[1.45rem] bg-white/70" />
                ))}
              </div>
            ) : calls.length ? (
              <div className="space-y-3">
                {calls.map((call) => (
                  <CallRow
                    key={call.id}
                    call={call}
                    isSelected={selectedCallId === call.id}
                    onOpen={() => {
                      void loadTranscript(call.id);
                    }}
                  />
                ))}
              </div>
            ) : (
              <p className="rounded-[1.45rem] border border-dashed border-stone px-4 py-10 text-sm text-ink/55">
                Nessuna chiamata trovata con i filtri correnti.
              </p>
            )}
          </SectionCard>

          <SectionCard title="Volume per fascia oraria" kicker="Heatmap">
            {trends ? (
              <Heatmap cells={trends.heatmap} />
            ) : (
              <div className="h-64 animate-pulse rounded-[1.6rem] bg-ivory/70" />
            )}
          </SectionCard>
        </div>

        <div className="min-w-0 space-y-6">
          <SectionCard title="Dettaglio chiamata" kicker="Su richiesta">
            {error ? (
              <p className="rounded-[1.45rem] border border-terracotta/30 bg-terracotta/10 px-4 py-4 text-sm text-terracotta">
                {error}
              </p>
            ) : null}
            {loadingTranscript ? (
              <div className="space-y-3">
                <div className="h-24 animate-pulse rounded-[1.45rem] bg-ivory/70" />
                <div className="h-64 animate-pulse rounded-[1.45rem] bg-white/70" />
              </div>
            ) : transcript && selectedCall ? (
              <div className="space-y-4">
                <div className="rounded-[1.45rem] border border-stone/80 bg-ivory/70 p-4">
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full border border-stone/80 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/65">
                      {formatCallOutcomeLabel(selectedCall.outcome)}
                    </span>
                    <span
                      className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                        selectedCall.call_status === "failed"
                          ? "bg-terracotta/10 text-terracotta"
                          : "bg-olive/10 text-olive"
                      }`}
                    >
                      {formatCallStatusLabel(selectedCall.call_status)}
                    </span>
                  </div>
                  <p className="mt-3 font-semibold text-ink">{getCallPresentation(selectedCall).headline}</p>
                  <p className="mt-2 text-sm leading-7 text-ink/70">{getCallPresentation(selectedCall).nextStep}</p>
                  <dl className="mt-4 grid gap-3 text-sm text-ink/65 sm:grid-cols-2">
                    <div>
                      <dt className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/45">Quando</dt>
                      <dd className="mt-1">{formatDateTime(selectedCall.started_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/45">Durata</dt>
                      <dd className="mt-1">
                        {Math.floor(selectedCall.duration_seconds / 60)}:
                        {String(selectedCall.duration_seconds % 60).padStart(2, "0")}
                      </dd>
                    </div>
                  </dl>
                </div>
                <div className="rounded-[1.45rem] border border-stone/80 bg-white/80 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                    Riassunto
                  </p>
                  <p className="mt-3 text-sm leading-7 text-ink/70">{transcript.summary}</p>
                </div>
                <details className="rounded-[1.45rem] border border-stone/80 bg-white/80 p-4">
                  <summary className="cursor-pointer text-sm font-semibold text-ink">
                    Mostra trascrizione completa
                  </summary>
                  <div className="mt-4 space-y-3">
                    {transcript.metadata.status ? (
                      <div className="rounded-[1.2rem] border border-stone/70 bg-ivory/60 px-4 py-3 text-xs uppercase tracking-[0.24em] text-ink/45">
                        Fonte {transcript.source} · stato conversazione {String(transcript.metadata.status)}
                      </div>
                    ) : null}
                    <pre className="overflow-x-auto whitespace-pre-wrap rounded-[1.2rem] border border-stone/70 bg-ivory/50 p-4 text-sm leading-7 text-ink/72">
                      {transcript.transcript ?? "Nessuna trascrizione disponibile."}
                    </pre>
                  </div>
                </details>
              </div>
            ) : (
              <p className="rounded-[1.45rem] border border-dashed border-stone px-4 py-10 text-sm text-ink/55">
                Seleziona una chiamata dalla lista per vedere solo il riassunto operativo e, se ti serve,
                aprire la trascrizione completa.
              </p>
            )}
          </SectionCard>

          <SectionCard title="Da osservare" kicker="Supervisione">
            <div className="space-y-3">
              {trends?.escalations.length ? (
                trends.escalations.map((item) => (
                  <article
                    key={item.outcome}
                    className="rounded-[1.35rem] border border-stone/80 bg-ivory/70 p-4"
                  >
                    <p className="font-semibold capitalize text-ink">
                      {item.outcome.replaceAll("_", " ")}
                    </p>
                    <p className="mt-2 text-sm text-ink/60">{item.total} chiamate nel periodo.</p>
                  </article>
                ))
              ) : (
                <p className="rounded-[1.35rem] border border-dashed border-stone px-4 py-8 text-sm text-ink/55">
                  Nessun segnale di escalation nel periodo selezionato.
                </p>
              )}
            </div>
          </SectionCard>
        </div>
      </div>
    </DashboardShell>
  );
}

function CallRow({
  call,
  isSelected,
  onOpen,
}: {
  call: CallLog;
  isSelected: boolean;
  onOpen: () => void;
}) {
  const presentation = getCallPresentation(call);

  return (
    <button
      type="button"
      onClick={onOpen}
      className={`w-full rounded-[1.45rem] border p-4 text-left transition ${
        isSelected
          ? "border-gold bg-ivory/80 shadow-[0_24px_60px_rgba(52,44,37,0.08)]"
          : "border-stone/80 bg-white/80 hover:border-gold"
      }`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                presentation.needsAttention ? "bg-terracotta" : call.call_status === "successful" ? "bg-olive" : "bg-stone"
              }`}
            />
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-terracotta/70">
              {presentation.label}
            </span>
            {presentation.needsAttention ? (
              <span className="rounded-full bg-terracotta/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-terracotta">
                attenzione
              </span>
            ) : null}
          </div>
          <p className="mt-3 font-semibold text-ink">{presentation.headline}</p>
          <p className="mt-2 text-sm leading-6 text-ink/65">{presentation.preview}</p>
        </div>
        <div className="text-xs uppercase tracking-[0.22em] text-ink/40 sm:text-right">
          <p>{formatDateTime(call.started_at)}</p>
          <p className="mt-2">
            {Math.floor(call.duration_seconds / 60)}:{String(call.duration_seconds % 60).padStart(2, "0")}
          </p>
          <p className={`mt-1 ${call.call_status === "failed" ? "text-terracotta" : ""}`}>
            {formatCallStatusLabel(call.call_status)}
          </p>
        </div>
      </div>
    </button>
  );
}
