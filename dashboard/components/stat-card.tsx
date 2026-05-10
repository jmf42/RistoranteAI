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
    terracotta: "from-terracotta/12 via-white/85 to-[#f4e6e0] text-terracotta",
    olive: "from-olive/12 via-white/85 to-[#eef1ec] text-olive",
    gold: "from-gold/16 via-white/85 to-[#f4eddd] text-gold"
  };

  return (
    <article
      className={`ui-soft-surface min-w-0 rounded-[1.75rem] bg-gradient-to-br ${colorMap[tone]} p-4 sm:p-5`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="ui-kicker max-w-[11rem] text-[11px] font-semibold uppercase text-ink/52 sm:max-w-none sm:text-xs">
          {label}
        </p>
        <div className="rounded-full border border-current/18 bg-white/78 px-2.5 py-1 text-xs font-semibold shadow-[0_10px_24px_-20px_rgba(28,22,18,0.4)] sm:px-3 sm:text-sm">
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
