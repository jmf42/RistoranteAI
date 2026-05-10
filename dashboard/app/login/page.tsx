"use client";

import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-6 sm:px-5 sm:py-10">
      <div className="grid w-full max-w-5xl gap-4 lg:grid-cols-[1.05fr_0.95fr] lg:gap-6">
        <section className="hidden overflow-hidden rounded-[2.2rem] border border-white/55 bg-night p-8 text-ivory shadow-[0_26px_60px_-40px_rgba(16,12,10,0.55)] lg:block">
          <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.24em] text-gold/75 sm:tracking-[0.34em]">
            Zero chiamate perse, più tavoli pieni
          </p>
          <h1 className="ui-display-title mt-5 max-w-2xl font-display text-[3.7rem]">
            Un banco più calmo.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-8 text-ivory/70">
            Il receptionist AI risponde, prenota e aggiorna la sala senza aggiungere rumore alla giornata.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {[
              ["24/7", "Nessuna chiamata persa"],
              ["~90s", "Da squillo a conferma"],
              ["100%", "Visibilità coperti live"]
            ].map(([value, label]) => (
              <article key={label} className="rounded-[1.7rem] border border-white/10 bg-white/5 p-5">
                <p className="ui-display-stat-value font-display text-white">{value}</p>
                <p className="mt-3 text-sm text-ivory/68">{label}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-[1.8rem] border border-white/80 bg-white/94 p-5 shadow-[0_22px_50px_-36px_rgba(29,22,18,0.2)] sm:rounded-[2.2rem] sm:p-8 lg:p-10">
          <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.2em] text-terracotta/68">
            Ristorante AI
          </p>
          <h2 className="ui-display-title mt-3 font-display text-[2.5rem] text-ink sm:text-4xl">Accedi</h2>
          <p className="mt-3 max-w-md text-sm leading-7 text-ink/62">
            Entra nella postazione operativa del ristorante.
          </p>
          <div className="mt-7">
            <LoginForm />
          </div>
          <div className="mt-6 grid gap-2 text-sm text-ink/56 lg:hidden">
            <p>Gestisci prenotazioni, chiamate e coperti da un’unica vista.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
