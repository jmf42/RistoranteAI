import { ReactNode } from "react";

import { StatusBadge } from "@/components/status-badge";

type MetricTone = "terracotta" | "olive" | "gold" | "ink";

const toneClasses: Record<MetricTone, string> = {
  terracotta: "ui-soft-surface bg-[linear-gradient(180deg,rgba(255,251,248,0.96),rgba(248,239,234,0.92))]",
  olive: "ui-soft-surface bg-[linear-gradient(180deg,rgba(255,252,248,0.96),rgba(239,243,237,0.92))]",
  gold: "ui-soft-surface bg-[linear-gradient(180deg,rgba(255,252,248,0.96),rgba(246,239,222,0.9))]",
  ink: "ui-night-surface text-ivory",
};

export function MetricPanel({
  label,
  value,
  detail,
  eyebrow,
  tone = "gold",
  badge,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  eyebrow?: string;
  tone?: MetricTone;
  badge?: { label: string; tone?: "neutral" | "good" | "warn" | "danger" | "dark" };
  icon?: ReactNode;
}) {
  const dark = tone === "ink";
  return (
    <article className={`min-w-0 rounded-[1.6rem] p-4 sm:p-5 ${toneClasses[tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {eyebrow ? (
            <p className={`ui-kicker text-[11px] font-semibold uppercase ${dark ? "text-gold/75" : "text-terracotta/70"}`}>
              {eyebrow}
            </p>
          ) : null}
          <p className={`mt-2 text-sm font-semibold uppercase tracking-[0.14em] ${dark ? "text-ivory/60" : "text-ink/55"}`}>
            {label}
          </p>
          {badge ? (
            <div className="mt-3">
              <StatusBadge tone={badge.tone ?? "neutral"}>{badge.label}</StatusBadge>
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {icon ? (
            <div className={`inline-flex h-10 w-10 items-center justify-center rounded-full ${dark ? "bg-white/10 text-gold/80" : "bg-white text-ink/58"}`}>
              {icon}
            </div>
          ) : null}
        </div>
      </div>
      <p className={`ui-display-stat-value mt-5 font-display ${dark ? "text-white" : "text-ink"}`}>{value}</p>
      <p className={`mt-3 max-w-[20rem] text-sm leading-6 ${dark ? "text-ivory/70" : "text-ink/60"}`}>{detail}</p>
    </article>
  );
}
