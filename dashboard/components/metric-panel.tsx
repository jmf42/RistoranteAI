import { ReactNode } from "react";

import { StatusBadge } from "@/components/status-badge";

type MetricTone = "terracotta" | "olive" | "gold" | "ink";

const toneClasses: Record<MetricTone, string> = {
  terracotta: "border-terracotta/15 bg-gradient-to-br from-terracotta/12 via-white to-white",
  olive: "border-olive/15 bg-gradient-to-br from-olive/12 via-white to-white",
  gold: "border-gold/15 bg-gradient-to-br from-gold/14 via-white to-white",
  ink: "border-ink/10 bg-ink text-ivory",
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
    <article className={`min-w-0 rounded-[1.6rem] border p-4 shadow-card sm:p-5 ${toneClasses[tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {eyebrow ? (
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${dark ? "text-gold/75" : "text-terracotta/70"}`}>
              {eyebrow}
            </p>
          ) : null}
          <p className={`mt-2 text-sm font-semibold uppercase tracking-[0.18em] ${dark ? "text-ivory/60" : "text-ink/55"}`}>
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
            <div className={`inline-flex h-10 w-10 items-center justify-center rounded-full ${dark ? "bg-white/10 text-gold/80" : "bg-white/85 text-ink/65"}`}>
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
