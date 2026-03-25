"use client";

import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Heatmap } from "@/components/heatmap";
import { SectionCard } from "@/components/section-card";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiDownload, apiFetch, queryString } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { CallLog, TranscriptResponse, TrendBundle } from "@/lib/types";

const callOutcomes = [
  { value: "", label: "Tutti gli esiti" },
  { value: "booking_created", label: "Prenotazione creata" },
  { value: "booking_modified", label: "Prenotazione modificata" },
  { value: "booking_cancelled", label: "Prenotazione cancellata" },
  { value: "info_provided", label: "Info fornite" },
  { value: "escalated", label: "Trasferita a umano" },
  { value: "abandoned", label: "Abbandonata" }
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
      subtitle="Controlla esiti, durata e qualità del presidio telefonico, poi entra nel dettaglio delle conversazioni che meritano attenzione."
    >
      <div className="grid gap-6 xl:grid-cols-[0.58fr_0.42fr]">
        <div className="space-y-6">
          <SectionCard title="Registro chiamate" kicker={`Ultimi ${days} giorni`}>
            <div className="mb-5 grid gap-4 md:grid-cols-2">
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
            <div className="mb-5 flex justify-end">
              <button
                type="button"
                onClick={() => void exportCalls()}
                className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-ink/70"
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
                  <button
                    key={call.id}
                    type="button"
                    onClick={() => {
                      void loadTranscript(call.id);
                    }}
                    className={`w-full rounded-[1.45rem] border p-4 text-left transition ${
                      selectedCallId === call.id
                        ? "border-gold bg-ivory/80 shadow-[0_24px_60px_rgba(52,44,37,0.08)]"
                        : "border-stone/80 bg-white/80 hover:border-gold"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-semibold capitalize text-ink">
                          {call.outcome.replaceAll("_", " ")}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-ink/65">{call.summary}</p>
                      </div>
                      <div className="text-right text-xs uppercase tracking-[0.22em] text-ink/40">
                        <p>{formatDateTime(call.started_at)}</p>
                        <p className="mt-2">{Math.floor(call.duration_seconds / 60)}:{String(call.duration_seconds % 60).padStart(2, "0")}</p>
                      </div>
                    </div>
                  </button>
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

        <div className="space-y-6">
          <SectionCard title="Anteprima trascrizione" kicker="Su richiesta">
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
            ) : transcript ? (
              <div className="space-y-4">
                <div className="rounded-[1.45rem] border border-stone/80 bg-ivory/70 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-terracotta/70">
                    Fonte {transcript.source}
                  </p>
                  <p className="mt-3 text-sm leading-7 text-ink/70">{transcript.summary}</p>
                </div>
                {transcript.metadata.status ? (
                  <div className="rounded-[1.2rem] border border-stone/70 bg-white/70 px-4 py-3 text-xs uppercase tracking-[0.24em] text-ink/45">
                    Stato conversazione {String(transcript.metadata.status)}
                  </div>
                ) : null}
                <pre className="whitespace-pre-wrap rounded-[1.45rem] border border-stone/80 bg-white/80 p-4 text-sm leading-7 text-ink/72">
                  {transcript.transcript ?? "Nessuna trascrizione disponibile. Collega l'API ElevenLabs per il recupero completo."}
                </pre>
              </div>
            ) : (
              <p className="rounded-[1.45rem] border border-dashed border-stone px-4 py-10 text-sm text-ink/55">
                Seleziona una chiamata dalla lista per visualizzare l'anteprima o la trascrizione completa se
                la chiave ElevenLabs è configurata.
              </p>
            )}
          </SectionCard>

          <SectionCard title="Dettaglio escalation" kicker="Supervisione">
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
                  Nessuna escalation registrata nei dati correnti.
                </p>
              )}
            </div>
          </SectionCard>
        </div>
      </div>
    </DashboardShell>
  );
}
