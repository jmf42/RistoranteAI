"use client";

import { useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch } from "@/lib/api";
import { Restaurant } from "@/lib/types";

const DAY_LABELS: Record<string, string> = {
  monday: "Lunedì",
  tuesday: "Martedì",
  wednesday: "Mercoledì",
  thursday: "Giovedì",
  friday: "Venerdì",
  saturday: "Sabato",
  sunday: "Domenica",
};

export default function SettingsPage() {
  const { restaurant, refreshWorkspace } = useWorkspace();
  const [form, setForm] = useState<Restaurant | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"success" | "error">("success");

  useEffect(() => {
    if (restaurant) {
      setForm(JSON.parse(JSON.stringify(restaurant)) as Restaurant);
    }
  }, [restaurant]);

  const isDirty = useMemo(() => {
    if (!restaurant || !form) return false;
    return JSON.stringify(form) !== JSON.stringify(restaurant);
  }, [form, restaurant]);

  const greetingPreview = useMemo(() => {
    if (!form) return "";
    const hour = Number(
      new Intl.DateTimeFormat("en-GB", {
        hour: "2-digit",
        hour12: false,
        timeZone: form.timezone || "Europe/Rome",
      }).format(new Date())
    );
    const saluto = hour < 14 ? "Buongiorno" : "Buonasera";
    const custom = form.custom_greeting?.trim();
    return custom ? custom.replaceAll("{saluto}", saluto) : `${saluto}, ${form.name}. Come posso aiutarla?`;
  }, [form]);

  if (!form || !restaurant) {
    return (
      <DashboardShell title="Impostazioni" subtitle="Carico la configurazione.">
        <div className="h-72 animate-pulse rounded-[2rem] bg-white/70" />
      </DashboardShell>
    );
  }

  async function save() {
    if (!restaurant || !form) return;
    setSaving(true);
    setMessage(null);
    try {
      const payload = {
        slug: form.slug,
        name: form.name,
        twilio_phone: form.twilio_phone || null,
        voice_provider: form.voice_provider,
        timezone: form.timezone,
        address: form.address,
        opening_hours: form.opening_hours,
        weekly_closures: form.weekly_closures,
        closure_dates: form.closure_dates,
        turni: form.turni,
        booking_rules: form.booking_rules,
        custom_greeting: form.custom_greeting || null,
        agent_style_notes: form.agent_style_notes || null,
        escalation_phone: form.escalation_phone || null,
        is_active: form.is_active,
      };
      const response = await apiFetch<Restaurant>(`/api/restaurants/${restaurant.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setMessageTone("success");
      setMessage(response.sync_status?.message ?? "Configurazione aggiornata.");
      await refreshWorkspace();
    } catch (error) {
      setMessageTone("error");
      setMessage(error instanceof ApiError ? error.message : "Impossibile salvare.");
    } finally {
      setSaving(false);
    }
  }

  function updateField<K extends keyof Restaurant>(field: K, value: Restaurant[K]) {
    setForm((cur) => (cur ? { ...cur, [field]: value } : cur));
  }

  return (
    <DashboardShell
      title="Impostazioni"
      subtitle="Profilo, turni, regole e personalizzazione agente."
    >
      <div className="space-y-6">
        {/* Save bar */}
        {isDirty || message ? (
          <div className="sticky top-3 z-30 flex flex-col gap-3 rounded-[1.5rem] border border-stone/80 bg-white/92 px-4 py-3 shadow-card backdrop-blur sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge tone={isDirty ? "warn" : "good"}>
                {isDirty ? "Modifiche non salvate" : "Salvato"}
              </StatusBadge>
              {message ? (
                <StatusBadge tone={messageTone === "error" ? "danger" : "good"}>
                  {message}
                </StatusBadge>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => void save()}
              disabled={saving || !isDirty}
              className="rounded-full bg-ink px-4 py-3 text-sm font-semibold uppercase tracking-[0.22em] text-ivory transition hover:bg-night disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Salvo..." : "Salva"}
            </button>
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-2">
          {/* Profile */}
          <SectionCard title="Profilo" kicker="Identità ristorante">
            <div className="grid gap-4">
              <Field label="Nome" value={form.name} onChange={(v) => updateField("name", v)} />
              <Field label="Slug" value={form.slug} onChange={(v) => updateField("slug", v)} />
              <Field label="Indirizzo" value={form.address} onChange={(v) => updateField("address", v)} />
              <Field label="Timezone" value={form.timezone} onChange={(v) => updateField("timezone", v)} />
              <div className="grid gap-4 sm:grid-cols-2">
                {Object.entries(form.opening_hours).map(([key, value]) => (
                  <Field
                    key={key}
                    label={DAY_LABELS[key] ?? key}
                    value={value}
                    placeholder="HH:MM-HH:MM"
                    onChange={(v) =>
                      updateField("opening_hours", { ...form.opening_hours, [key]: v })
                    }
                  />
                ))}
              </div>
            </div>
          </SectionCard>

          {/* Telephony */}
          <SectionCard title="Telefono" kicker="Numeri e routing">
            <div className="grid gap-4">
              <div
                className={`flex items-center justify-between gap-4 rounded-2xl border px-4 py-3 ${
                  form.is_active
                    ? "border-olive/30 bg-olive/8"
                    : "border-terracotta/25 bg-terracotta/8"
                }`}
              >
                <div>
                  <p className="text-sm font-semibold text-ink">
                    {form.is_active ? "Agente attivo" : "Agente in pausa"}
                  </p>
                  <p className="mt-0.5 text-xs text-ink/50">
                    {form.is_active
                      ? "Il telefono risponde automaticamente."
                      : "Le chiamate non vengono gestite dall'AI."}
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={form.is_active}
                  onClick={() => updateField("is_active", !form.is_active)}
                  className={`relative h-7 w-12 shrink-0 rounded-full border transition-colors ${
                    form.is_active
                      ? "border-olive/40 bg-olive"
                      : "border-stone bg-stone/40"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all ${
                      form.is_active ? "left-[calc(100%-1.625rem)]" : "left-0.5"
                    }`}
                  />
                </button>
              </div>
              <Field label="Motore voce" value="OpenAI Realtime" disabled />
              <Field
                label="Numero Twilio"
                value={form.twilio_phone ?? ""}
                onChange={(v) => updateField("twilio_phone", v || null)}
              />
              <Field
                label="Numero backup umano"
                value={form.escalation_phone ?? ""}
                onChange={(v) => updateField("escalation_phone", v || null)}
              />
            </div>
          </SectionCard>

          {/* AI Personalization */}
          <SectionCard title="Agente AI" kicker="Personalizzazione">
            <div className="grid gap-4">
              <label className="grid gap-2 text-sm text-ink/65">
                Greeting iniziale
                <textarea
                  rows={2}
                  className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                  placeholder="{saluto}, Trattoria Madonnina. Come posso aiutarla?"
                  value={form.custom_greeting ?? ""}
                  onChange={(e) => updateField("custom_greeting", e.target.value || null)}
                />
              </label>
              <label className="grid gap-2 text-sm text-ink/65">
                Note stile agente
                <textarea
                  rows={3}
                  className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                  placeholder="Warm, concise, premium Italian hospitality tone."
                  value={form.agent_style_notes ?? ""}
                  onChange={(e) => updateField("agent_style_notes", e.target.value || null)}
                />
              </label>
              <div className="rounded-xl border border-stone/70 bg-ivory/50 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ink/40">
                  Anteprima greeting
                </p>
                <p className="mt-2 font-display text-xl leading-tight text-ink">{greetingPreview}</p>
                <p className="mt-2 text-xs text-ink/50">
                  Usa <strong>{`{saluto}`}</strong> per Buongiorno/Buonasera automatico.
                </p>
              </div>
            </div>
          </SectionCard>

          {/* Turni */}
          <SectionCard title="Turni" kicker="Servizi giornalieri">
            <div className="grid gap-4">
              {form.turni.map((turno, index) => (
                <div
                  key={`${turno.name}-${index}`}
                  className="relative grid gap-3 rounded-xl border border-stone/80 bg-ivory/60 p-4 pt-9 sm:grid-cols-4 sm:pt-4"
                >
                  {form.turni.length > 1 ? (
                    <button
                      type="button"
                      title="Rimuovi"
                      onClick={() =>
                        setForm((cur) =>
                          cur ? { ...cur, turni: cur.turni.filter((_, i) => i !== index) } : cur
                        )
                      }
                      className="absolute right-3 top-2 text-xs text-ink/30 transition hover:text-terracotta"
                    >
                      ✕
                    </button>
                  ) : null}
                  <Field
                    label="Nome"
                    value={turno.name}
                    onChange={(v) =>
                      setForm((cur) =>
                        cur
                          ? { ...cur, turni: cur.turni.map((t, i) => (i === index ? { ...t, name: v } : t)) }
                          : cur
                      )
                    }
                  />
                  <label className="grid gap-2 text-sm text-ink/65">
                    Inizio
                    <input
                      type="time"
                      className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={turno.start}
                      onChange={(e) =>
                        setForm((cur) =>
                          cur
                            ? { ...cur, turni: cur.turni.map((t, i) => (i === index ? { ...t, start: e.target.value } : t)) }
                            : cur
                        )
                      }
                    />
                  </label>
                  <label className="grid gap-2 text-sm text-ink/65">
                    Fine
                    <input
                      type="time"
                      className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={turno.end}
                      onChange={(e) =>
                        setForm((cur) =>
                          cur
                            ? { ...cur, turni: cur.turni.map((t, i) => (i === index ? { ...t, end: e.target.value } : t)) }
                            : cur
                        )
                      }
                    />
                  </label>
                  <label className="grid gap-2 text-sm text-ink/65">
                    Coperti max
                    <input
                      type="number"
                      min={1}
                      className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={turno.max_covers}
                      onChange={(e) =>
                        setForm((cur) =>
                          cur
                            ? { ...cur, turni: cur.turni.map((t, i) => (i === index ? { ...t, max_covers: Number(e.target.value) } : t)) }
                            : cur
                        )
                      }
                    />
                  </label>
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setForm((cur) =>
                    cur
                      ? { ...cur, turni: [...cur.turni, { name: "", start: "19:00", end: "23:00", max_covers: 30 }] }
                      : cur
                  )
                }
                className="rounded-xl border border-dashed border-stone/60 px-4 py-3 text-sm text-ink/50 transition hover:border-gold hover:text-ink/70"
              >
                + Aggiungi turno
              </button>
            </div>
          </SectionCard>
        </div>

        {/* Booking rules + closures — full width */}
        <SectionCard title="Regole prenotazione" kicker="Booking engine">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Object.entries(form.booking_rules).map(([key, value]) => {
              const labels: Record<string, string> = {
                min_party: "Coperti min",
                max_party: "Coperti max",
                large_group_threshold: "Soglia gruppi",
                max_advance_days: "Max giorni avanti",
                min_lead_hours: "Preavviso min (h)",
              };
              return (
                <label key={key} className="grid gap-2 text-sm text-ink/65">
                  {labels[key] ?? key}
                  <input
                    type="number"
                    min={0}
                    className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                    value={value}
                    onChange={(e) =>
                      updateField("booking_rules", { ...form.booking_rules, [key]: Number(e.target.value) })
                    }
                  />
                </label>
              );
            })}
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Field
              label="Chiusure settimanali (virgola)"
              value={form.weekly_closures.join(", ")}
              onChange={(v) =>
                updateField(
                  "weekly_closures",
                  v.split(",").map((s) => s.trim()).filter(Boolean)
                )
              }
            />
            <Field
              label="Chiusure straordinarie (YYYY-MM-DD)"
              value={form.closure_dates.join(", ")}
              onChange={(v) =>
                updateField(
                  "closure_dates",
                  v.split(",").map((s) => s.trim()).filter(Boolean)
                )
              }
            />
          </div>
        </SectionCard>
      </div>
    </DashboardShell>
  );
}

function Field({
  label,
  value,
  placeholder,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  disabled?: boolean;
  onChange?: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm text-ink/65">
      {label}
      <input
        className={`rounded-2xl border border-stone px-4 py-3 text-ink outline-none transition focus:border-gold ${
          disabled ? "bg-stone/20 text-ink/50" : "bg-ivory/80"
        }`}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        readOnly={disabled}
        onChange={onChange ? (e) => onChange(e.target.value) : undefined}
      />
    </label>
  );
}
