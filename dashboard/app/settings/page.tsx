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

const openAiModelPresets = ["gpt-5.4", "gpt-5", "gpt-5-mini", "gpt-5-nano"];
const reasoningEffortOptions = ["none", "minimal", "low", "medium", "high", "xhigh"];
const verbosityOptions = ["low", "medium", "high"];

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
        assistant_settings: form.assistant_settings,
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

            <div className="grid gap-4 md:grid-cols-2">
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
              <p className="text-xs uppercase tracking-[0.24em] text-ink/45">Modello e comportamento</p>
              <div className="mt-4 grid gap-4">
                <label className="grid gap-2 text-sm text-ink/65">
                  Provider LLM
                  <input
                    className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                    value={form.assistant_settings.llm_provider}
                    readOnly
                  />
                </label>

                <label className="grid gap-2 text-sm text-ink/65">
                  Modello OpenAI
                  <div className="grid gap-3 md:grid-cols-[0.45fr_0.55fr]">
                    <select
                      className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={
                        openAiModelPresets.includes(form.assistant_settings.openai_model)
                          ? form.assistant_settings.openai_model
                          : "custom"
                      }
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                assistant_settings: {
                                  ...current.assistant_settings,
                                  openai_model:
                                    event.target.value === "custom"
                                      ? current.assistant_settings.openai_model
                                      : event.target.value
                                }
                              }
                            : current
                        )
                      }
                    >
                      {openAiModelPresets.map((model) => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                      <option value="custom">Custom</option>
                    </select>
                    <input
                      className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={form.assistant_settings.openai_model}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                assistant_settings: {
                                  ...current.assistant_settings,
                                  openai_model: event.target.value
                                }
                              }
                            : current
                        )
                      }
                    />
                  </div>
                </label>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="grid gap-2 text-sm text-ink/65">
                    Reasoning effort
                    <select
                      className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={form.assistant_settings.reasoning_effort}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                assistant_settings: {
                                  ...current.assistant_settings,
                                  reasoning_effort: event.target.value as Restaurant["assistant_settings"]["reasoning_effort"]
                                }
                              }
                            : current
                        )
                      }
                    >
                      {reasoningEffortOptions.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="grid gap-2 text-sm text-ink/65">
                    Verbosità risposta
                    <select
                      className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                      value={form.assistant_settings.response_verbosity}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? {
                                ...current,
                                assistant_settings: {
                                  ...current.assistant_settings,
                                  response_verbosity: event.target.value as Restaurant["assistant_settings"]["response_verbosity"]
                                }
                              }
                            : current
                        )
                      }
                    >
                      {verbosityOptions.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <label className="grid gap-2 text-sm text-ink/65">
                  Greeting iniziale personalizzato
                  <textarea
                    rows={3}
                    className="rounded-2xl border border-stone bg-white/80 px-4 py-3 text-ink outline-none transition focus:border-gold"
                    placeholder="Buonasera, Trattoria da Mario. Come posso aiutarla?"
                    value={form.assistant_settings.custom_greeting ?? ""}
                    onChange={(event) =>
                      setForm((current) =>
                        current
                          ? {
                              ...current,
                              assistant_settings: {
                                ...current.assistant_settings,
                                custom_greeting: event.target.value || null
                              }
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
                    value={form.assistant_settings.agent_style_notes ?? ""}
                    onChange={(event) =>
                      setForm((current) =>
                        current
                          ? {
                              ...current,
                              assistant_settings: {
                                ...current.assistant_settings,
                                agent_style_notes: event.target.value || null
                              }
                            }
                          : current
                      )
                    }
                  />
                </label>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-stone/80 bg-white/70 p-4 text-sm leading-7 text-ink/65">
              Il numero Twilio, il numero di escalation e l’agent id restano configurabili qui sopra. Il
              modello OpenAI scelto viene salvato nel ristorante e incluso nella personalizzazione runtime
              verso ElevenLabs, così non rimane più solo scritto nella documentazione.
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
                    className="grid gap-3 rounded-[1.5rem] border border-stone/80 bg-ivory/70 p-4 md:grid-cols-4"
                  >
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
              </div>

              <div className="grid gap-4 md:grid-cols-2">
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
                className="rounded-2xl bg-ink px-5 py-3 text-sm font-semibold uppercase tracking-[0.26em] text-ivory"
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
