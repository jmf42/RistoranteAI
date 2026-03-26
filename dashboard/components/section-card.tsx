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
    <section className="min-w-0 rounded-[2rem] border border-stone/80 bg-white/80 p-6 shadow-card backdrop-blur">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div className="min-w-0">
          {kicker ? (
            <p className="ui-kicker mb-2 text-xs font-semibold uppercase tracking-[0.24em] text-terracotta/70 sm:tracking-[0.32em]">
              {kicker}
            </p>
          ) : null}
          <h2 className="ui-display-title font-display text-2xl text-ink">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
