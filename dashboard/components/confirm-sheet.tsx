"use client";

import { ReactNode } from "react";

export function ConfirmSheet({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = "Annulla",
  tone = "danger",
  busy = false,
  onConfirm,
  onCancel,
  children,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "danger" | "neutral";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-night/40 px-3 py-3 backdrop-blur-[2px] sm:items-center sm:px-6">
      <button
        type="button"
        aria-label="Chiudi finestra di conferma"
        className="absolute inset-0"
        onClick={onCancel}
      />
      <div className="ui-shell-surface relative z-[71] w-full max-w-lg rounded-[2rem] p-5 sm:p-6">
        <p className="ui-kicker text-[11px] font-semibold uppercase text-terracotta/72">Conferma azione</p>
        <h3 className="mt-3 font-display text-3xl text-ink">{title}</h3>
        <p className="mt-3 text-sm leading-7 text-ink/65">{description}</p>
        {children ? <div className="mt-4">{children}</div> : null}
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-stone px-4 py-3 text-sm font-semibold text-ink/70 transition hover:border-gold hover:text-ink"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className={`rounded-full px-4 py-3 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60 ${
              tone === "danger" ? "bg-terracotta hover:bg-terracotta/90" : "bg-ink hover:bg-night"
            }`}
          >
            {busy ? "Attendo..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
