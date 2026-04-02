"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";

import { ConfirmSheet } from "@/components/confirm-sheet";
import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiDownload, apiFetch, queryString } from "@/lib/api";
import { shiftLocalDateInputValue, toLocalDateInputValue } from "@/lib/format";
import { Booking, BookingEvent, BookingStatus, CapacitySnapshot } from "@/lib/types";

const activeStatuses = new Set(["confirmed", "modified"]);

const emptyForm = {
  date: "",
  time: "20:00:00",
  party_size: 1,
  customer_name: "",
  customer_phone: "",
  special_requests: "",
};

export default function BookingsPage() {
  const { activeRestaurantId, restaurant } = useWorkspace();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [snapshot, setSnapshot] = useState<CapacitySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedBooking, setSelectedBooking] = useState<Booking | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [search, setSearch] = useState("");
  const [showArchive, setShowArchive] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [events, setEvents] = useState<BookingEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [pendingStatusChange, setPendingStatusChange] = useState<{
    booking: Booking;
    nextStatus: BookingStatus;
  } | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [upcomingBookings, setUpcomingBookings] = useState<Booking[]>([]);
  const [selectedDate, setSelectedDate] = useState(toLocalDateInputValue());
  const [selectedTurno, setSelectedTurno] = useState("all");
  const [paramsReady, setParamsReady] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const nextDate = params.get("date");
    const nextTurno = params.get("turno");
    if (nextDate) {
      setSelectedDate(nextDate);
    }
    if (nextTurno) {
      setSelectedTurno(nextTurno);
    }
    setParamsReady(true);
  }, []);

  const turnOptions = useMemo(
    () =>
      (restaurant?.turni ?? []).map((turno) => ({
        name: turno.name,
        start: withSeconds(turno.start),
        end: withSeconds(turno.end),
        max_covers: turno.max_covers,
      })),
    [restaurant?.turni],
  );

  useEffect(() => {
    if (selectedTurno === "all") {
      return;
    }
    if (!turnOptions.some((turno) => turno.name === selectedTurno)) {
      setSelectedTurno("all");
    }
  }, [selectedTurno, turnOptions]);

  useEffect(() => {
    if (!paramsReady) {
      return;
    }
    const params = new URLSearchParams();
    params.set("date", selectedDate);
    if (selectedTurno !== "all") {
      params.set("turno", selectedTurno);
    }
    window.history.replaceState(null, "", `/bookings?${params.toString()}`);
  }, [paramsReady, selectedDate, selectedTurno]);

  async function loadBookings() {
    if (!activeRestaurantId) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const upcomingDateTo = shiftLocalDateInputValue(toLocalDateInputValue(), 4);
      const [bookingsPayload, upcomingBookingsPayload, capacityPayload] = await Promise.all([
        apiFetch<Booking[]>(
          `/api/bookings${queryString({
            restaurant_id: activeRestaurantId,
            date_from: selectedDate,
            date_to: selectedDate,
          })}`,
        ),
        apiFetch<Booking[]>(
          `/api/bookings${queryString({
            restaurant_id: activeRestaurantId,
            date_from: toLocalDateInputValue(),
            date_to: upcomingDateTo,
          })}`,
        ),
        apiFetch<CapacitySnapshot>(
          `/api/analytics/capacity${queryString({
            restaurant_id: activeRestaurantId,
            date: selectedDate,
          })}`,
        ),
      ]);
      setBookings(bookingsPayload);
      setUpcomingBookings(upcomingBookingsPayload);
      setSnapshot(capacityPayload);
    } catch (caught) {
      setBookings([]);
      setUpcomingBookings([]);
      setSnapshot(null);
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Non sono riuscito a caricare il servizio selezionato.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadBookings();
  }, [activeRestaurantId, selectedDate]);

  useEffect(() => {
    if (selectedBooking || !restaurant) {
      return;
    }
    const matchedTurno = restaurant.turni.find((turno) => turno.name === selectedTurno);
    setForm((current) => ({
      ...current,
      date: selectedDate,
      time: matchedTurno ? withSeconds(matchedTurno.start) : current.time,
    }));
  }, [restaurant, selectedBooking, selectedDate, selectedTurno]);

  useEffect(() => {
    if (!selectedBooking || !activeRestaurantId) {
      setEvents([]);
      return;
    }

    let ignore = false;
    setLoadingEvents(true);
    setError(null);

    void apiFetch<BookingEvent[]>(
      `/api/bookings/${selectedBooking.id}/events${queryString({
        restaurant_id: activeRestaurantId,
      })}`,
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

  const filteredBookings = useMemo(() => {
    const query = search.trim().toLowerCase();
    return bookings.filter((booking) => {
      const matchesTurno = selectedTurno === "all" ? true : booking.turno === selectedTurno;
      const matchesQuery = !query
        ? true
        : [booking.customer_name, booking.confirmation_code, booking.special_requests ?? ""]
            .join(" ")
            .toLowerCase()
            .includes(query);
      return matchesTurno && matchesQuery;
    });
  }, [bookings, search, selectedTurno]);

  const serviceBookings = useMemo(
    () =>
      bookings
        .filter((booking) => activeStatuses.has(booking.status))
        .filter((booking) => (selectedTurno === "all" ? true : booking.turno === selectedTurno))
        .sort((left, right) => left.time.localeCompare(right.time)),
    [bookings, selectedTurno],
  );

  const visibleBookings = useMemo(
    () => filteredBookings.filter((booking) => activeStatuses.has(booking.status)).sort((left, right) => left.time.localeCompare(right.time)),
    [filteredBookings],
  );

  const archivedBookings = useMemo(
    () =>
      filteredBookings
        .filter((booking) => !activeStatuses.has(booking.status))
        .sort((left, right) => left.time.localeCompare(right.time)),
    [filteredBookings],
  );

  const selectedSlots = useMemo(() => {
    const slots = snapshot?.slots ?? [];
    return selectedTurno === "all" ? slots : slots.filter((slot) => slot.turno === selectedTurno);
  }, [selectedTurno, snapshot?.slots]);

  const reservedCovers = selectedTurno === "all"
    ? selectedSlots.reduce((sum, slot) => sum + slot.booked_covers, 0)
    : serviceBookings.reduce((sum, booking) => sum + booking.party_size, 0);
  const remainingCovers = selectedSlots.reduce((sum, slot) => sum + slot.remaining_covers, 0);
  const maxCovers = selectedSlots.reduce((sum, slot) => sum + slot.max_covers, 0);
  const serviceSummary = getServiceSummary(selectedDate, selectedTurno, turnOptions, selectedSlots);
  const upcomingDays = useMemo(() => {
    const today = toLocalDateInputValue();

    return Array.from({ length: 5 }).map((_, index) => {
      const date = shiftLocalDateInputValue(today, index);
      const confirmedForDate = upcomingBookings
        .filter((booking) => booking.date === date)
        .filter((booking) => activeStatuses.has(booking.status))
        .sort((left, right) => left.time.localeCompare(right.time));

      return {
        date,
        label: new Intl.DateTimeFormat("it-IT", {
          weekday: "short",
          day: "2-digit",
          month: "short",
        }).format(new Date(`${date}T12:00:00`)),
        bookings: confirmedForDate.length,
        covers: confirmedForDate.reduce((sum, booking) => sum + booking.party_size, 0),
        previewBookings: confirmedForDate.slice(0, 3),
        selected: date === selectedDate,
      };
    });
  }, [selectedDate, upcomingBookings]);

  const bookingGroups = useMemo(() => {
    if (selectedTurno !== "all") {
      return [{ key: selectedTurno, label: serviceSummary.turnoLabel, bookings: visibleBookings }];
    }

    const turnoNames = turnOptions.map((turno) => turno.name);
    const names = turnoNames.length
      ? turnoNames
      : Array.from(new Set(visibleBookings.map((booking) => booking.turno)));

    return names.map((turnoName) => ({
      key: turnoName,
      label: formatTurnoName(turnoName),
      bookings: visibleBookings.filter((booking) => booking.turno === turnoName),
    }));
  }, [selectedTurno, serviceSummary.turnoLabel, turnOptions, visibleBookings]);

  function hydrateForm(booking: Booking | null) {
    setFormError(null);
    if (!booking) {
      const matchedTurno = restaurant?.turni.find((turno) => turno.name === selectedTurno);
      setForm({
        ...emptyForm,
        date: selectedDate,
        time: matchedTurno ? withSeconds(matchedTurno.start) : emptyForm.time,
      });
      return;
    }
    setForm({
      date: booking.date,
      time: booking.time,
      party_size: booking.party_size,
      customer_name: booking.customer_name,
      customer_phone: booking.customer_phone,
      special_requests: booking.special_requests ?? "",
    });
  }

  async function saveBooking() {
    if (!activeRestaurantId) {
      return;
    }

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
      status: selectedBooking?.status ?? "confirmed",
    };

    try {
      if (selectedBooking) {
        await apiFetch(
          `/api/bookings/${selectedBooking.id}${queryString({ restaurant_id: activeRestaurantId })}`,
          {
            method: "PATCH",
            body: JSON.stringify(payload),
          },
        );
      } else {
        await apiFetch("/api/bookings", {
          method: "POST",
          body: JSON.stringify(payload),
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

  async function confirmStatusChange() {
    if (!pendingStatusChange || !activeRestaurantId) {
      return;
    }

    const { booking, nextStatus } = pendingStatusChange;
    setUpdatingStatus(true);
    setError(null);
    try {
      if (nextStatus === "cancelled") {
        await apiFetch(`/api/bookings/${booking.id}/cancel${queryString({ restaurant_id: activeRestaurantId })}`, {
          method: "POST",
        });
      } else {
        await apiFetch(`/api/bookings/${booking.id}${queryString({ restaurant_id: activeRestaurantId })}`, {
          method: "PATCH",
          body: JSON.stringify({ status: nextStatus }),
        });
      }
      setPendingStatusChange(null);
      await loadBookings();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Aggiornamento stato non riuscito.",
      );
    } finally {
      setUpdatingStatus(false);
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
          date_from: selectedDate,
          date_to: selectedDate,
        })}`,
        `prenotazioni-${selectedDate}.csv`,
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
      subtitle="Apri un giorno, controlla i coperti prenotati e scorri subito la lista ospiti."
    >
      <div className="space-y-6">
        <SectionCard title="Giorni in arrivo" kicker="Chi hai in sala">
          <div className="grid gap-3 lg:grid-cols-5">
            {upcomingDays.map((day) => (
              <button
                key={day.date}
                type="button"
                onClick={() => {
                  setSelectedDate(day.date);
                  setSelectedTurno("all");
                }}
                className={`rounded-[1.45rem] border p-4 text-left transition ${
                  day.selected
                    ? "border-gold bg-ivory/92 shadow-card"
                    : "border-stone/80 bg-white/70 hover:border-gold hover:bg-ivory/80"
                }`}
              >
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-terracotta/70">
                  {day.label}
                </p>
                <p className="mt-3 font-display text-3xl text-ink">{day.covers}</p>
                <p className="mt-1 text-sm text-ink/60">
                  {day.bookings} {day.bookings === 1 ? "prenotazione" : "prenotazioni"}
                </p>
                <div className="mt-4 space-y-2">
                  {day.previewBookings.length ? (
                    day.previewBookings.map((booking) => (
                      <div key={booking.id} className="rounded-2xl bg-ivory/70 px-3 py-2">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/44">
                          {booking.time.slice(0, 5)} · {booking.party_size}{" "}
                          {booking.party_size === 1 ? "coperto" : "coperti"}
                        </p>
                        <p className="mt-1 text-sm font-medium text-ink">{booking.customer_name}</p>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs leading-6 text-ink/52">Nessun ospite confermato</p>
                  )}
                </div>
              </button>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Dettaglio del giorno" kicker="Vista selezionata">
          <div className="space-y-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedDate(shiftLocalDateInputValue(selectedDate, -1))}
                  className="rounded-full border border-stone px-3 py-2 text-sm text-ink/60 transition hover:border-gold hover:text-ink"
                >
                  ←
                </button>
                <input
                  type="date"
                  value={selectedDate}
                  min={toLocalDateInputValue()}
                  onChange={(event) => setSelectedDate(event.target.value)}
                  className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-sm text-ink outline-none transition focus:border-gold"
                />
                <button
                  type="button"
                  onClick={() => setSelectedDate(shiftLocalDateInputValue(selectedDate, 1))}
                  className="rounded-full border border-stone px-3 py-2 text-sm text-ink/60 transition hover:border-gold hover:text-ink"
                >
                  →
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedDate(toLocalDateInputValue())}
                  className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
                >
                  Oggi
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedDate(shiftLocalDateInputValue(toLocalDateInputValue(), 1))}
                  className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
                >
                  Domani
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedTurno("all")}
                  className={serviceChipClass(selectedTurno === "all")}
                >
                  Tutto il giorno
                </button>
                {turnOptions.map((turno) => (
                  <button
                    key={turno.name}
                    type="button"
                    onClick={() => setSelectedTurno(turno.name)}
                    className={serviceChipClass(selectedTurno === turno.name)}
                  >
                    {formatTurnoName(turno.name)}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-[1.6rem] border border-stone/80 bg-ivory/55 p-5">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                    {serviceSummary.dateLabel}
                  </p>
                  <h3 className="mt-3 font-display text-4xl text-ink">{serviceSummary.turnoLabel}</h3>
                  <p className="mt-2 text-sm leading-7 text-ink/62">
                    Hai {serviceBookings.length} {serviceBookings.length === 1 ? "prenotazione attiva" : "prenotazioni attive"} per {reservedCovers}{" "}
                    {reservedCovers === 1 ? "coperto" : "coperti"}. Restano {remainingCovers} posti liberi
                    {maxCovers ? ` su ${maxCovers}` : ""}.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge tone="good">
                    {serviceBookings.length} {serviceBookings.length === 1 ? "prenotazione" : "prenotazioni"}
                  </StatusBadge>
                  <StatusBadge tone="neutral">{reservedCovers} coperti</StatusBadge>
                  <StatusBadge tone={remainingCovers <= 5 ? "warn" : "good"}>
                    {remainingCovers} posti liberi
                  </StatusBadge>
                </div>
              </div>
            </div>
          </div>
        </SectionCard>

        <div className="grid gap-6 2xl:grid-cols-[0.64fr_0.36fr]">
          <SectionCard
            title="Lista ospiti"
            kicker="Chi arriva"
            action={
              <div className="flex w-full flex-col gap-3 sm:min-w-[320px]">
                <div className="relative">
                  <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink/38" />
                  <input
                    aria-label="Cerca prenotazioni"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Cerca per nome, codice o nota"
                    className="w-full rounded-2xl border border-stone bg-ivory/80 px-11 py-3 text-sm text-ink outline-none transition focus:border-gold"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setShowArchive((current) => !current)}
                    className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
                  >
                    {showArchive ? "Nascondi storico" : `Mostra storico (${archivedBookings.length})`}
                  </button>
                  <button
                    type="button"
                    onClick={() => void exportBookings()}
                    className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
                  >
                    Export CSV
                  </button>
                </div>
              </div>
            }
          >
            <div className="space-y-4">
              {error ? (
                <div className="rounded-[1.4rem] border border-terracotta/20 bg-terracotta/8 p-4 text-sm text-terracotta">
                  {error}
                </div>
              ) : null}

              {loading ? (
                <div className="h-72 animate-pulse rounded-[1.6rem] bg-ivory/70" />
              ) : visibleBookings.length === 0 ? (
                <div className="rounded-[1.4rem] border border-dashed border-stone/80 bg-white/60 p-8 text-sm text-ink/60">
                  Nessun ospite da mostrare per questo servizio.
                </div>
              ) : (
                <div className="space-y-5">
                  {bookingGroups.map((group) =>
                    group.bookings.length ? (
                      <div key={group.key} className="space-y-3">
                        {selectedTurno === "all" ? (
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                              {group.label}
                            </p>
                            <StatusBadge tone="neutral">
                              {group.bookings.reduce((sum, booking) => sum + booking.party_size, 0)} coperti
                            </StatusBadge>
                          </div>
                        ) : null}
                        {group.bookings.map((booking) => (
                          <GuestRow
                            key={booking.id}
                            booking={booking}
                            onEdit={() => {
                              setSelectedBooking(booking);
                              hydrateForm(booking);
                            }}
                            onStatusChange={(nextStatus) => setPendingStatusChange({ booking, nextStatus })}
                          />
                        ))}
                      </div>
                    ) : null,
                  )}
                </div>
              )}

              {showArchive && archivedBookings.length ? (
                <details open className="rounded-[1.35rem] border border-dashed border-stone bg-ivory/35 p-4">
                  <summary className="cursor-pointer text-sm font-semibold text-ink">
                    Storico del servizio ({archivedBookings.length})
                  </summary>
                  <div className="mt-4 space-y-3">
                    {archivedBookings.map((booking) => (
                      <GuestRow key={booking.id} booking={booking} compact />
                    ))}
                  </div>
                </details>
              ) : null}
            </div>
          </SectionCard>

          <SectionCard
            title={selectedBooking ? "Modifica prenotazione" : "Aggiungi prenotazione"}
            kicker="Inserimento manuale"
            action={
              selectedBooking ? (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedBooking(null);
                    hydrateForm(null);
                  }}
                  className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/65 transition hover:border-gold hover:text-ink"
                >
                  Chiudi modifica
                </button>
              ) : null
            }
          >
            <div className="grid gap-4">
              {selectedBooking ? (
                <div className="rounded-[1.4rem] border border-gold/20 bg-gold/8 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge tone="warn">{selectedBooking.confirmation_code}</StatusBadge>
                    <StatusBadge tone="neutral">{formatTurnoName(selectedBooking.turno)}</StatusBadge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-ink/68">
                    Stai aggiornando la prenotazione di <strong>{selectedBooking.customer_name}</strong>.
                  </p>
                </div>
              ) : (
                <div className="rounded-[1.4rem] border border-stone/80 bg-ivory/60 p-4 text-sm leading-7 text-ink/68">
                  {selectedTurno === "all"
                    ? `Nuova prenotazione per il giorno selezionato: ${serviceSummary.dateLabel.toLowerCase()}.`
                    : `Nuova prenotazione per ${serviceSummary.turnoLabel.toLowerCase()} del ${serviceSummary.dateLabel.toLowerCase()}.`}
                </div>
              )}

              <label className="grid gap-2 text-sm text-ink/65">
                Data
                <input
                  type="date"
                  min={toLocalDateInputValue()}
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
                Note per la sala
                <textarea
                  rows={4}
                  className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                  value={form.special_requests}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, special_requests: event.target.value }))
                  }
                />
              </label>

              {formError ? <p className="text-sm font-medium text-terracotta">{formError}</p> : null}

              <button
                type="button"
                disabled={saving || !form.date || !form.customer_name || !form.customer_phone}
                onClick={() => void saveBooking()}
                className="rounded-2xl bg-ink px-5 py-3 text-sm font-semibold uppercase tracking-[0.22em] text-ivory transition hover:bg-night disabled:cursor-not-allowed disabled:opacity-50"
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
                        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <p className="text-sm font-semibold text-ink">
                              {formatBookingEventLabel(event.event_type)}
                            </p>
                            <p className="mt-1 text-xs text-ink/55">{formatBookingActor(event.changed_by)}</p>
                          </div>
                          <p className="text-xs uppercase tracking-[0.18em] text-ink/40">
                            {event.created_at.slice(0, 10)}
                          </p>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-ink/62">
                          {summarizeBookingChanges(event.changes)}
                        </p>
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
      </div>

      <ConfirmSheet
        open={Boolean(pendingStatusChange)}
        title={
          pendingStatusChange?.nextStatus === "cancelled"
            ? "Confermare cancellazione"
            : "Confermare no-show"
        }
        description={
          pendingStatusChange
            ? pendingStatusChange.nextStatus === "cancelled"
              ? `Stai per cancellare la prenotazione di ${pendingStatusChange.booking.customer_name}.`
              : `Stai per segnare come no-show la prenotazione di ${pendingStatusChange.booking.customer_name}.`
            : ""
        }
        confirmLabel={
          pendingStatusChange?.nextStatus === "cancelled" ? "Sì, cancella" : "Sì, segna no-show"
        }
        busy={updatingStatus}
        onCancel={() => setPendingStatusChange(null)}
        onConfirm={() => {
          void confirmStatusChange();
        }}
      >
        {pendingStatusChange ? (
          <div className="rounded-[1.2rem] border border-stone/70 bg-ivory/60 px-4 py-3 text-sm text-ink/68">
            {pendingStatusChange.booking.time.slice(0, 5)} · {pendingStatusChange.booking.party_size}{" "}
            {pendingStatusChange.booking.party_size === 1 ? "persona" : "persone"}
          </div>
        ) : null}
      </ConfirmSheet>
    </DashboardShell>
  );
}

function GuestRow({
  booking,
  onEdit,
  onStatusChange,
  compact = false,
}: {
  booking: Booking;
  onEdit?: () => void;
  onStatusChange?: (nextStatus: BookingStatus) => void;
  compact?: boolean;
}) {
  const tone =
    booking.status === "confirmed"
      ? "good"
      : booking.status === "modified"
        ? "warn"
        : booking.status === "cancelled"
          ? "danger"
          : "neutral";

  return (
    <article className="rounded-[1.4rem] border border-stone/80 bg-white/78 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-display text-3xl text-ink">{booking.time.slice(0, 5)}</p>
            <StatusBadge tone="neutral">{booking.party_size} {booking.party_size === 1 ? "persona" : "persone"}</StatusBadge>
            <StatusBadge tone={tone}>{statusLabel(booking.status)}</StatusBadge>
          </div>
          <p className="mt-3 font-semibold text-ink">{booking.customer_name}</p>
          <p className="mt-2 text-sm text-ink/58">
            {booking.confirmation_code} · {formatTurnoName(booking.turno)}
          </p>
          <p className="mt-2 text-sm text-ink/58">{booking.customer_phone}</p>
          <p className="mt-2 text-sm leading-6 text-ink/55">
            {booking.special_requests || "Nessuna nota speciale"}
          </p>
        </div>

        {!compact && activeStatuses.has(booking.status) ? (
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <button
              type="button"
              onClick={onEdit}
              className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/70 transition hover:border-gold"
            >
              Modifica
            </button>
            <button
              type="button"
              onClick={() => onStatusChange?.("no_show")}
              className="rounded-full border border-stone px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-ink/70 transition hover:border-gold"
            >
              No-show
            </button>
            <button
              type="button"
              onClick={() => onStatusChange?.("cancelled")}
              className="col-span-2 rounded-full bg-terracotta px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-white transition hover:bg-terracotta/85 sm:col-span-1"
            >
              Cancella
            </button>
          </div>
        ) : null}
      </div>
    </article>
  );
}

function getServiceSummary(
  selectedDate: string,
  selectedTurno: string,
  turnOptions: Array<{ name: string; start: string; end: string }>,
  selectedSlots: Array<{ turno: string; start: string; end: string }>,
) {
  const turnOption = turnOptions.find((turno) => turno.name === selectedTurno);
  const slot = selectedSlots[0];
  const start = turnOption?.start ?? slot?.start;
  const end = turnOption?.end ?? slot?.end;

  return {
    dateLabel: new Intl.DateTimeFormat("it-IT", {
      weekday: "long",
      day: "2-digit",
      month: "long",
    }).format(new Date(`${selectedDate}T12:00:00`)),
    turnoLabel:
      selectedTurno === "all"
        ? "Tutto il giorno"
        : `${formatTurnoName(selectedTurno)}${start && end ? ` · ${start.slice(0, 5)} - ${end.slice(0, 5)}` : ""}`,
  };
}

function serviceChipClass(active: boolean) {
  return `rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition ${
    active
      ? "border-gold bg-ivory/90 text-ink"
      : "border-stone bg-white/70 text-ink/60 hover:border-gold hover:text-ink"
  }`;
}

function statusLabel(status: BookingStatus) {
  if (status === "confirmed") return "Confermata";
  if (status === "modified") return "Modificata";
  if (status === "cancelled") return "Cancellata";
  if (status === "no_show") return "No-show";
  return "Completata";
}

function formatTurnoName(value: string) {
  const normalized = value.trim();
  if (!normalized) {
    return "Servizio";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function withSeconds(value: string) {
  return value.length === 5 ? `${value}:00` : value;
}

function formatBookingEventLabel(eventType: string) {
  if (eventType === "created") return "Prenotazione creata";
  if (eventType === "updated") return "Prenotazione aggiornata";
  if (eventType === "cancelled") return "Prenotazione cancellata";
  if (eventType === "marked_no_show") return "Segnata come no-show";
  return eventType.replaceAll("_", " ");
}

function formatBookingActor(changedBy: string | null) {
  if (!changedBy) return "Sistema";
  if (changedBy === "ai_phone") return "Telefono AI";
  if (changedBy.startsWith("user:")) return changedBy.slice(5);
  return changedBy;
}

function summarizeBookingChanges(changes: Record<string, unknown>) {
  const entries = Object.entries(changes);
  if (!entries.length) {
    return "Nessun dettaglio aggiuntivo.";
  }

  return entries
    .slice(0, 4)
    .map(([key, value]) => `${fieldLabel(key)}: ${String(value)}`)
    .join(" · ");
}

function fieldLabel(key: string) {
  if (key === "party_size") return "Coperti";
  if (key === "date") return "Data";
  if (key === "time") return "Orario";
  if (key === "turno") return "Servizio";
  if (key === "confirmation_code") return "Codice";
  return key.replaceAll("_", " ");
}
