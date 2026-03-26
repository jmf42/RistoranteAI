"use client";

import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-5 py-10">
      <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="overflow-hidden rounded-[2.5rem] border border-white/70 bg-night p-8 text-ivory shadow-card lg:p-12">
          <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.24em] text-gold/75 sm:tracking-[0.34em]">
            Zero chiamate perse, più tavoli pieni
          </p>
          <h1 className="ui-display-title mt-5 max-w-2xl font-display text-5xl lg:text-6xl">
            Ogni chiamata diventa un tavolo. Anche alle 2 di notte.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-8 text-ivory/70">
            Il tuo receptionist AI risponde, prenota e gestisce i coperti — così il team si concentra
            sulla sala e la cucina, non sul telefono che squilla.
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
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

        <section className="rounded-[2.5rem] border border-white/75 bg-white/78 p-8 shadow-card backdrop-blur lg:p-10">
          <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.24em] text-terracotta/70 sm:tracking-[0.3em]">
            Dashboard ristorante
          </p>
          <h2 className="ui-display-title mt-4 font-display text-4xl text-ink">Accedi</h2>
          <p className="mt-3 text-sm leading-7 text-ink/65">
            Inserisci le tue credenziali per accedere alla dashboard operativa del ristorante.
          </p>
          <div className="mt-8">
            <LoginForm />
          </div>
        </section>
      </div>
    </div>
  );
}
