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
    <section className="ui-soft-surface min-w-0 rounded-[2rem] p-5 sm:p-6">
      <div className="mb-4 flex flex-col gap-3 2xl:flex-row 2xl:items-start 2xl:justify-between">
        <div className="min-w-0">
          {kicker ? (
            <p className="ui-kicker mb-2 text-xs font-semibold uppercase text-terracotta/72 sm:text-[11px]">
              {kicker}
            </p>
          ) : null}
          <h2 className="ui-display-title font-display text-[1.85rem] text-ink sm:text-2xl">{title}</h2>
        </div>
        {action ? <div className="w-full min-w-0 lg:w-auto lg:flex-none">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}
