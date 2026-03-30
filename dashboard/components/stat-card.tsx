import { trendLabel } from "@/lib/format";

export function StatCard({
  label,
  value,
  detail,
  delta,
  tone
}: {
  label: string;
  value: string;
  detail: string;
  delta: number;
  tone: "terracotta" | "olive" | "gold";
}) {
  const colorMap = {
    terracotta: "from-terracotta/15 to-terracotta/5 text-terracotta",
    olive: "from-olive/15 to-olive/5 text-olive",
    gold: "from-gold/20 to-gold/8 text-gold"
  };

  return (
    <article
      className={`min-w-0 rounded-[1.75rem] border border-white/70 bg-gradient-to-br ${colorMap[tone]} p-4 shadow-card sm:p-5`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="ui-kicker max-w-[11rem] text-[11px] font-semibold uppercase tracking-[0.18em] text-ink/55 sm:max-w-none sm:text-xs sm:tracking-[0.24em]">
          {label}
        </p>
        <div className="rounded-full border border-current/20 bg-white/75 px-2.5 py-1 text-xs font-semibold sm:px-3 sm:text-sm">
          {trendLabel(delta)}
        </div>
      </div>
      <div className="mt-4 min-w-0">
        <p className="ui-display-stat-value font-display text-ink">{value}</p>
        <p className="mt-2 max-w-[17rem] text-sm leading-6 text-ink/60">{detail}</p>
      </div>
    </article>
  );
}
