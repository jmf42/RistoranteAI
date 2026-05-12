"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  Mic,
  PlayCircle,
  RotateCcw,
  Save,
  Send,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Wand2,
} from "lucide-react";

import { useWorkspace } from "@/components/workspace-provider";
import { ApiError, apiFetch } from "@/lib/api";
import type {
  StudioAgentPreview,
  StudioConfigUpdateResponse,
  StudioSessionOverrides,
  StudioSimulationResponse,
} from "@/lib/types";

const PROMPT_GUIDE = [
  {
    title: "Structured sections",
    body: "Keep labeled sections like Role, Language, Context, Tools, Safety, and Unclear Audio. The Realtime guide recommends bullets over long prose.",
  },
  {
    title: "Tool preambles",
    body: "Before each tool call, use one short line like “Controllo subito.” and then call the tool immediately.",
  },
  {
    title: "Language pinning",
    body: "Prefer a clear language strategy. By default, let the agent mirror the caller’s language; only pin one language when you explicitly need that constraint.",
  },
  {
    title: "Write-action safety",
    body: "Create, modify, and cancel should require explicit confirmation in a separate turn. The backend also enforces this.",
  },
  {
    title: "Escape hatch",
    body: "Voice agents should have a stable human-handoff path for out-of-scope or risky cases instead of over-handling them.",
  },
];

function compact(obj: StudioSessionOverrides): StudioSessionOverrides {
  return Object.fromEntries(
    Object.entries(obj).filter(([, value]) => value !== null && value !== undefined && value !== "")
  ) as StudioSessionOverrides;
}

function serializeStudioState(prompt: string, overrides: StudioSessionOverrides): string {
  return JSON.stringify({
    prompt: prompt.trim(),
    overrides: compact(overrides),
  });
}

