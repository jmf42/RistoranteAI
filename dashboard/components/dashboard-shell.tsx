"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";
import {
  BarChart3,
  CalendarDays,
  CookingPot,
  PhoneCall,
  Settings,
  ShieldCheck
} from "lucide-react";

import { useWorkspace } from "@/components/workspace-provider";

const navigation = [
  { href: "/", label: "Panoramica", icon: BarChart3 },
  { href: "/bookings", label: "Prenotazioni", icon: CalendarDays },
  { href: "/capacity", label: "Capienza", icon: CookingPot },
  { href: "/calls", label: "Chiamate", icon: PhoneCall },
  { href: "/settings", label: "Impostazioni", icon: Settings },
  { href: "/admin", label: "Admin", icon: ShieldCheck, operatorOnly: true }
];

export function DashboardShell({
  title,
  subtitle,
  children,
  actions
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const {
    user,
    loading,
    restaurant,
    restaurants,
    activeRestaurantId,
    setActiveRestaurantId,
    logout
  } = useWorkspace();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-grain px-6">
        <div className="rounded-[2rem] border border-white/70 bg-white/75 px-8 py-10 text-center shadow-card">
          <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.24em] text-terracotta/70 sm:tracking-[0.32em]">
            Ristorante AI
          </p>
          <p className="ui-display-title mt-4 font-display text-3xl text-ink">Carico la postazione...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-grain text-ink">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-6 px-4 py-5 lg:flex-row lg:px-6">
        <aside className="lg:sticky lg:top-5 lg:h-[calc(100vh-2.5rem)] lg:w-[280px] lg:flex-none">
          <div className="flex h-full flex-col rounded-[2rem] border border-white/70 bg-night px-6 py-7 text-ivory shadow-card">
            <div>
              <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.24em] text-gold/80 sm:tracking-[0.34em]">
                Italian hospitality OS
              </p>
              <h1 className="ui-display-title mt-4 font-display text-4xl">Ristorante AI</h1>
              <p className="mt-3 text-sm text-ivory/70">
                Più tavoli pieni, meno telefonate al banco. Tutto in una sola cabina di regia.
              </p>
            </div>
            <nav className="mt-10 space-y-2">
              {navigation
                .filter((item) => !item.operatorOnly || user.role === "operator")
                .map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm transition ${
                        active
                          ? "bg-white/10 text-white"
                          : "text-ivory/72 hover:bg-white/6 hover:text-white"
                      }`}
                    >
                      <Icon size={18} />
                      {item.label}
                    </Link>
                  );
                })}
            </nav>
            <div className="mt-auto rounded-[1.7rem] border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.28em] text-gold/70">Profilo</p>
              <p className="mt-3 font-medium text-white">{user.full_name}</p>
              <p className="text-sm text-ivory/65">{user.email}</p>
              <button
                type="button"
                onClick={async () => {
                  await logout();
                  router.replace("/login");
                }}
                className="mt-4 rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-ivory/85 transition hover:bg-white/10"
              >
                Esci
              </button>
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <div className="rounded-[2.25rem] border border-white/75 bg-white/70 p-5 shadow-card backdrop-blur lg:p-7">
            <header className="mb-8 flex flex-col gap-5 border-b border-stone/80 pb-6 lg:flex-row lg:items-end lg:justify-between">
              <div>
              <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.24em] text-terracotta/70 sm:tracking-[0.32em]">
                {restaurant ? restaurant.name : "Workspace"}
              </p>
              <h2 className="ui-display-title mt-3 font-display text-4xl text-ink">{title}</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/65">{subtitle}</p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                {user.role === "operator" && restaurants.length ? (
                  <label className="flex min-w-[240px] flex-col gap-2 text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">
                    Ristorante attivo
                    <select
                      className="rounded-2xl border border-stone bg-ivory/80 px-4 py-3 text-sm font-medium normal-case tracking-normal text-ink outline-none transition focus:border-gold"
                      value={activeRestaurantId ?? ""}
                      onChange={(event) => setActiveRestaurantId(event.target.value)}
                    >
                      {restaurants.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                <div className="rounded-2xl border border-stone bg-ivory/70 px-4 py-3 text-sm text-ink/65">
                  {restaurant ? restaurant.address : "Nessun ristorante attivo"}
                </div>
                {actions}
              </div>
            </header>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
