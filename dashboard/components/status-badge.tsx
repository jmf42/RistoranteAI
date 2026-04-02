import { ReactNode } from "react";

type StatusTone = "neutral" | "good" | "warn" | "danger" | "dark";

const toneClasses: Record<StatusTone, string> = {
  neutral: "border-stone/80 bg-white/80 text-ink/70",
  good: "border-olive/20 bg-olive/10 text-olive",
  warn: "border-gold/25 bg-gold/12 text-[#8c6a1f]",
  danger: "border-terracotta/20 bg-terracotta/10 text-terracotta",
  dark: "border-ink/15 bg-ink text-ivory",
};

export function StatusBadge({
  children,
  tone = "neutral",
  compact = false,
}: {
  children: ReactNode;
  tone?: StatusTone;
  compact?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border font-semibold uppercase ${
        compact
          ? "px-2.5 py-1 text-[10px] tracking-[0.18em]"
          : "px-3 py-1.5 text-[11px] tracking-[0.2em]"
      } ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
