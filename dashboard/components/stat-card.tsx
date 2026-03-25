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
      className={`rounded-[1.75rem] border border-white/70 bg-gradient-to-br ${colorMap[tone]} p-5 shadow-card`}
    >
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/55">{label}</p>
      <div className="mt-4 flex items-end justify-between gap-4">
        <div>
          <p className="font-display text-4xl text-ink">{value}</p>
          <p className="mt-2 text-sm text-ink/60">{detail}</p>
        </div>
        <div className="rounded-full border border-current/20 bg-white/75 px-3 py-1 text-sm font-semibold">
          {trendLabel(delta)}
        </div>
      </div>
    </article>
  );
}
