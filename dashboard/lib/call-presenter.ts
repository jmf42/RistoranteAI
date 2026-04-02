import { ActivityItem, CallLog, CallOutcome, CallStatus } from "@/lib/types";

const outcomeLabels: Record<CallOutcome, string> = {
  booking_created: "Prenotazione creata",
  booking_modified: "Prenotazione aggiornata",
  booking_cancelled: "Prenotazione cancellata",
  info_provided: "Informazioni gestite",
  escalated: "Passata al ristorante",
  abandoned: "Chiamata interrotta",
  tool_error: "Errore tecnico",
};

const statusLabels: Record<CallStatus, string> = {
  successful: "Completata",
  failed: "Fallita",
  unknown: "Da verificare",
};

export function formatCallOutcomeLabel(outcome: CallOutcome): string {
  return outcomeLabels[outcome] ?? outcome.replaceAll("_", " ");
}

export function formatCallStatusLabel(status: CallStatus): string {
  return statusLabels[status] ?? "Da verificare";
}

export function getCallOperationalStatusLabel(
  call: Pick<CallLog, "outcome" | "call_status" | "summary" | "booking_id">,
): string {
  const presentation = getCallPresentation(call);
  if (presentation.needsAttention) {
    return "Da seguire";
  }
  if (call.call_status === "successful") {
    return "Completata";
  }
  if (
    call.outcome === "booking_created" ||
    call.outcome === "booking_modified" ||
    call.outcome === "booking_cancelled" ||
    call.outcome === "info_provided" ||
    call.outcome === "escalated"
  ) {
    return "Gestita";
  }
  return formatCallStatusLabel(call.call_status);
}

function detectConfirmCall(summary: string): boolean {
  const lowered = summary.toLowerCase();
  return (
    lowered.includes("confirm a restaurant reservation") ||
    lowered.includes("confirm reservation") ||
    lowered.includes("prenotazione esistente") ||
    lowered.includes("found a confirmed booking")
  );
}

function detectGreetingOnly(summary: string): boolean {
  const lowered = summary.toLowerCase();
  return (
    lowered.includes("greeting") ||
    lowered.includes("began with greetings") ||
    lowered.includes("initiated the conversation with a greeting")
  );
}

function detectTechFailure(summary: string): boolean {
  const lowered = summary.toLowerCase();
  return (
    lowered.includes("tool call failed") ||
    lowered.includes("technical error") ||
    lowered.includes("401 unauthorized") ||
    lowered.includes("problem") ||
    lowered.includes("retry")
  );
}

function detectSummaryMissing(summary: string): boolean {
  const lowered = summary.toLowerCase();
  return lowered === "chiamata registrata" || lowered.includes("summary couldn't be generated");
}

