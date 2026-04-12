"use client";

import { useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch } from "@/lib/api";
import { RestaurantSummary } from "@/lib/types";

export default function AdminPage() {
  const { user, restaurants, refreshWorkspace } = useWorkspace();
  const [form, setForm] = useState({
    name: "",
    slug: "",
    address: "",
    timezone: "Europe/Rome",
    twilio_phone: "",
    escalation_phone: ""
  });
  const [saving, setSaving] = useState(false);
  const [updatingRestaurantId, setUpdatingRestaurantId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"success" | "error">("success");

  if (user?.role !== "operator") {
    return (
      <DashboardShell
        title="Admin"
        subtitle="Questa area è riservata all’operatore piattaforma."
      >
        <SectionCard title="Accesso limitato" kicker="Operator only">
          <p className="rounded-[1.5rem] border border-dashed border-stone px-4 py-10 text-sm text-ink/55">
            L’account owner non può creare o disattivare tenant. Accedi con il profilo operator per
            gestire il portafoglio ristoranti.
          </p>
        </SectionCard>
      </DashboardShell>
    );
  }

  async function createRestaurant() {
    setSaving(true);
    setMessage(null);
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(form.slug)) {
      setMessageTone("error");
      setMessage("Lo slug può contenere solo lettere minuscole, numeri e trattini.");
      setSaving(false);
      return;
    }
    try {
      await apiFetch("/api/restaurants", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          slug: form.slug,
          address: form.address,
          timezone: form.timezone,
          twilio_phone: form.twilio_phone || null,
          voice_provider: "openai_realtime",
          escalation_phone: form.escalation_phone || null,
          opening_hours: { lunch: "12:00-15:00", dinner: "19:00-23:00" },
          weekly_closures: [],
          closure_dates: [],
          turni: [
            { name: "primo", start: "19:00", end: "21:00", max_covers: 40 },
            { name: "secondo", start: "21:00", end: "23:30", max_covers: 35 }
          ],
          booking_rules: {
            min_party: 1,
            max_party: 20,
            large_group_threshold: 8,
            max_advance_days: 60,
            min_lead_hours: 2
          },
          is_active: true
        })
      });
      setMessageTone("success");
      setMessage("Nuovo tenant creato e disponibile nella workspace.");
      setForm({
        name: "",
        slug: "",
        address: "",
        timezone: "Europe/Rome",
        twilio_phone: "",
        escalation_phone: ""
      });
      await refreshWorkspace();
    } catch (error) {
      setMessageTone("error");
      setMessage(error instanceof ApiError ? error.message : "Creazione tenant non riuscita.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleRestaurant(restaurant: RestaurantSummary) {
    setUpdatingRestaurantId(restaurant.id);
    setMessage(null);
    try {
      await apiFetch(`/api/restaurants/${restaurant.id}?sync_agent=false`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !restaurant.is_active })
      });
      setMessageTone("success");
      setMessage(
        !restaurant.is_active
          ? `${restaurant.name} riattivato.`
          : `${restaurant.name} messo in pausa.`
      );
      await refreshWorkspace();
    } catch (error) {
      const detail =
        error instanceof ApiError ? error.message : "Aggiornamento tenant non riuscito.";
      setMessageTone("error");
      setMessage(detail);
    } finally {
      setUpdatingRestaurantId(null);
    }
  }

  return (
    <DashboardShell
      title="Admin tenant"
      subtitle="Vista piattaforma per monitorare i ristoranti attivi, il loro volume di chiamate e l’onboarding di nuovi locali."
    >
      <div className="grid gap-6 xl:grid-cols-[0.58fr_0.42fr]">
        <SectionCard title="Portafoglio ristoranti" kicker="Tenant list">
          {message ? (
            <p className={`mb-4 text-sm ${messageTone === "error" ? "text-terracotta" : "text-olive"}`}>
              {message}
            </p>
          ) : null}
          <div className="space-y-3">
            {restaurants.map((restaurant) => (
              <article
                key={restaurant.id}
                className="rounded-[1.45rem] border border-stone/80 bg-white/80 p-4"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-display text-2xl text-ink">{restaurant.name}</p>
                    <p className="mt-2 text-sm text-ink/60">{restaurant.twilio_phone ?? "Numero non assegnato"}</p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] ${
                      restaurant.is_active
                        ? "bg-olive/15 text-olive"
                        : "bg-terracotta/15 text-terracotta"
                    }`}
                  >
                    {restaurant.is_active ? "attivo" : "pausa"}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl bg-ivory/70 p-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-ink/45">Chiamate oggi</p>
                    <p className="mt-2 font-display text-3xl text-ink">{restaurant.calls_today}</p>
                  </div>
                  <div className="rounded-2xl bg-ivory/70 p-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-ink/45">Prenotazioni</p>
                    <p className="mt-2 font-display text-3xl text-ink">{restaurant.bookings_today}</p>
                  </div>
                  <div className="rounded-2xl bg-ivory/70 p-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-ink/45">Booking rate</p>
                    <p className="mt-2 font-display text-3xl text-ink">{restaurant.booking_rate.toFixed(1)}%</p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      void toggleRestaurant(restaurant);
                    }}
                    disabled={updatingRestaurantId === restaurant.id}
                    className="rounded-2xl border border-ink/15 bg-ink px-4 py-3 text-xs font-semibold uppercase tracking-[0.22em] text-ivory"
                  >
                    {updatingRestaurantId === restaurant.id
                      ? "Aggiorno..."
                      : restaurant.is_active
                        ? "Metti in pausa"
                        : "Riattiva"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="Nuovo ristorante" kicker="Onboarding rapido">
            <div className="grid gap-4">
              {[
                ["name", "Nome", ""],
                ["slug", "Slug (solo lettere minuscole, numeri e trattini)", "^[a-z0-9]+(?:-[a-z0-9]+)*$"],
                ["address", "Indirizzo", ""],
                ["timezone", "Timezone", ""],
                ["twilio_phone", "Numero Twilio", ""],
                ["escalation_phone", "Numero escalation", ""]
              ].map(([field, label, pattern]) => (
                <label key={field} className="grid gap-2 text-sm text-ink/65">
                  {label}
                  <input
                    className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                    value={(form as Record<string, string>)[field]}
                    pattern={pattern || undefined}
                    placeholder={field === "slug" ? "trattoria-da-mario" : undefined}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, [field]: event.target.value }))
                    }
                  />
                </label>
              ))}
              <button
                type="button"
                onClick={() => void createRestaurant()}
                disabled={saving || !form.name || !form.slug || !form.address}
                className="rounded-2xl bg-ink px-5 py-3 text-sm font-semibold uppercase tracking-[0.26em] text-ivory transition hover:bg-night disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? "Creo..." : "Crea tenant"}
              </button>
            </div>
          </SectionCard>

          <SectionCard title="Checklist onboarding" kicker="Setup guide">
            <ol className="list-inside list-decimal space-y-3 text-sm leading-6 text-ink/65">
              <li>
                <strong className="text-ink/80">Crea il tenant qui sopra</strong> &mdash; inserisci nome, slug e
                indirizzo. Twilio si può collegare subito dopo.
              </li>
              <li>
                <strong className="text-ink/80">Collega un numero Twilio</strong> &mdash; configura il numero
                inbound e punta il webhook voce al backend di Ristorante AI.
              </li>
              <li>
                <strong className="text-ink/80">Personalizza turni e orari</strong> &mdash; vai in Impostazioni per
                configurare turni, capienza, chiusure settimanali e regole prenotazione.
              </li>
              <li>
                <strong className="text-ink/80">Crea un account owner</strong> &mdash; assegna un utente owner al
                ristorante per permettere al gestore di accedere alla dashboard.
              </li>
              <li>
                <strong className="text-ink/80">Testa una chiamata</strong> &mdash; chiama il numero Twilio e verifica
                che l&apos;assistente OpenAI risponda con il greeting corretto e possa prenotare.
              </li>
            </ol>
          </SectionCard>
        </div>
      </div>
    </DashboardShell>
  );
}