export default function StudioPage() {
  const router = useRouter();
  const { user, restaurant, restaurants, activeRestaurantId, setActiveRestaurantId, loading, logout } =
    useWorkspace();

  const [preview, setPreview] = useState<StudioAgentPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [overrides, setOverrides] = useState<StudioSessionOverrides>({});
  const [saving, setSaving] = useState(false);
  const [publishInfo, setPublishInfo] = useState<StudioConfigUpdateResponse | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const [chatInput, setChatInput] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [sim, setSim] = useState<StudioSimulationResponse | null>(null);
  const [simulating, setSimulating] = useState(false);

  const [tab, setTab] = useState<"prompt" | "config" | "simulate">("prompt");

  function flash(msg: string, ok: boolean) {
    setToast({ msg, ok });
    window.setTimeout(() => setToast(null), 4000);
  }

  async function loadPreview(restaurantId: string) {
    setLoadingPreview(true);
    try {
      const nextPreview = await apiFetch<StudioAgentPreview>(
        `/api/studio/agent?restaurant_id=${encodeURIComponent(restaurantId)}`
      );
      setPreview(nextPreview);
      setPrompt(nextPreview.saved_prompt_override ?? nextPreview.prompt);
      setOverrides(nextPreview.effective_session_overrides ?? {});
      setChatInput(nextPreview.scenarios[0]?.message ?? "");
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Failed to load agent config", false);
    } finally {
      setLoadingPreview(false);
    }
  }

  useEffect(() => {
    if (!restaurant?.id) return;
    setPublishInfo(null);
    void loadPreview(restaurant.id);
  }, [restaurant?.id, activeRestaurantId]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-grain">
        <p className="font-display text-2xl text-ink/60">Loading...</p>
      </div>
    );
  }

  if (user.role !== "operator") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-grain px-6">
        <div className="max-w-md rounded-3xl border border-stone bg-white p-8 text-center shadow-card">
          <p className="font-display text-2xl text-ink">Access Restricted</p>
          <p className="mt-3 text-sm text-ink/60">This console is only available to platform operators.</p>
          <Link href="/" className="mt-6 inline-block rounded-2xl bg-ink px-6 py-3 text-sm font-semibold text-ivory">
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  async function save() {
    if (!restaurant?.id) return;
    setSaving(true);
    try {
      const response = await apiFetch<StudioConfigUpdateResponse>("/api/studio/config", {
        method: "PUT",
        body: JSON.stringify({
          restaurant_id: restaurant.id,
          prompt_override: prompt.trim() || null,
          session_overrides: compact(overrides),
        }),
      });
      setPublishInfo(response);
      setPrompt(response.effective_prompt);
      setOverrides(response.effective_session_overrides ?? {});
      await loadPreview(restaurant.id);
      const warningCount = response.prompt_diagnostics.filter((item) => item.status !== "good").length;
      flash(
        warningCount
          ? `Published live with ${warningCount} prompt quality warning${warningCount === 1 ? "" : "s"}.`
          : "Published live. Backend confirmed the exact prompt for the next new call.",
        response.deployment_status === "live"
      );
    } catch (err) {
      flash(err instanceof Error ? err.message : "Save failed", false);
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    if (!restaurant?.id) return;
    setSaving(true);
    try {
      const response = await apiFetch<StudioConfigUpdateResponse>(
        `/api/studio/config?restaurant_id=${encodeURIComponent(restaurant.id)}`,
        { method: "DELETE" }
      );
      setPublishInfo(response);
      await loadPreview(restaurant.id);
      setSim(null);
      flash("Reset live config. The backend default prompt is active for the next new call.", true);
    } catch (err) {
      flash(err instanceof Error ? err.message : "Reset failed", false);
    } finally {
      setSaving(false);
    }
  }

  async function simulate(messages: string[]) {
    if (!restaurant?.id || !messages.length) return;
    setSimulating(true);
    try {
      const response = await apiFetch<StudioSimulationResponse>("/api/studio/simulate", {
        method: "POST",
        body: JSON.stringify({
          restaurant_id: restaurant.id,
          caller_phone: "+390000000000",
          user_messages: messages,
          prompt_override: prompt.trim() || undefined,
          session_overrides: compact(overrides),
        }),
      });
      setSim(response);
      setHistory(messages);
      setChatInput("");
      flash("Simulation complete.", true);
    } catch (err) {
      flash(err instanceof Error ? err.message : "Simulation failed", false);
    } finally {
      setSimulating(false);
    }
  }

  function applyPreset(presetId: string) {
    const preset = preview?.presets.find((item) => item.id === presetId);
    if (!preset) return;
    setOverrides((prev) => ({ ...prev, ...preset.session_overrides }));
    flash(`Loaded preset: ${preset.label}. Publish live when you're ready.`, true);
  }

  function set<K extends keyof StudioSessionOverrides>(key: K, value: StudioSessionOverrides[K]) {
    setOverrides((prev) => ({ ...prev, [key]: value }));
  }

  const livePrompt = preview?.saved_prompt_override ?? preview?.prompt ?? "";
  const liveOverrides = preview?.effective_session_overrides ?? {};
  const hasDraftChanges = preview
    ? serializeStudioState(prompt, overrides) !== serializeStudioState(livePrompt, liveOverrides)
    : false;

  const tabs = [
    { id: "prompt" as const, label: "Prompt", icon: Sparkles },
    { id: "config" as const, label: "Settings", icon: SlidersHorizontal },
    { id: "simulate" as const, label: "Simulator", icon: PlayCircle },
  ];
  const activePromptChecks = publishInfo?.prompt_diagnostics ?? preview?.prompt_diagnostics ?? [];
  const activeWarningCount = activePromptChecks.filter((item) => item.status !== "good").length;

  return (
    <div className="min-h-screen bg-grain text-ink">
      <header className="sticky top-0 z-40 border-b border-stone/60 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-4">
            <Link href="/" className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-stone hover:bg-ivory">
              <ArrowLeft size={16} />
            </Link>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-terracotta/70">Voice Studio</p>
              <p className="text-sm text-ink/60">{restaurant?.name ?? "No restaurant"}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {restaurants.length > 1 && (
              <select
                className="rounded-xl border border-stone bg-ivory/80 px-3 py-2 text-sm text-ink outline-none"
                value={activeRestaurantId ?? ""}
                onChange={(e) => setActiveRestaurantId(e.target.value)}
              >
                {restaurants.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={save}
              disabled={saving || !hasDraftChanges}
              className="flex items-center gap-2 rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-ivory disabled:opacity-50"
            >
              <Save size={14} /> {saving ? "Publishing..." : hasDraftChanges ? "Publish live" : "Published"}
            </button>
            <button
              onClick={reset}
              disabled={saving}
              className="flex items-center gap-2 rounded-xl border border-stone px-4 py-2 text-sm font-semibold text-ink disabled:opacity-50"
            >
              <Trash2 size={14} /> Reset
            </button>
            <button
              onClick={async () => {
                await logout();
                router.replace("/login");
              }}
              className="rounded-xl border border-stone px-3 py-2 text-xs text-ink/60 hover:text-ink"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {toast && (
        <div
          className={`fixed left-1/2 top-16 z-50 -translate-x-1/2 rounded-xl px-5 py-3 text-sm font-medium shadow-lg ${
            toast.ok ? "bg-olive text-ivory" : "bg-terracotta text-ivory"
          }`}
        >
          {toast.msg}
        </div>
      )}

      <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
        <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-3xl border border-stone/60 bg-white/80 p-5 shadow-card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-terracotta/70">OpenAI Realtime</p>
                <h1 className="mt-2 font-display text-3xl text-ink">Tune the live phone agent.</h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-ink/60">
                  This page is now only for things that actually matter in production: prompt, preset, voice, turn-taking,
                  language, and a few call-stability controls.
                </p>
              </div>
              <div className="space-y-3">
                <div className="rounded-2xl border border-stone/60 bg-ivory/70 px-4 py-3 text-right">
                  <p className="text-xs uppercase tracking-[0.16em] text-ink/40">Live provider</p>
                  <p className="mt-1 text-sm font-semibold text-ink">{restaurant?.voice_provider ?? "unknown"}</p>
                </div>
                <div
                  className={`rounded-2xl border px-4 py-3 text-right ${
                    hasDraftChanges ? "border-gold/50 bg-gold/10" : "border-olive/20 bg-olive/10"
                  }`}
                >
                  <p className="text-xs uppercase tracking-[0.16em] text-ink/40">Studio status</p>
                  <p className={`mt-1 text-sm font-semibold ${hasDraftChanges ? "text-gold" : "text-olive"}`}>
                    {hasDraftChanges ? "Draft changes not published" : "Live config published"}
                  </p>
                </div>
              </div>
            </div>
            <div className="mt-5 rounded-2xl border border-olive/20 bg-olive/10 p-4">
              <p className="text-sm font-semibold text-olive">How publish works</p>
              <p className="mt-2 text-sm leading-6 text-ink/65">
                Publishing here writes the prompt and settings straight to the restaurant record in the live database.
                New inbound calls load that record again, so the next new call uses the latest published config without a Cloud Run redeploy.
              </p>
              {publishInfo && (
                <div className="mt-4 rounded-xl border border-olive/20 bg-white/70 px-4 py-3 text-sm text-ink/65">
                  <p className="font-semibold text-ink">Latest verified publish</p>
                  <p className="mt-1">{publishInfo.deployment_message}</p>
                  <p className="mt-2 font-mono text-xs text-ink/50">
                    Prompt fingerprint: {publishInfo.effective_prompt_hash}
                    {publishInfo.published_at ? ` · ${new Date(publishInfo.published_at).toLocaleString()}` : ""}
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-stone/60 bg-white/80 p-5 shadow-card">
            <div className="flex items-center gap-2">
              <Wand2 size={16} className="text-terracotta" />
              <h2 className="font-semibold text-ink">Recommended presets</h2>
            </div>
            <p className="mt-2 text-sm leading-6 text-ink/55">
              Start from one of these instead of tuning everything manually.
            </p>
            <div className="mt-4 space-y-3">
              {preview?.presets.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => applyPreset(preset.id)}
                  className="w-full rounded-2xl border border-stone/60 bg-ivory/60 p-4 text-left transition hover:border-gold hover:bg-ivory"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold text-ink">{preset.label}</span>
                    <span className="text-xs text-ink/45">{preset.session_overrides.model}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-ink/55">{preset.description}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-5 flex gap-1 rounded-2xl border border-stone/60 bg-white/70 p-1.5">
          {tabs.map((item) => {
            const Icon = item.icon;
            const active = tab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setTab(item.id)}
                className={`flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                  active ? "bg-ink text-ivory shadow-sm" : "text-ink/55 hover:text-ink"
                }`}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </div>

        {loadingPreview ? (
          <div className="flex items-center justify-center py-20">
            <p className="text-sm text-ink/50">Loading agent config...</p>
          </div>
        ) : (
          <>
            {tab === "prompt" && (
              <div className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
                <div>
                  <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <h3 className="font-semibold text-ink">System prompt</h3>
                        <p className="mt-1 text-sm text-ink/55">
                          Keep it short, bulleted, explicit, and voice-native.
                        </p>
                      </div>
                      {preview?.saved_prompt_override && (
                        <span className="rounded-full bg-olive/15 px-3 py-1 text-xs font-semibold text-olive">Custom</span>
                      )}
                    </div>
                    <textarea
                      rows={26}
                      className="mt-4 w-full rounded-xl border border-stone/60 bg-ivory/50 px-4 py-4 text-sm leading-7 text-ink outline-none transition focus:border-gold"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="Write your system prompt here..."
                    />
                  </div>
                </div>

                <div>
                  <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                    <h3 className="font-semibold text-ink">Good prompt shape</h3>
                    <p className="mt-1 text-sm text-ink/55">
                      These checks come from the backend prompt diagnostics, not the browser draft alone.
                    </p>
                    <div className="mt-4 space-y-3">
                      <div
                        className={`rounded-xl border p-4 ${
                          activeWarningCount === 0 ? "border-olive/20 bg-olive/10" : "border-gold/40 bg-gold/10"
                        }`}
                      >
                        <p className={`font-medium ${activeWarningCount === 0 ? "text-olive" : "text-gold"}`}>
                          {activeWarningCount === 0
                            ? "Prompt checks passed"
                            : `${activeWarningCount} prompt quality warning${activeWarningCount === 1 ? "" : "s"}`}
                        </p>
                        <p className="mt-1 text-sm leading-6 text-ink/60">
                          Publish still works, but the backend is flagging the items below as likely voice-agent risks.
                        </p>
                      </div>
                      {activePromptChecks.map((item) => (
                        <div key={item.label} className="rounded-xl border border-stone/60 bg-ivory/60 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-medium text-ink">{item.label}</p>
                            <span
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                                item.status === "good"
                                  ? "bg-olive/15 text-olive"
                                  : "bg-gold/15 text-gold"
                              }`}
                            >
                              {item.status}
                            </span>
                          </div>
                          <p className="mt-1 text-sm leading-6 text-ink/55">{item.detail}</p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-5 space-y-3">
                      {PROMPT_GUIDE.map((item) => (
                        <div key={item.title} className="rounded-xl border border-stone/60 bg-ivory/60 p-4">
                          <p className="font-medium text-ink">{item.title}</p>
                          <p className="mt-1 text-sm leading-6 text-ink/55">{item.body}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {tab === "config" && (
              <div className="mt-5 grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
                <div className="space-y-5">
                  <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                    <div className="flex items-center gap-2">
                      <Bot size={16} className="text-terracotta" />
                      <h3 className="font-semibold text-ink">Live controls</h3>
                    </div>
                    <p className="mt-1 text-sm text-ink/55">
                      This is intentionally short. Every control here is wired into the live runtime and useful in practice.
                    </p>
                    <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      <Field label="Model">
                        <select value={overrides.model ?? "gpt-realtime-2"} onChange={(e) => set("model", e.target.value)}>
                          <option value="gpt-realtime-2">gpt-realtime-2</option>
                          <option value="gpt-realtime-1.5">gpt-realtime-1.5</option>
                          <option value="gpt-realtime">gpt-realtime</option>
                          <option value="gpt-realtime-mini">gpt-realtime-mini</option>
                        </select>
                      </Field>
                      <Field label="Voice">
                        <select value={overrides.voice ?? "cedar"} onChange={(e) => set("voice", e.target.value)}>
                          {["marin", "cedar", "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"].map((voice) => (
                            <option key={voice} value={voice}>
                              {voice}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <div className="rounded-xl border border-stone/60 bg-ivory/60 px-4 py-3 text-sm leading-6 text-ink/55">
                        Il prompt ora controlla la brevità delle risposte. Questo evita un cursore “reply length” che non influenzava davvero il runtime live.
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                    <div className="flex items-center gap-2">
                      <Mic size={16} className="text-terracotta" />
                      <h3 className="font-semibold text-ink">Turn-taking & audio</h3>
                    </div>
                    <p className="mt-1 text-sm text-ink/55">
                      Phone calls need patient turn-taking, noise reduction, and Italian transcription pinning.
                    </p>
                    <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      <Field label="Detection type">
                        <select
                          value={overrides.turn_detection_type ?? "server_vad"}
                          onChange={(e) => set("turn_detection_type", e.target.value as "server_vad" | "semantic_vad")}
                        >
                          <option value="server_vad">Server VAD</option>
                          <option value="semantic_vad">Semantic VAD</option>
                        </select>
                      </Field>
                      {(overrides.turn_detection_type ?? "server_vad") === "semantic_vad" ? (
                        <div className="rounded-xl border border-stone/60 bg-ivory/60 px-4 py-3 text-sm leading-6 text-ink/55">
                          Semantic VAD uses the runtime default eagerness. This studio keeps that advanced tuning hidden on purpose.
                        </div>
                      ) : (
                        <>
                          <Field label="VAD threshold">
                            <input
                              type="number"
                              step="0.05"
                              min="0"
                              max="1"
                              value={overrides.vad_threshold ?? 0.55}
                              onChange={(e) => set("vad_threshold", parseFloat(e.target.value))}
                            />
                          </Field>
                          <Field label="Silence duration (ms)">
                            <input
                              type="number"
                              step="50"
                              min="100"
                              max="5000"
                              value={overrides.vad_silence_duration_ms ?? 700}
                              onChange={(e) => set("vad_silence_duration_ms", parseInt(e.target.value, 10))}
                            />
                          </Field>
                          <Field label="Idle timeout (ms)" hint="Useful for missed VAD and quiet callers">
                            <input
                              type="number"
                              step="250"
                              min="0"
                              max="60000"
                              value={overrides.vad_idle_timeout_ms ?? 6000}
                              onChange={(e) => set("vad_idle_timeout_ms", parseInt(e.target.value, 10))}
                            />
                          </Field>
                        </>
                      )}
                      <Field label="Noise reduction">
                        <select
                          value={overrides.noise_reduction_type ?? "near_field"}
                          onChange={(e) => set("noise_reduction_type", e.target.value as "near_field" | "far_field" | "off")}
                        >
                          <option value="near_field">near_field</option>
                          <option value="far_field">far_field</option>
                          <option value="off">off</option>
                        </select>
                      </Field>
                      <Field label="Input language">
                        <select value={overrides.input_language ?? ""} onChange={(e) => set("input_language", e.target.value)}>
                          <option value="">auto-detect / mirror caller</option>
                          <option value="it">it</option>
                          <option value="en">en</option>
                          <option value="fr">fr</option>
                          <option value="de">de</option>
                          <option value="es">es</option>
                        </select>
                      </Field>
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-1">
                      <ToggleRow
                        label="Enable tracing"
                        checked={overrides.tracing_enabled ?? true}
                        onChange={(checked) => set("tracing_enabled", checked)}
                      />
                    </div>
                  </div>

                  <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                    <div className="flex items-center gap-2">
                      <AlertTriangle size={16} className="text-terracotta" />
                      <h3 className="font-semibold text-ink">Context & cost control</h3>
                    </div>
                    <p className="mt-1 text-sm text-ink/55">
                      Realtime costs grow with conversation length. Retention-ratio truncation helps keep long calls stable.
                    </p>
                    <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      <Field label="Truncation mode">
                        <select
                          value={overrides.truncation_mode ?? "retention_ratio"}
                          onChange={(e) => set("truncation_mode", e.target.value as "retention_ratio" | "disabled")}
                        >
                          <option value="retention_ratio">retention_ratio</option>
                          <option value="disabled">disabled</option>
                        </select>
                      </Field>
                      <Field label="Retention ratio" hint="0.8 is the recommended baseline here">
                        <input
                          type="number"
                          step="0.05"
                          min="0.1"
                          max="1"
                          value={overrides.truncation_retention_ratio ?? 0.8}
                          onChange={(e) => set("truncation_retention_ratio", parseFloat(e.target.value) || 0.8)}
                        />
                      </Field>
                    </div>
                  </div>
                </div>

                <div className="space-y-5">
                  <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                    <h3 className="font-semibold text-ink">What is live right now</h3>
                    <p className="mt-1 text-sm text-ink/55">
                      These are the practical settings currently different from the system defaults.
                    </p>
                    <div className="mt-4 space-y-3">
                      {preview?.config_diff.map((item) => (
                        <div key={`${item.field}-${item.source}`} className="rounded-xl border border-stone/60 bg-ivory/60 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <span className="font-medium text-ink">{item.label}</span>
                            <span className="text-xs uppercase tracking-[0.18em] text-ink/35">{item.source}</span>
                          </div>
                          <p className="mt-2 text-sm text-ink/55">
                            {item.baseline} → <span className="font-medium text-ink">{item.effective}</span>
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                    <h3 className="font-semibold text-ink">What the simulator is for</h3>
                    <div className="mt-4 space-y-3 text-sm leading-6 text-ink/60">
                      <p>Use the text simulator to check if the prompt stays short, asks for the right missing info, and uses tools correctly.</p>
                      <p>Keep checks focused. Run one realistic caller message at a time so you can inspect behavior without burning unnecessary usage.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {tab === "simulate" && (
              <div className="mt-5 space-y-5">
                <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                    <h3 className="font-semibold text-ink">Text simulator</h3>
                    <p className="mt-1 text-sm text-ink/55">
                      Runs the same prompt and tool logic as live calls, but in text mode so you can iterate faster.
                    </p>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {preview?.scenarios.map((scenario) => (
                        <button
                          key={scenario.id}
                          onClick={() => setChatInput(scenario.message)}
                          className="rounded-full border border-stone/60 bg-ivory/70 px-3 py-1.5 text-xs font-medium text-ink/70 hover:bg-ivory hover:text-ink"
                        >
                          {scenario.label}
                        </button>
                      ))}
                    </div>

                    <div className="mt-4 flex gap-3">
                      <textarea
                        rows={4}
                        className="flex-1 rounded-xl border border-stone/60 bg-ivory/50 px-4 py-3 text-sm text-ink outline-none focus:border-gold"
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        placeholder="Type what the caller says..."
                      />
                      <div className="flex flex-col gap-2">
                        <button
                          onClick={() => simulate([...history, chatInput.trim()].filter(Boolean))}
                          disabled={simulating || !chatInput.trim()}
                          className="flex items-center gap-2 rounded-xl bg-ink px-4 py-3 text-sm font-semibold text-ivory disabled:opacity-50"
                        >
                          <Send size={14} /> {simulating ? "..." : "Send"}
                        </button>
                        <button
                          onClick={() => {
                            setHistory([]);
                            setSim(null);
                            setChatInput(preview?.scenarios[0]?.message ?? "");
                          }}
                          className="flex items-center gap-2 rounded-xl border border-stone px-4 py-3 text-sm text-ink/60"
                        >
                          <RotateCcw size={14} /> Reset
                        </button>
                      </div>
                    </div>
                </div>

                {sim && (
                  <div className="grid gap-5 lg:grid-cols-[1fr_0.45fr]">
                    <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
                      <h4 className="text-sm font-semibold text-ink/60">Conversation</h4>
                      <div className="mt-4 space-y-3">
                        {sim.transcript.map((turn, index) => (
                          <div
                            key={`${turn.role}-${index}`}
                            className={`rounded-xl px-4 py-3 text-sm leading-6 ${
                              turn.role === "assistant" ? "bg-ink text-ivory" : "bg-ivory text-ink"
                            }`}
                          >
                            <p className="text-[10px] font-semibold uppercase tracking-widest opacity-60">
                              {turn.role === "assistant" ? "Agent" : "Caller"}
                            </p>
                            <p className="mt-1.5">{turn.content}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <ToolPanel title="Tool calls" payload={sim.tool_events} />
                      <ToolPanel title="Usage" payload={sim.usage} />
                    </div>
                  </div>
                )}

              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ToolPanel({ title, payload }: { title: string; payload: unknown }) {
  if (!payload || (Array.isArray(payload) && payload.length === 0)) {
    return null;
  }
  return (
    <div className="rounded-2xl border border-stone/60 bg-white/70 p-5">
      <h4 className="text-sm font-semibold text-ink/60">{title}</h4>
      <pre className="mt-3 max-h-[320px] overflow-auto rounded-xl bg-night p-3 text-xs leading-5 text-ivory/85">
        {JSON.stringify(payload, null, 2)}
      </pre>
    </div>
  );
}

function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-3 rounded-xl border border-stone/60 bg-ivory/60 px-4 py-3 text-sm text-ink/70">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded"
      />
      {label}
    </label>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactElement;
}) {
  return (
    <label className="grid gap-1.5 text-sm">
      <span className="font-medium text-ink/70">{label}</span>
      {hint && <span className="text-xs text-ink/40">{hint}</span>}
      <div className="[&>*]:w-full [&>*]:rounded-xl [&>*]:border [&>*]:border-stone/60 [&>*]:bg-ivory/50 [&>*]:px-3 [&>*]:py-2.5 [&>*]:text-sm [&>*]:text-ink [&>*]:outline-none [&>*]:transition focus-within:[&>*]:border-gold">
        {children}
      </div>
    </label>
  );
}