export function getCallPresentation(call: Pick<CallLog, "outcome" | "call_status" | "summary" | "booking_id">) {
  const summary = call.summary.trim();
  const needsAttention =
    call.call_status === "failed" ||
    call.outcome === "tool_error" ||
    call.outcome === "abandoned" ||
    detectTechFailure(summary);

  if (call.outcome === "booking_created") {
    return {
      label: formatCallOutcomeLabel(call.outcome),
      headline: "Prenotazione confermata",
      preview: "L’agente ha chiuso la prenotazione con successo.",
      needsAttention: false,
      nextStep: "Nessuna azione necessaria.",
    };
  }

  if (call.outcome === "booking_modified") {
    return {
      label: formatCallOutcomeLabel(call.outcome),
      headline: "Prenotazione aggiornata",
      preview: "Il cliente ha modificato una prenotazione esistente.",
      needsAttention: false,
      nextStep: "Verifica solo se ci sono richieste speciali.",
    };
  }

  if (call.outcome === "booking_cancelled") {
    return {
      label: formatCallOutcomeLabel(call.outcome),
      headline: "Prenotazione cancellata",
      preview: "La chiamata si è chiusa con una cancellazione confermata.",
      needsAttention: false,
      nextStep: "Nessuna azione necessaria.",
    };
  }

  if (detectConfirmCall(summary)) {
    return {
      label: "Conferma prenotazione",
      headline: "Prenotazione verificata",
      preview: "Il cliente ha richiamato per controllare una prenotazione già presente.",
      needsAttention: false,
      nextStep: "Nessuna azione necessaria, salvo richieste successive del cliente.",
    };
  }

  if (needsAttention) {
    return {
      label: "Da seguire",
      headline: "Serve un controllo umano",
      preview: "L’agente non ha chiuso la richiesta. Conviene verificare o richiamare il cliente.",
      needsAttention: true,
      nextStep: "Apri il dettaglio e valuta se richiamare il cliente o verificare la disponibilità a mano.",
    };
  }

  if (detectGreetingOnly(summary)) {
    return {
      label: "Contatto breve",
      headline: "Chiamata chiusa presto",
      preview: "La conversazione si è fermata poco dopo il saluto iniziale.",
      needsAttention: false,
      nextStep: "Nessuna urgenza, ma monitora se succede spesso.",
    };
  }

  if (detectSummaryMissing(summary)) {
    return {
      label: "Dettaglio limitato",
      headline: "Informazioni non complete",
      preview: "Questa chiamata è stata registrata, ma il sistema non ha prodotto un riassunto utile.",
      needsAttention: false,
      nextStep: "Apri il dettaglio solo se ti serve ricostruire il contesto.",
    };
  }

  return {
    label: formatCallOutcomeLabel(call.outcome),
    headline: "Richiesta gestita",
    preview: "La chiamata è stata gestita senza creare o modificare una prenotazione.",
    needsAttention: false,
    nextStep: "Apri il dettaglio solo se vuoi leggere il riassunto completo.",
  };
}

export function isLowSignalCall(call: Pick<CallLog, "outcome" | "call_status" | "summary" | "duration_seconds">) {
  const summary = call.summary.trim();
  if (call.outcome === "booking_created" || call.outcome === "booking_modified" || call.outcome === "booking_cancelled") {
    return false;
  }
  if (call.call_status === "failed" || call.outcome === "tool_error" || call.outcome === "abandoned") {
    return false;
  }
  if (detectConfirmCall(summary)) {
    return false;
  }
  if (detectSummaryMissing(summary) && call.duration_seconds <= 5) {
    return true;
  }
  if (detectGreetingOnly(summary) && call.duration_seconds <= 20) {
    return true;
  }
  return false;
}

export function isFollowUpCall(call: Pick<CallLog, "outcome" | "call_status" | "summary">) {
  const summary = call.summary.trim();
  return (
    call.call_status === "failed" ||
    call.outcome === "tool_error" ||
    call.outcome === "abandoned" ||
    detectTechFailure(summary)
  );
}

function activityOutcomeFromTitle(title: string): CallOutcome {
  const lowered = title.toLowerCase();
  if (lowered.includes("booking created")) return "booking_created";
  if (lowered.includes("booking modified")) return "booking_modified";
  if (lowered.includes("booking cancelled")) return "booking_cancelled";
  if (lowered.includes("escalated")) return "escalated";
  if (lowered.includes("abandoned")) return "abandoned";
  if (lowered.includes("tool error")) return "tool_error";
  return "info_provided";
}

export function getActivityPresentation(item: ActivityItem) {
  if (item.kind !== "call") {
    return {
      eyebrow: "Prenotazione",
      headline: item.title,
      preview: item.detail,
      needsAttention: false,
    };
  }

  const callView = getCallPresentation({
    outcome: activityOutcomeFromTitle(item.title),
    call_status: item.detail.toLowerCase().includes("technical error") ? "failed" : "unknown",
    summary: item.detail,
    booking_id: null,
  });

  return {
    eyebrow: callView.label,
    headline: callView.headline,
    preview: callView.preview,
    needsAttention: callView.needsAttention,
  };
}
