import { ReactNode } from "react";

type StatusTone = "neutral" | "good" | "warn" | "danger" | "dark";

const toneClasses: Record<StatusTone, string> = {
  neutral: "border-stone/70 bg-white/88 text-ink/68",
  good: "border-olive/20 bg-olive/10 text-olive",
  warn: "border-gold/25 bg-gold/12 text-[#8c6a1f]",
  danger: "border-terracotta/20 bg-terracotta/10 text-terracotta",
  dark: "border-white/10 bg-white/10 text-ivory",
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
          : "px-3 py-1.5 text-[11px] tracking-[0.18em]"
      } ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
