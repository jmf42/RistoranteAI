"use client";

import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { SectionCard } from "@/components/section-card";
import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch } from "@/lib/api";
import { Restaurant } from "@/lib/types";

const profileFields: Array<{
  field: "name" | "slug" | "address" | "timezone";
  label: string;
}> = [
  { field: "name", label: "Nome ristorante" },
  { field: "slug", label: "Slug" },
  { field: "address", label: "Indirizzo" },
  { field: "timezone", label: "Timezone" }
];

const telephonyFields: Array<{
  field: "twilio_phone" | "elevenlabs_agent_id" | "escalation_phone";
  label: string;
}> = [
  { field: "twilio_phone", label: "Numero Twilio" },
  { field: "elevenlabs_agent_id", label: "Agent id ElevenLabs" },
  { field: "escalation_phone", label: "Numero trasferimento umano" }
];

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

  if (!form || !restaurant) {
    return (
      <DashboardShell
        title="Impostazioni"
        subtitle="Carico la configurazione del ristorante."
      >
        <div className="h-72 animate-pulse rounded-[2rem] bg-white/70" />
      </DashboardShell>
    );
  }

  async function save() {
    if (!restaurant || !form) {
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const payload = {
        slug: form.slug,
        name: form.name,
        twilio_phone: form.twilio_phone || null,
        elevenlabs_agent_id: form.elevenlabs_agent_id || null,
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
        body: JSON.stringify(payload)
      });
      setMessageTone("success");
      setMessage(response.sync_status?.message ?? "Configurazione aggiornata.");
      await refreshWorkspace();
    } catch (error) {
      setMessageTone("error");
      setMessage(error instanceof ApiError ? error.message : "Impossibile salvare la configurazione.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <DashboardShell
      title="Impostazioni ristorante"
      subtitle="Configura identità, numeri telefonici e cervello AI del ristorante senza toccare codice."
    >
      <div className="grid gap-6 xl:grid-cols-[0.55fr_0.45fr]">
        <SectionCard title="Profilo ristorante" kicker="Core profile">
          <div className="grid gap-4">
            {profileFields.map(({ field, label }) => (
              <label key={field} className="grid gap-2 text-sm text-ink/65">
                {label}
                <input
                  className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                  value={form[field] ?? ""}
                  onChange={(event) =>
                    setForm((current) =>
                      current
                        ? {
                            ...current,
                            [field]: event.target.value
                          }
                        : current
                    )
                  }
                />
              </label>
            ))}

            <div className="mt-2 rounded-[1.5rem] border border-stone/80 bg-ivory/60 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-ink/45">Numeri e routing</p>
              <div className="mt-4 grid gap-4">
                {telephonyFields.map(({ field, label }) => (
                  <label key={field} className="grid gap-2 text-sm text-ink/65">
                    {label}
                    <input
                      className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={form[field] ?? ""}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                [field]: event.target.value
                              }
                            : current
                        )
                      }
                    />
                  </label>
                ))}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {Object.entries(form.opening_hours).map(([key, value]) => (
                <label key={key} className="grid gap-2 text-sm text-ink/65">
                  Orario {key}
                  <input
                    className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                    placeholder="HH:MM-HH:MM"
                    pattern="\d{2}:\d{2}-\d{2}:\d{2}"
                    title="Formato: HH:MM-HH:MM (es. 12:00-15:00)"
                    value={value}
                    onChange={(event) =>
                      setForm((current) =>
                        current
                          ? {
                              ...current,
                              opening_hours: {
                                ...current.opening_hours,
                                [key]: event.target.value
                              }
                            }
                          : current
                      )
                    }
                  />
                </label>
              ))}
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Cervello AI e telefono" kicker="Owner configurable">
          <div className="space-y-5">
            <div className="rounded-[1.5rem] border border-stone/80 bg-ivory/60 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-ink/45">Personalizzazione agente</p>
              <div className="mt-4 grid gap-4">
                <label className="grid gap-2 text-sm text-ink/65">
                  Greeting iniziale personalizzato
                  <textarea
                    rows={3}
                    className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                    placeholder="{saluto}, Trattoria Madonnina. Come posso aiutarla?"
                    value={form.custom_greeting ?? ""}
                    onChange={(event) =>
                      setForm((current) =>
                        current
                          ? {
                              ...current,
                              custom_greeting: event.target.value || null
                            }
                          : current
                      )
                    }
                  />
                </label>

                <label className="grid gap-2 text-sm text-ink/65">
                  Note stile agente
                  <textarea
                    rows={4}
                    className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                    placeholder="Warm, concise, premium Italian hospitality tone."
                    value={form.agent_style_notes ?? ""}
                    onChange={(event) =>
                      setForm((current) =>
                        current
                          ? {
                              ...current,
                              agent_style_notes: event.target.value || null
                            }
                          : current
                      )
                    }
                  />
                </label>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-stone/80 bg-white/70 p-4 text-sm leading-7 text-ink/65">
              Usa <strong>{`{saluto}`}</strong> nel greeting per inserire automaticamente &ldquo;Buongiorno&rdquo; o &ldquo;Buonasera&rdquo; in base all&apos;orario. Esempio: <em>{`{saluto}, Trattoria Madonnina. Come posso aiutarla?`}</em>. Se lasci il campo vuoto, il sistema genera il saluto automaticamente. Le note stile vengono iniettate nel prompt di sistema dell&apos;agente ElevenLabs per calibrare tono e comportamento. Modello LLM, voce e parametri avanzati si configurano direttamente nella console ElevenLabs.
            </div>
          </div>
        </SectionCard>

        <div className="xl:col-span-2">
          <SectionCard title="Turni e regole" kicker="Booking engine">
            <div className="space-y-5">
              <div className="grid gap-4">
                {form.turni.map((turno, index) => (
                  <div
                    key={`${turno.name}-${index}`}
                    className="relative grid gap-3 rounded-[1.5rem] border border-stone/80 bg-ivory/70 p-4 pt-10 sm:grid-cols-2 sm:pt-4 xl:grid-cols-4"
                  >
                    {form.turni.length > 1 ? (
                      <button
                        type="button"
                        title="Rimuovi turno"
                        onClick={() =>
                          setForm((current) =>
                            current
                              ? { ...current, turni: current.turni.filter((_, i) => i !== index) }
                              : current
                          )
                        }
                        className="absolute right-3 top-3 rounded-full border border-stone/60 px-2 py-0.5 text-xs text-ink/40 transition hover:border-terracotta hover:text-terracotta"
                      >
                        ✕
                      </button>
                    ) : null}
                    <label className="grid gap-2 text-sm text-ink/65">
                      Nome turno
                      <input
                        className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                        value={turno.name}
                        onChange={(event) =>
                          setForm((current) =>
                            current
                              ? {
                                  ...current,
                                  turni: current.turni.map((item, itemIndex) =>
                                    itemIndex === index ? { ...item, name: event.target.value } : item
                                  )
                                }
                              : current
                          )
                        }
                      />
                    </label>
                    {(["start", "end"] as const).map((field) => (
                      <label key={field} className="grid gap-2 text-sm text-ink/65">
                        {field === "start" ? "Inizio" : "Fine"}
                        <input
                          type="time"
                          className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                          value={turno[field]}
                          onChange={(event) =>
                            setForm((current) =>
                              current
                                ? {
                                    ...current,
                                    turni: current.turni.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, [field]: event.target.value } : item
                                    )
                                  }
                                : current
                            )
                          }
                        />
                      </label>
                    ))}
                    <label className="grid gap-2 text-sm text-ink/65">
                      Coperti max
                      <input
                        type="number"
                        min={1}
                        className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                        value={turno.max_covers}
                        onChange={(event) =>
                          setForm((current) =>
                            current
                              ? {
                                  ...current,
                                  turni: current.turni.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? { ...item, max_covers: Number(event.target.value) }
                                      : item
                                  )
                                }
                              : current
                          )
                        }
                      />
                    </label>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() =>
                    setForm((current) =>
                      current
                        ? {
                            ...current,
                            turni: [...current.turni, { name: "", start: "19:00", end: "23:00", max_covers: 30 }]
                          }
                        : current
                    )
                  }
                  className="rounded-[1.5rem] border border-dashed border-stone/60 px-4 py-3 text-sm text-ink/50 transition hover:border-gold hover:text-ink/70"
                >
                  + Aggiungi turno
                </button>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {Object.entries(form.booking_rules).map(([key, value]) => {
                  const ruleLabels: Record<string, string> = {
                    min_party: "Coperti minimi",
                    max_party: "Coperti massimi",
                    large_group_threshold: "Soglia gruppo grande",
                    max_advance_days: "Prenotazione max giorni avanti",
                    min_lead_hours: "Preavviso minimo (ore)",
                  };
                  return (
                  <label key={key} className="grid gap-2 text-sm text-ink/65">
                    {ruleLabels[key] ?? key}
                    <input
                      type="number"
                      min={0}
                      className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={value}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                booking_rules: {
                                  ...current.booking_rules,
                                  [key]: Number(event.target.value)
                                }
                              }
                            : current
                        )
                      }
                    />
                  </label>
                  );
                })}
              </div>

              <label className="grid gap-2 text-sm text-ink/65">
                Chiusure settimanali (separate da virgola)
                <input
                  className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                  value={form.weekly_closures.join(", ")}
                  onChange={(event) =>
                    setForm((current) =>
                      current
                        ? {
                            ...current,
                            weekly_closures: event.target.value
                              .split(",")
                              .map((item) => item.trim())
                              .filter(Boolean)
                          }
                        : current
                    )
                  }
                />
              </label>

              <label className="grid gap-2 text-sm text-ink/65">
                Chiusure straordinarie (YYYY-MM-DD, separate da virgola)
                <input
                  className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                  value={form.closure_dates.join(", ")}
                  onChange={(event) =>
                    setForm((current) =>
                      current
                        ? {
                            ...current,
                            closure_dates: event.target.value
                              .split(",")
                              .map((item) => item.trim())
                              .filter(Boolean)
                          }
                        : current
                    )
                  }
                />
              </label>

              <button
                type="button"
                onClick={() => void save()}
                disabled={saving}
                className="rounded-2xl bg-ink px-5 py-3 text-sm font-semibold uppercase tracking-[0.26em] text-ivory transition hover:bg-night disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? "Salvo..." : "Salva configurazione"}
              </button>
              {message ? (
                <p className={`text-sm ${messageTone === "error" ? "text-terracotta" : "text-olive"}`}>
                  {message}
                </p>
              ) : null}
            </div>
          </SectionCard>
        </div>
      </div>
    </DashboardShell>
  );
}
