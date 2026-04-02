"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  CalendarClock,
  CircleAlert,
  CalendarDays,
  CookingPot,
  Menu,
  PhoneCall,
  PhoneForwarded,
  RadioTower,
  Settings,
  ShieldCheck,
  X
} from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const {
    user,
    loading,
    restaurant,
    restaurants,
    activeRestaurantId,
    error: workspaceError,
    setActiveRestaurantId,
    logout
  } = useWorkspace();

  const visibleNavigation = useMemo(
    () => navigation.filter((item) => !item.operatorOnly || user?.role === "operator"),
    [user?.role]
  );

  const mobilePrimaryNavigation = useMemo(
    () =>
      visibleNavigation.filter((item) =>
        ["/", "/bookings", "/capacity", "/calls"].includes(item.href)
      ),
    [visibleNavigation]
  );

  const readinessItems = useMemo(() => {
    if (!restaurant) {
      return [];
    }

    return [
      {
        label: restaurant.is_active ? "Ristorante attivo" : "Ristorante in pausa",
        tone: restaurant.is_active ? "good" : "warn",
        icon: <CalendarClock size={16} />
      },
      {
        label: restaurant.twilio_phone && restaurant.elevenlabs_agent_id ? "Linea AI pronta" : "Linea AI da collegare",
        tone: restaurant.twilio_phone && restaurant.elevenlabs_agent_id ? "good" : "warn",
        icon: <RadioTower size={16} />
      },
      {
        label: restaurant.escalation_phone ? "Escalation umana pronta" : "Manca numero di backup",
        tone: restaurant.escalation_phone ? "neutral" : "danger",
        icon: <PhoneForwarded size={16} />
      }
    ] as const;
  }, [restaurant]);

  const headerReadinessItems = useMemo(() => {
    if (!restaurant) {
      return [];
    }

    const issues = [];
    if (!restaurant.is_active) {
      issues.push({ label: "Ristorante in pausa", tone: "warn" as const });
    }
    if (!(restaurant.twilio_phone && restaurant.elevenlabs_agent_id)) {
      issues.push({ label: "Linea AI da collegare", tone: "warn" as const });
    }
    if (!restaurant.escalation_phone) {
      issues.push({ label: "Manca backup umano", tone: "danger" as const });
    }

    return issues.length
      ? issues
      : [{ label: "Postazione pronta", tone: "good" as const }];
  }, [restaurant]);

  const todayLabel = useMemo(
    () =>
      new Intl.DateTimeFormat("it-IT", {
        weekday: "long",
        day: "2-digit",
        month: "long"
      }).format(new Date()),
    []
  );

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileMenuOpen]);

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
      <div className="lg:hidden sticky top-0 z-40 px-3 pt-3">
        <div className="rounded-[1.6rem] border border-white/75 bg-white/78 px-4 py-3 shadow-card backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="ui-kicker text-[10px] font-semibold uppercase tracking-[0.22em] text-terracotta/70">
                Ristorante AI
              </p>
              <p className="truncate text-base font-semibold text-ink">{title}</p>
              <p className="truncate text-xs text-ink/58">{restaurant?.name ?? user.full_name}</p>
            </div>
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-stone/80 bg-ivory/80 text-ink transition hover:border-gold"
              aria-label="Apri menu"
            >
              <Menu size={18} />
            </button>
          </div>
        </div>
      </div>

      {mobileMenuOpen ? (
        <div className="lg:hidden fixed inset-0 z-50 overflow-hidden" aria-hidden={false}>
          <button
            type="button"
            aria-label="Chiudi menu"
            onClick={() => setMobileMenuOpen(false)}
            className="absolute inset-0 bg-night/45 backdrop-blur-[2px]"
          />
          <aside className="fixed inset-y-0 right-0 w-[min(90vw,24rem)] overflow-y-auto border-l border-white/10 bg-night px-5 py-5 text-ivory shadow-[0_24px_90px_rgba(16,12,10,0.55)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.24em] text-gold/80">
                  Italian hospitality OS
                </p>
                <h1 className="ui-display-title mt-3 font-display text-3xl">Ristorante AI</h1>
                <p className="mt-2 text-sm text-ivory/68">
                  Postazione operativa pensata per il banco, anche da telefono.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/5 text-ivory/82"
                aria-label="Chiudi menu"
              >
                <X size={18} />
              </button>
            </div>

            {user.role === "operator" && restaurants.length ? (
              <label className="mt-7 flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.24em] text-ivory/45">
                Ristorante attivo
                <select
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium normal-case tracking-normal text-white outline-none transition focus:border-gold"
                  value={activeRestaurantId ?? ""}
                  onChange={(event) => {
                    setActiveRestaurantId(event.target.value);
                    setMobileMenuOpen(false);
                  }}
                >
                  {restaurants.map((item) => (
                    <option key={item.id} value={item.id} className="text-ink">
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}

            <nav className="mt-7 space-y-2">
              {visibleNavigation.map((item) => {
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

            <div className="mt-7 rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-gold/72">Workspace</p>
              <p className="mt-3 font-medium text-white">
                {restaurant ? restaurant.name : "Nessun ristorante attivo"}
              </p>
              <p className="mt-2 text-sm leading-6 text-ivory/65">
                {restaurant?.address ?? "Seleziona un tenant per vedere i dettagli operativi."}
              </p>
              {readinessItems.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {readinessItems.map((item) => (
                    <span
                      key={item.label}
                      className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-ivory/75"
                    >
                      {item.icon}
                      {item.label}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="mt-4 rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-gold/72">Profilo</p>
              <p className="mt-3 font-medium text-white">{user.full_name}</p>
              <p className="text-sm text-ivory/65">{user.email}</p>
              <button
                type="button"
                onClick={async () => {
                  await logout();
                  router.replace("/login");
                }}
                className="mt-4 rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-ivory/85 transition hover:bg-white/10"
              >
                Esci
              </button>
            </div>
          </aside>
        </div>
      ) : null}

      <div className="mx-auto flex max-w-[1500px] flex-col gap-5 px-3 pb-32 pt-3 lg:flex-row lg:gap-6 lg:px-6 lg:py-5 lg:pb-5">
        <aside className="hidden lg:block lg:sticky lg:top-5 lg:h-[calc(100vh-2.5rem)] lg:w-[280px] lg:flex-none">
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
              {visibleNavigation.map((item) => {
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
            {readinessItems.length ? (
              <div className="mt-8 rounded-[1.7rem] border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.28em] text-gold/70">Stato ristorante</p>
                <div className="mt-4 space-y-2">
                  {readinessItems.map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center gap-3 rounded-[1rem] border border-white/8 bg-white/5 px-3 py-3 text-sm text-ivory/78"
                    >
                      <div className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-gold/75">
                        {item.icon}
                      </div>
                      <span>{item.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
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
          <div className="rounded-[1.85rem] border border-white/75 bg-white/72 p-4 shadow-card backdrop-blur sm:p-5 lg:rounded-[2.25rem] lg:p-7">
            <header className="mb-5 flex flex-col gap-4 border-b border-stone/80 pb-5 xl:mb-6 xl:flex-row xl:items-end xl:justify-between xl:gap-5 xl:pb-6">
              <div>
                <p className="ui-kicker text-xs font-semibold uppercase tracking-[0.24em] text-terracotta/70 sm:tracking-[0.32em]">
                  {restaurant ? restaurant.name : "Workspace"}
                </p>
                <h2 className="ui-display-title mt-3 font-display text-3xl text-ink sm:text-4xl">
                  {title}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/65">{subtitle}</p>
                <div className="mt-4 flex flex-wrap gap-2.5">
                  <StatusBadge tone="neutral">{todayLabel}</StatusBadge>
                  {headerReadinessItems.map((item) => (
                    <StatusBadge key={item.label} tone={item.tone}>
                      {item.label}
                    </StatusBadge>
                  ))}
                </div>
              </div>
              <div className="flex w-full flex-col gap-2.5 sm:flex-row sm:flex-wrap sm:items-center xl:w-auto xl:justify-end">
                {user.role === "operator" && restaurants.length ? (
                  <label className="flex w-full flex-col gap-2 text-xs font-semibold uppercase tracking-[0.24em] text-ink/45 sm:min-w-[240px] sm:flex-1 xl:flex-none">
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
                <div className="min-w-0 rounded-[1.25rem] border border-stone bg-ivory/70 px-4 py-3 text-sm leading-6 text-ink/65 sm:flex-1 xl:max-w-[320px] xl:flex-none">
                  {restaurant ? restaurant.address : "Nessun ristorante attivo"}
                </div>
                {actions ? (
                  <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:flex-wrap sm:justify-end">
                    {actions}
                  </div>
                ) : null}
              </div>
            </header>
            {workspaceError ? (
              <div className="mb-5 flex items-start gap-3 rounded-[1.5rem] border border-terracotta/20 bg-terracotta/8 px-4 py-4 text-sm text-terracotta xl:mb-6">
                <CircleAlert size={18} className="mt-0.5 shrink-0" />
                <div>
                  <p className="font-semibold">Attenzione workspace</p>
                  <p className="mt-1 text-terracotta/80">{workspaceError}</p>
                </div>
              </div>
            ) : null}
            {children}
          </div>
        </main>
      </div>

      <div className="lg:hidden fixed inset-x-0 bottom-0 z-40 px-3 pb-[calc(0.8rem+env(safe-area-inset-bottom))]">
        <div className="grid grid-cols-5 gap-1 rounded-[1.55rem] border border-white/10 bg-night/92 p-1.5 shadow-[0_24px_80px_rgba(16,12,10,0.4)] backdrop-blur">
          {mobilePrimaryNavigation.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex min-w-0 flex-col items-center gap-1 rounded-[1rem] px-1.5 py-2 text-[10px] font-semibold transition ${
                  active
                    ? "bg-ivory text-ink shadow-[0_10px_24px_rgba(255,248,238,0.18)]"
                    : "text-ivory/60"
                }`}
              >
                <Icon size={18} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            className="flex min-w-0 flex-col items-center gap-1 rounded-[1rem] px-1.5 py-2 text-[10px] font-semibold text-ivory/60 transition"
          >
            <Menu size={18} />
            <span className="truncate">Menu</span>
          </button>
        </div>
      </div>
    </div>
  );
}
