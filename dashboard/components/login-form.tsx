"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch, ApiError } from "@/lib/api";
import { useWorkspace } from "@/components/workspace-provider";

export function LoginForm() {
  const router = useRouter();
  const { user, refreshWorkspace } = useWorkspace();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      router.replace("/");
    }
  }, [router, user]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      await refreshWorkspace();
      router.replace("/");
    } catch (caught) {
      const message =
        caught instanceof ApiError ? caught.message : "Accesso non riuscito. Riprova.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label className="text-xs font-semibold uppercase tracking-[0.22em] text-ink/55" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          required
          autoComplete="email"
          className="w-full rounded-[1.1rem] border border-stone/85 bg-white px-4 py-3 text-ink outline-none transition focus:border-gold"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <label
          className="text-xs font-semibold uppercase tracking-[0.22em] text-ink/55"
          htmlFor="password"
        >
          Password
        </label>
        <input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          className="w-full rounded-[1.1rem] border border-stone/85 bg-white px-4 py-3 text-ink outline-none transition focus:border-gold"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      {error ? <p className="text-sm font-medium text-terracotta">{error}</p> : null}
      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-[1.1rem] bg-ink px-5 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-ivory transition hover:bg-night disabled:opacity-60"
      >
        {submitting ? "Accesso..." : "Entra nella dashboard"}
      </button>
    </form>
  );
}
