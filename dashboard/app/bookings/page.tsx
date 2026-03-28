"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiDownload, apiFetch, queryString } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { Booking, BookingEvent, BookingStatus } from "@/lib/types";

const emptyForm = {
  date: "",
  time: "20:00:00",
  party_size: 1,
  customer_name: "",
  customer_phone: "",
  special_requests: ""
};

export default function BookingsPage() {
  const { activeRestaurantId } = useWorkspace();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBooking, setSelectedBooking] = useState<Booking | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [events, setEvents] = useState<BookingEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const deferredSearch = useDeferredValue(search);

  async function loadBookings() {
    if (!activeRestaurantId) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await apiFetch<Booking[]>(
        `/api/bookings${queryString({
          restaurant_id: activeRestaurantId,
          date_from: new Date().toISOString().slice(0, 10)
        })}`
      );
      setBookings(payload);
    } catch (caught) {
      setBookings([]);
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Non sono riuscito a caricare le prenotazioni.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let ignore = false;
    void (async () => {
      await loadBookings();
      if (ignore) {
        return;
      }
    })();
    return () => {
      ignore = true;
    };
  }, [activeRestaurantId]);

  useEffect(() => {
    if (!selectedBooking) {
      setEvents([]);
      return;
    }
    let ignore = false;
    setLoadingEvents(true);
    setError(null);
    void apiFetch<BookingEvent[]>(
      `/api/bookings/${selectedBooking.id}/events${queryString({
        restaurant_id: activeRestaurantId,
      })}`
    )
      .then((payload) => {
        if (!ignore) {
          setEvents(payload);
        }
      })
      .catch((caught) => {
        if (!ignore) {
          setEvents([]);
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Non sono riuscito a caricare lo storico prenotazione.",
          );
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoadingEvents(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [activeRestaurantId, selectedBooking]);

  const filtered = useMemo(() => {
    if (!deferredSearch.trim()) {
      return bookings;
    }
    const query = deferredSearch.toLowerCase();
    return bookings.filter((booking) =>
      [booking.customer_name, booking.confirmation_code, booking.special_requests ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(query)
    );
  }, [bookings, deferredSearch]);

  function hydrateForm(booking: Booking | null) {
    setFormError(null);
    if (!booking) {
      setForm(emptyForm);
      return;
    }
    setForm({
      date: booking.date,
      time: booking.time,
      party_size: booking.party_size,
      customer_name: booking.customer_name,
      customer_phone: booking.customer_phone,
      special_requests: booking.special_requests ?? ""
    });
  }

  async function saveBooking() {
    if (!activeRestaurantId) return;
    setSaving(true);
    setFormError(null);

    const partySize = Number(form.party_size);
    if (!partySize || partySize < 1 || partySize > 30) {
      setFormError("Coperti deve essere tra 1 e 30.");
      setSaving(false);
      return;
    }
    if (form.customer_phone.length < 6) {
      setFormError("Numero di telefono troppo corto (minimo 6 cifre).");
      setSaving(false);
      return;
    }

    const payload = {
      restaurant_id: activeRestaurantId,
      date: form.date,
      time: form.time,
      party_size: partySize,
      customer_name: form.customer_name,
      customer_phone: form.customer_phone,
      special_requests: form.special_requests || null,
      source: selectedBooking?.source ?? "dashboard",
      status: selectedBooking?.status ?? "confirmed"
    };

    try {
      if (selectedBooking) {
        await apiFetch(`/api/bookings/${selectedBooking.id}${queryString({ restaurant_id: activeRestaurantId })}`, {
          method: "PATCH",
          body: JSON.stringify(payload)
        });
      } else {
        await apiFetch("/api/bookings", {
          method: "POST",
          body: JSON.stringify(payload)
        });
      }
      setSelectedBooking(null);
      hydrateForm(null);
      await loadBookings();
    } catch (caught) {
      setFormError(
        caught instanceof ApiError
          ? caught.message
          : "Non sono riuscito a salvare la prenotazione.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function updateStatus(booking: Booking, newStatus: BookingStatus) {
    const labels: Record<string, string> = {
      cancelled: "Cancellare",
      no_show: "Segnare come no-show",
      completed: "Completare",
    };
    const label = labels[newStatus] ?? newStatus;
    if (!window.confirm(`${label} la prenotazione di ${booking.customer_name}?`)) {
      return;
    }
    setError(null);
    try {
      if (newStatus === "cancelled") {
        await apiFetch(`/api/bookings/${booking.id}/cancel${queryString({ restaurant_id: activeRestaurantId })}`, {
          method: "POST",
        });
      } else {
        await apiFetch(`/api/bookings/${booking.id}${queryString({ restaurant_id: activeRestaurantId })}`, {
          method: "PATCH",
          body: JSON.stringify({ status: newStatus })
        });
      }
      await loadBookings();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Aggiornamento stato non riuscito.",
      );
    }
  }

  async function exportBookings() {
    if (!activeRestaurantId) {
      return;
    }
    setError(null);
    try {
      await apiDownload(
        `/api/bookings/export${queryString({
          restaurant_id: activeRestaurantId,
          date_from: new Date().toISOString().slice(0, 10),
        })}`,
        "bookings.csv",
      );
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Export prenotazioni non riuscito.",
      );
    }
  }

  return (
    <DashboardShell
      title="Prenotazioni"
      subtitle="Gestisci le tavolate confermate, modifica i dettagli dal banco e registra walk-in senza uscire dalla dashboard."
    >
      <div className="grid gap-6 xl:grid-cols-[0.62fr_0.38fr]">
        <SectionCard
          title="Lista prenotazioni"
          kicker="Agenda"
          action={
            <input
              aria-label="Cerca prenotazioni"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Cerca per nome o codice"
              className="w-full rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-sm text-ink outline-none sm:max-w-xs"
            />
          }
        >
          <div className="space-y-3">
            {error ? (
              <div className="rounded-[1.4rem] border border-terracotta/20 bg-terracotta/8 p-4 text-sm text-terracotta">
                {error}
              </div>
            ) : null}
            {loading ? (
              <div className="h-72 animate-pulse rounded-[1.6rem] bg-ivory/70" />
            ) : filtered.length === 0 ? (
              <div className="rounded-[1.4rem] border border-dashed border-stone/80 bg-white/60 p-8 text-sm text-ink/60">
                Nessuna prenotazione trovata per i filtri attuali.
              </div>
            ) : (
              filtered.map((booking) => (
                <article
                  key={booking.id}
                  className="rounded-[1.4rem] border border-stone/80 bg-white/75 p-4"
                >
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <p className="font-display text-2xl text-ink">{booking.customer_name}</p>
                        <span className="rounded-full bg-ivory px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-terracotta/75">
                          {booking.confirmation_code}
                        </span>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] ${
                          booking.status === "confirmed" ? "bg-olive/15 text-olive" :
                          booking.status === "modified" ? "bg-gold/15 text-gold" :
                          booking.status === "cancelled" ? "bg-terracotta/15 text-terracotta" :
                          booking.status === "no_show" ? "bg-ink/10 text-ink/60" :
                          "bg-stone/40 text-ink/50"
                        }`}>
                          {booking.status === "confirmed" ? "confermata" :
                           booking.status === "modified" ? "modificata" :
                           booking.status === "cancelled" ? "cancellata" :
                           booking.status === "no_show" ? "no-show" :
                           "completata"}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-ink/65">
                        {formatDate(booking.date)} · {booking.time.slice(0, 5)} · {booking.party_size} persone ·{" "}
                        {booking.turno}
                      </p>
                      <p className="mt-2 text-sm text-ink/55">
                        {booking.special_requests || "Nessuna nota speciale"}
                      </p>
                    </div>
                    {["confirmed", "modified"].includes(booking.status) ? (
                      <div className="grid grid-cols-2 gap-2 md:flex md:flex-wrap">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedBooking(booking);
                            hydrateForm(booking);
                          }}
                          className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-ink/70 transition hover:border-gold"
                        >
                          Modifica
                        </button>
                        <button
                          type="button"
                          onClick={() => updateStatus(booking, "no_show")}
                          className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-ink/70 transition hover:border-gold"
                        >
                          No-show
                        </button>
                        <button
                          type="button"
                          onClick={() => updateStatus(booking, "cancelled")}
                          className="col-span-2 rounded-full bg-terracotta px-3 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-white transition hover:bg-terracotta/85 md:col-span-1"
                        >
                          Cancella
                        </button>
                      </div>
                    ) : null}
                  </div>
                </article>
              ))
            )}
          </div>
        </SectionCard>

        <SectionCard
          title={selectedBooking ? "Modifica prenotazione" : "Nuova prenotazione"}
          kicker="Back office"
          action={
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void exportBookings()}
                className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-ink/70"
              >
                Export CSV
              </button>
              {selectedBooking ? (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedBooking(null);
                    hydrateForm(null);
                  }}
                  className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-ink/70"
                >
                  Nuova
                </button>
              ) : null}
            </div>
          }
        >
          <div className="grid gap-4">
            <label className="grid gap-2 text-sm text-ink/65">
              Data
              <input
                type="date"
                min={new Date().toISOString().slice(0, 10)}
                required
                className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                value={form.date}
                onChange={(event) => setForm((current) => ({ ...current, date: event.target.value }))}
              />
            </label>
            <label className="grid gap-2 text-sm text-ink/65">
              Orario
              <input
                type="time"
                className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                value={form.time.slice(0, 5)}
                onChange={(event) =>
                  setForm((current) => ({ ...current, time: `${event.target.value}:00` }))
                }
              />
            </label>
            <label className="grid gap-2 text-sm text-ink/65">
              Coperti
              <input
                type="number"
                min={1}
                max={30}
                required
                className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                value={form.party_size}
                onChange={(event) =>
                  setForm((current) => ({ ...current, party_size: Number(event.target.value) }))
                }
              />
            </label>
            <label className="grid gap-2 text-sm text-ink/65">
              Nome cliente
              <input
                required
                className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                value={form.customer_name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, customer_name: event.target.value }))
                }
              />
            </label>
            <label className="grid gap-2 text-sm text-ink/65">
              Telefono
              <input
                type="tel"
                required
                minLength={6}
                maxLength={30}
                placeholder="+39 333 1234567"
                className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                value={form.customer_phone}
                onChange={(event) =>
                  setForm((current) => ({ ...current, customer_phone: event.target.value }))
                }
              />
            </label>
            <label className="grid gap-2 text-sm text-ink/65">
              Richieste speciali
              <textarea
                rows={4}
                className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                value={form.special_requests}
                onChange={(event) =>
                  setForm((current) => ({ ...current, special_requests: event.target.value }))
                }
              />
            </label>
            {formError ? (
              <p className="text-sm font-medium text-terracotta">{formError}</p>
            ) : null}
            <button
              type="button"
              disabled={saving || !form.date || !form.customer_name || !form.customer_phone}
              onClick={() => void saveBooking()}
              className="rounded-2xl bg-ink px-5 py-3 text-sm font-semibold uppercase tracking-[0.26em] text-ivory transition hover:bg-night disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Salvo..." : selectedBooking ? "Aggiorna prenotazione" : "Crea prenotazione"}
            </button>
            {selectedBooking ? (
              <div className="space-y-3 rounded-[1.4rem] border border-stone/80 bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-ink/45">Storico prenotazione</p>
                {loadingEvents ? (
                  <div className="h-28 animate-pulse rounded-[1.2rem] bg-ivory/70" />
                ) : events.length ? (
                  events.map((event) => (
                    <article key={event.id} className="rounded-[1.2rem] border border-stone/70 bg-ivory/70 p-3">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="text-sm font-semibold capitalize text-ink">
                            {event.event_type.replaceAll("_", " ")}
                          </p>
                          <p className="mt-1 text-xs text-ink/55">{event.changed_by ?? "system"}</p>
                        </div>
                        <p className="text-xs uppercase tracking-[0.18em] text-ink/40 sm:text-right">
                          {formatDate(event.created_at.slice(0, 10))}
                        </p>
                      </div>
                      <pre className="mt-3 whitespace-pre-wrap text-xs leading-6 text-ink/65">
                        {JSON.stringify(event.changes, null, 2)}
                      </pre>
                    </article>
                  ))
                ) : (
                  <p className="text-sm text-ink/55">Nessun evento disponibile per questa prenotazione.</p>
                )}
              </div>
            ) : null}
          </div>
        </SectionCard>
      </div>
    </DashboardShell>
  );
}
