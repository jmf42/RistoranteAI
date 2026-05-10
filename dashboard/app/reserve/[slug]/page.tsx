"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import {
  PublicAvailabilityResponse,
  PublicBookingResponse,
  PublicReservationConfig,
} from "@/lib/types";

function defaultDateValue() {
  const next = new Date();
  next.setDate(next.getDate() + 1);
  return next.toISOString().slice(0, 10);
}

function defaultTimeValue(turni?: Array<{ start: string }>) {
  return `${turni?.[0]?.start ?? "19:30"}:00`;
}

function formatLongDate(value: string) {
  return new Intl.DateTimeFormat("it-IT", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(`${value}T12:00:00`));
}

function formatTurnoLabel(value: string) {
  const normalized = value.trim();
  if (!normalized) {
    return "servizio";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function notificationStatusLabel(value: string) {
  if (value === "queued") return "Email in preparazione";
  if (value === "sent") return "Email inviata";
  if (value === "failed") return "Link pronto, email da verificare";
  return `Stato invio: ${value}`;
}

export default function PublicReservationPage() {
  const params = useParams<{ slug: string }>();
  const slug = Array.isArray(params?.slug) ? params.slug[0] : params?.slug;
  const [config, setConfig] = useState<PublicReservationConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availability, setAvailability] = useState<PublicAvailabilityResponse | null>(null);
  const [confirmation, setConfirmation] = useState<PublicBookingResponse | null>(null);
  const [slotForm, setSlotForm] = useState({
    date: defaultDateValue(),
    time: "19:30:00",
    party_size: 2,
  });
  const [guestForm, setGuestForm] = useState({
    customer_name: "",
    customer_phone: "",
    customer_email: "",
    special_requests: "",
  });

  useEffect(() => {
    if (!slug) {
      return;
    }
    let ignore = false;
    setLoading(true);
    void apiFetch<PublicReservationConfig>(`/api/public/restaurants/${slug}/reservation-config`)
      .then((payload) => {
        if (ignore) {
          return;
        }
        setConfig(payload);
        setSlotForm((current) => ({
          ...current,
          time: defaultTimeValue(payload.turni),
          party_size: payload.online_booking.party_size_min,
        }));
        setError(null);
      })
      .catch((caught) => {
        if (ignore) {
          return;
        }
        setConfig(null);
        setError(caught instanceof ApiError ? caught.message : "Prenotazioni online non disponibili.");
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [slug]);

  const [verifiedSlot, setVerifiedSlot] = useState<string | null>(null);
  const currentSlotKey = `${slotForm.date}|${slotForm.time}|${slotForm.party_size}`;
  const canBook = availability?.result.available === true && verifiedSlot === currentSlotKey;
  const partyOptions = useMemo(() => {
    const min = config?.online_booking.party_size_min ?? 1;
    const max = config?.online_booking.party_size_max ?? 8;
    return Array.from({ length: max - min + 1 }, (_, index) => min + index);
  }, [config?.online_booking.party_size_max, config?.online_booking.party_size_min]);
  const serviceHighlights = useMemo(
    () => [
      ["Conferma immediata", "Niente attese o chiamate perse: l'esito arriva subito."],
      ["Link privato", "Puoi spostare o cancellare senza passare dalla sala."],
      [
        `Fino a ${config?.online_booking.party_size_max ?? 8} persone`,
        "Per tavolate piu' grandi conviene chiamare il ristorante.",
      ],
    ],
    [config?.online_booking.party_size_max],
  );
  const selectedSlotLabel = useMemo(() => {
    const slot = availability?.result.slot;
    if (!slot) {
      return null;
    }
    return `${slot.time.slice(0, 5)} · ${slot.turno}`;
  }, [availability?.result.slot]);
  const selectedVisitSummary = useMemo(() => {
    if (!selectedSlotLabel) {
      return null;
    }
    return `${formatLongDate(slotForm.date)} alle ${selectedSlotLabel.split(" · ")[0]} per ${slotForm.party_size} ${
      slotForm.party_size === 1 ? "persona" : "persone"
    }`;
  }, [selectedSlotLabel, slotForm.date, slotForm.party_size]);

  async function handleAvailability(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slug) {
      return;
    }
    setSearching(true);
    setError(null);
    setConfirmation(null);
    try {
      const payload = await apiFetch<PublicAvailabilityResponse>(
        `/api/public/restaurants/${slug}/availability`,
        {
          method: "POST",
          body: JSON.stringify(slotForm),
        },
      );
      setAvailability(payload);
      setVerifiedSlot(currentSlotKey);
    } catch (caught) {
      setAvailability(null);
      setVerifiedSlot(null);
      setError(caught instanceof ApiError ? caught.message : "Non riesco a verificare la disponibilita'.");
    } finally {
      setSearching(false);
    }
  }

  async function handleBooking(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slug) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const idempotencyKey =
        typeof window !== "undefined" && "crypto" in window && "randomUUID" in window.crypto
          ? window.crypto.randomUUID()
          : `${Date.now()}-${guestForm.customer_phone}`;
      const trimmedEmail = guestForm.customer_email.trim();
      const body = {
        ...slotForm,
        customer_name: guestForm.customer_name.trim(),
        customer_phone: guestForm.customer_phone.trim(),
        customer_email: trimmedEmail ? trimmedEmail : null,
        special_requests: guestForm.special_requests.trim() || null,
      };
      const payload = await apiFetch<PublicBookingResponse>(
        `/api/public/restaurants/${slug}/bookings`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey },
          body: JSON.stringify(body),
        },
      );
      setConfirmation(payload);
    } catch (caught) {
      setConfirmation(null);
      setError(caught instanceof ApiError ? caught.message : "Prenotazione non completata.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto grid w-full max-w-6xl gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="ui-night-surface overflow-hidden rounded-[2rem] px-6 py-7 text-ivory sm:px-8 sm:py-9">
          <p className="ui-kicker text-xs font-semibold uppercase text-gold/74">Prenota il tuo tavolo</p>
          <h1 className="ui-display-title mt-4 font-display text-[3.1rem] leading-[0.92] sm:text-[4.4rem]">
            Una prenotazione chiara,
            <br />
            in stile trattoria.
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-7 text-ivory/70 sm:text-base">
            {config
              ? `${config.restaurant.name} conferma online in tempo reale. Scegli quando venire, lascia i tuoi dettagli e tieni il link privato per eventuali cambi.`
              : "Controlla i posti disponibili e conferma la prenotazione in pochi passaggi."}
          </p>
          {config?.restaurant.address ? (
            <p className="mt-3 max-w-xl text-sm leading-7 text-ivory/58">{config.restaurant.address}</p>
          ) : null}

          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            {serviceHighlights.map(([title, body]) => (
              <article key={title} className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                <p className="font-display text-2xl text-white">{title}</p>
                <p className="mt-2 text-sm text-ivory/64">{body}</p>
              </article>
            ))}
          </div>

          {config ? (
            <div className="mt-8 rounded-[1.6rem] border border-white/10 bg-white/6 p-5">
              <p className="ui-kicker text-[11px] font-semibold uppercase text-gold/76">Come funziona</p>
              <div className="mt-3 grid gap-3 text-sm text-ivory/70">
                <p>
                  1. Scegli data, orario e numero di persone. Ti mostriamo subito se la sala puo' confermare.
                </p>
                <p>2. Inserisci i dati essenziali una sola volta. Il link privato arriva appena la prenotazione e' salvata.</p>
                <p>
                  3. Puoi modificare fino a{" "}
                  <strong className="text-white">{config.online_booking.modify_cutoff_hours}h</strong> prima e cancellare fino a{" "}
                  <strong className="text-white">{config.online_booking.cancel_cutoff_hours}h</strong> prima.
                </p>
              </div>
              <div className="mt-4 rounded-[1.2rem] border border-white/10 bg-black/10 p-4 text-sm leading-7 text-ivory/68">
                <p>
                  Se siete piu' di <strong className="text-white">{config.online_booking.party_size_max}</strong>, meglio
                  contattare il ristorante direttamente: la sala puo' gestire tavoli grandi con piu' cura.
                </p>
              </div>
            </div>
          ) : null}
        </section>

        <section className="ui-shell-surface rounded-[2rem] p-5 sm:p-7">
          <p className="ui-kicker text-xs font-semibold uppercase text-terracotta/70">1. Scegli quando venire</p>
          <form onSubmit={handleAvailability} className="mt-4 grid gap-3">
            <label className="grid gap-2 text-sm text-ink/66">
              Data
              <input
                type="date"
                required
                className="rounded-[1.1rem] border border-stone/80 bg-white/90 px-4 py-3 outline-none transition focus:border-gold"
                value={slotForm.date}
                onChange={(event) => setSlotForm((current) => ({ ...current, date: event.target.value }))}
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-[1.15fr_0.85fr]">
              <label className="grid gap-2 text-sm text-ink/66">
                Ora
                <input
                  type="time"
                  required
                  className="rounded-[1.1rem] border border-stone/80 bg-white/90 px-4 py-3 outline-none transition focus:border-gold"
                  value={slotForm.time.slice(0, 5)}
                  onChange={(event) =>
                    setSlotForm((current) => ({ ...current, time: `${event.target.value}:00` }))
                  }
                />
              </label>
              <label className="grid gap-2 text-sm text-ink/66">
                Persone
                <select
                  className="rounded-[1.1rem] border border-stone/80 bg-white/90 px-4 py-3 outline-none transition focus:border-gold"
                  value={slotForm.party_size}
                  onChange={(event) =>
                    setSlotForm((current) => ({ ...current, party_size: Number(event.target.value) }))
                  }
                >
                  {partyOptions.map((partySize) => (
                    <option key={partySize} value={partySize}>
                      {partySize} {partySize === 1 ? "persona" : "persone"}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {config?.turni?.length ? (
              <div className="flex flex-wrap gap-2 pt-1">
                {config.turni.map((turno) => (
                  <button
                    key={turno.name}
                    type="button"
                    onClick={() => setSlotForm((current) => ({ ...current, time: `${turno.start}:00` }))}
                    className={`rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition ${
                      slotForm.time.slice(0, 5) === turno.start
                        ? "border-gold bg-gold/14 text-ink"
                        : "border-stone bg-white/70 text-ink/62 hover:border-gold"
                    }`}
                  >
                    {formatTurnoLabel(turno.name)} · {turno.start}
                  </button>
                ))}
              </div>
            ) : null}
            <button
              type="submit"
              disabled={searching || loading}
              className="mt-1 rounded-[1.1rem] bg-ink px-5 py-3 text-sm font-semibold uppercase tracking-[0.16em] text-ivory transition hover:bg-night disabled:opacity-60"
            >
              {searching ? "Controllo..." : "Verifica disponibilita'"}
            </button>
          </form>

          {availability ? (
            <div className="mt-5 rounded-[1.5rem] border border-stone/70 bg-white/76 p-4">
              {availability.result.available ? (
                <>
                  <p className="ui-kicker text-[11px] font-semibold uppercase text-olive">Disponibile</p>
                  <p className="mt-2 font-display text-3xl text-ink">{selectedSlotLabel}</p>
                  {selectedVisitSummary ? (
                    <p className="mt-2 text-sm leading-7 text-ink/62">{selectedVisitSummary}</p>
                  ) : null}
                  <p className="mt-3 rounded-[1.1rem] border border-olive/15 bg-olive/8 px-4 py-3 text-sm leading-7 text-ink/62">
                    {config?.online_booking.confirmation_message ??
                      "Inserisci i tuoi dati qui sotto e riceverai subito il riepilogo con link privato."}
                  </p>
                </>
              ) : (
                <>
                  <p className="ui-kicker text-[11px] font-semibold uppercase text-terracotta">Da rivedere</p>
                  <p className="mt-2 text-sm leading-7 text-ink/66">
                    {availability.result.reason ?? "Questo orario non e' disponibile."}
                  </p>
                  {availability.result.alternatives.length ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {availability.result.alternatives.map((option) => (
                        <button
                          key={`${option.turno}-${option.time}`}
                          type="button"
                          onClick={() =>
                            setSlotForm((current) => ({
                              ...current,
                              time: `${option.time}:00`,
                            }))
                          }
                          className="rounded-full border border-stone bg-ivory/80 px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink/68 transition hover:border-gold"
                        >
                          {option.time} · {option.turno}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </>
              )}
            </div>
          ) : null}

          <div className="mt-7 border-t border-stone/70 pt-6">
            <p className="ui-kicker text-xs font-semibold uppercase text-terracotta/70">2. Inserisci i tuoi dettagli</p>
            <p className="mt-3 text-sm leading-7 text-ink/60">
              Ti chiediamo solo quello che serve alla sala per confermare e, se serve, contattarti.
            </p>
            <form onSubmit={handleBooking} className="mt-4 grid gap-3">
              <label className="grid gap-2 text-sm text-ink/66">
                Nome e cognome
                <input
                  type="text"
                  required
                  placeholder="Es. Giulia Rossi"
                  className="rounded-[1.1rem] border border-stone/80 bg-white/90 px-4 py-3 outline-none transition focus:border-gold"
                  value={guestForm.customer_name}
                  onChange={(event) =>
                    setGuestForm((current) => ({ ...current, customer_name: event.target.value }))
                  }
                />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-2 text-sm text-ink/66">
                  Telefono
                  <input
                    type="tel"
                    required
                    placeholder="+39 333 123 4567"
                    className="rounded-[1.1rem] border border-stone/80 bg-white/90 px-4 py-3 outline-none transition focus:border-gold"
                    value={guestForm.customer_phone}
                    onChange={(event) =>
                      setGuestForm((current) => ({ ...current, customer_phone: event.target.value }))
                    }
                  />
                </label>
                <label className="grid gap-2 text-sm text-ink/66">
                  Email
                  <input
                    type="email"
                    required={config?.online_booking.require_email ?? true}
                    placeholder="nome@email.it"
                    className="rounded-[1.1rem] border border-stone/80 bg-white/90 px-4 py-3 outline-none transition focus:border-gold"
                    value={guestForm.customer_email}
                    onChange={(event) =>
                      setGuestForm((current) => ({ ...current, customer_email: event.target.value }))
                    }
                  />
                </label>
              </div>
              <label className="grid gap-2 text-sm text-ink/66">
                Richieste di sala
                <textarea
                  rows={3}
                  placeholder="Seggiolone, allergie da segnalare alla sala, preferenze di posto..."
                  className="rounded-[1.1rem] border border-stone/80 bg-white/90 px-4 py-3 outline-none transition focus:border-gold"
                  value={guestForm.special_requests}
                  onChange={(event) =>
                    setGuestForm((current) => ({ ...current, special_requests: event.target.value }))
                  }
                />
              </label>
              <button
                type="submit"
                disabled={!canBook || submitting}
                className="rounded-[1.1rem] bg-terracotta px-5 py-3 text-sm font-semibold uppercase tracking-[0.16em] text-white transition hover:bg-[#9c402b] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "Confermo..." : canBook ? "Conferma il tavolo" : "Controlla prima la disponibilita'"}
              </button>
            </form>
          </div>

          {error ? (
            <p className="mt-4 rounded-[1.2rem] border border-terracotta/20 bg-terracotta/10 px-4 py-3 text-sm text-terracotta">
              {error}
            </p>
          ) : null}

          {confirmation ? (
            <div className="mt-5 rounded-[1.6rem] border border-gold/30 bg-[#faf4e8] p-5">
              <p className="ui-kicker text-[11px] font-semibold uppercase text-terracotta/76">Prenotazione confermata</p>
              <p className="mt-2 font-display text-3xl text-ink">{confirmation.booking.confirmation_code}</p>
              <p className="mt-2 text-sm leading-7 text-ink/66">
                Ti aspettiamo {formatLongDate(confirmation.booking.date)} alle {confirmation.booking.time.slice(0, 5)} per{" "}
                {confirmation.booking.party_size} {confirmation.booking.party_size === 1 ? "persona" : "persone"}.
              </p>
              <p className="mt-2 text-sm leading-7 text-ink/58">
                Apri subito il link privato qui sotto: e' il modo piu' rapido per spostare o cancellare la prenotazione.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  href={confirmation.manage_url}
                  className="rounded-full bg-ink px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-ivory"
                >
                  Gestisci prenotazione
                </Link>
                <span className="rounded-full border border-stone bg-white/75 px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink/58">
                  {notificationStatusLabel(confirmation.notification_status)}
                </span>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
