"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { PublicManagedBookingResponse } from "@/lib/types";

export default function ManageReservationPage() {
  const params = useParams<{ token: string }>();
  const token = Array.isArray(params?.token) ? params.token[0] : params?.token;
  const [payload, setPayload] = useState<PublicManagedBookingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    date: "",
    time: "",
    party_size: 2,
    special_requests: "",
  });

  useEffect(() => {
    if (!token) {
      return;
    }
    let ignore = false;
    setLoading(true);
    void apiFetch<PublicManagedBookingResponse>(`/api/public/bookings/${token}`)
      .then((response) => {
        if (ignore) {
          return;
        }
        setPayload(response);
        setForm({
          date: response.booking.date,
          time: response.booking.time.slice(0, 5),
          party_size: response.booking.party_size,
          special_requests: response.booking.special_requests ?? "",
        });
        setError(null);
      })
      .catch((caught) => {
        if (ignore) {
          return;
        }
        setPayload(null);
        setError(caught instanceof ApiError ? caught.message : "Link non valido o scaduto.");
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [token]);

  async function handleModify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const response = await apiFetch<PublicManagedBookingResponse>(`/api/public/bookings/${token}/modify`, {
        method: "POST",
        body: JSON.stringify({
          date: form.date,
          time: `${form.time}:00`,
          party_size: form.party_size,
          special_requests: form.special_requests,
        }),
      });
      setPayload(response);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Aggiornamento non riuscito.");
    } finally {
      setSaving(false);
    }
  }

  async function handleCancel() {
    if (!token) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const response = await apiFetch<PublicManagedBookingResponse>(`/api/public/bookings/${token}/cancel`, {
        method: "POST",
      });
      setPayload(response);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Cancellazione non riuscita.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto grid w-full max-w-5xl gap-5 lg:grid-cols-[0.92fr_1.08fr]">
        <section className="ui-night-surface rounded-[2rem] px-6 py-7 text-ivory sm:px-8">
          <p className="ui-kicker text-xs font-semibold uppercase text-gold/74">Gestione prenotazione</p>
          <h1 className="ui-display-title mt-4 font-display text-[3rem] leading-[0.94] sm:text-[4rem]">
            Cambia tavolo,
            <br />
            non i piani.
          </h1>
          <p className="mt-4 text-sm leading-7 text-ivory/68">
            Da qui puoi rivedere il tavolo confermato, cambiare l'orario se la sala lo consente oppure annullare.
          </p>
          {payload ? (
            <div className="mt-8 rounded-[1.6rem] border border-white/10 bg-white/6 p-5">
              <p className="ui-kicker text-[11px] font-semibold uppercase text-gold/74">Codice</p>
              <p className="mt-2 font-display text-3xl text-white">{payload.booking.confirmation_code}</p>
              <div className="mt-4 grid gap-2 text-sm text-ivory/68">
                <p>{payload.booking.date}</p>
                <p>{payload.booking.time.slice(0, 5)}</p>
                <p>{payload.booking.party_size} persone</p>
                <p className="capitalize">{payload.booking.status.replace("_", " ")}</p>
              </div>
            </div>
          ) : null}
        </section>

        <section className="ui-shell-surface rounded-[2rem] p-5 sm:p-7">
          {loading ? (
            <div className="space-y-3">
              <div className="h-20 animate-pulse rounded-[1.4rem] bg-white/75" />
              <div className="h-20 animate-pulse rounded-[1.4rem] bg-white/75" />
            </div>
          ) : payload ? (
            <>
              <p className="ui-kicker text-xs font-semibold uppercase text-terracotta/70">Dettagli ospite</p>
              <h2 className="mt-3 font-display text-4xl text-ink">{payload.booking.customer_name}</h2>
              <p className="mt-2 text-sm leading-7 text-ink/62">
                {payload.booking.customer_email ?? payload.booking.customer_phone}
              </p>

              <form onSubmit={handleModify} className="mt-6 grid gap-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-2 text-sm text-ink/66">
                    Data
                    <input
                      type="date"
                      className="rounded-[1.1rem] border border-stone/80 bg-white/92 px-4 py-3 outline-none transition focus:border-gold"
                      value={form.date}
                      onChange={(event) => setForm((current) => ({ ...current, date: event.target.value }))}
                    />
                  </label>
                  <label className="grid gap-2 text-sm text-ink/66">
                    Ora
                    <input
                      type="time"
                      className="rounded-[1.1rem] border border-stone/80 bg-white/92 px-4 py-3 outline-none transition focus:border-gold"
                      value={form.time}
                      onChange={(event) => setForm((current) => ({ ...current, time: event.target.value }))}
                    />
                  </label>
                </div>

                <label className="grid gap-2 text-sm text-ink/66">
                  Persone
                  <input
                    type="number"
                    min={1}
                    max={20}
                    className="rounded-[1.1rem] border border-stone/80 bg-white/92 px-4 py-3 outline-none transition focus:border-gold"
                    value={form.party_size}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, party_size: Number(event.target.value) }))
                    }
                  />
                </label>

                <label className="grid gap-2 text-sm text-ink/66">
                  Note
                  <textarea
                    rows={3}
                    className="rounded-[1.1rem] border border-stone/80 bg-white/92 px-4 py-3 outline-none transition focus:border-gold"
                    value={form.special_requests}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, special_requests: event.target.value }))
                    }
                  />
                </label>

                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    type="submit"
                    disabled={!payload.can_modify || saving}
                    className="rounded-full bg-ink px-5 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-ivory transition hover:bg-night disabled:opacity-50"
                  >
                    {saving ? "Salvo..." : "Aggiorna prenotazione"}
                  </button>
                  <button
                    type="button"
                    disabled={!payload.can_cancel || saving}
                    onClick={handleCancel}
                    className="rounded-full border border-terracotta/35 bg-terracotta/10 px-5 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-terracotta transition hover:bg-terracotta/15 disabled:opacity-50"
                  >
                    Cancella prenotazione
                  </button>
                </div>
              </form>
            </>
          ) : (
            <p className="text-sm text-ink/60">Non trovo una prenotazione valida per questo link.</p>
          )}

          {error ? (
            <p className="mt-4 rounded-[1.2rem] border border-terracotta/20 bg-terracotta/10 px-4 py-3 text-sm text-terracotta">
              {error}
            </p>
          ) : null}

          <div className="mt-6 pt-2">
            <Link
              href="/"
              className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/46 underline decoration-stone underline-offset-4"
            >
              Torna a Ristorante AI
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
