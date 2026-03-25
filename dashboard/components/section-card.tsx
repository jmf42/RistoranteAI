import { ReactNode } from "react";

export function SectionCard({
  title,
  kicker,
  children,
  action
}: {
  title: string;
  kicker?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="rounded-[2rem] border border-stone/80 bg-white/80 p-6 shadow-card backdrop-blur">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          {kicker ? (
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.32em] text-terracotta/70">
              {kicker}
            </p>
          ) : null}
          <h2 className="font-display text-2xl text-ink">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
