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
    <section className="min-w-0 rounded-[2rem] border border-stone/80 bg-white/80 p-5 shadow-card backdrop-blur sm:p-6">
      <div className="mb-5 flex flex-col gap-4 2xl:flex-row 2xl:items-start 2xl:justify-between">
        <div className="min-w-0">
          {kicker ? (
            <p className="ui-kicker mb-2 text-xs font-semibold uppercase tracking-[0.24em] text-terracotta/70 sm:tracking-[0.32em]">
              {kicker}
            </p>
          ) : null}
          <h2 className="ui-display-title font-display text-2xl text-ink">{title}</h2>
        </div>
        {action ? <div className="w-full min-w-0 lg:w-auto lg:flex-none">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}
