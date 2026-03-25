"use client";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-ivory px-4 text-center">
      <h2 className="text-xl font-semibold text-ink">Qualcosa è andato storto</h2>
      <p className="max-w-md text-sm text-ink/60">
        {error.message || "Si è verificato un errore imprevisto. Riprova."}
      </p>
      <button
        onClick={reset}
        className="rounded-2xl bg-ink px-6 py-3 text-sm font-semibold uppercase tracking-[0.26em] text-ivory"
      >
        Riprova
      </button>
    </div>
  );
}
