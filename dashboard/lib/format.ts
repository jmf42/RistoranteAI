export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    weekday: "short",
    day: "2-digit",
    month: "short"
  }).format(new Date(value));
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function trendLabel(value: number): string {
  if (value === 0) {
    return "in linea";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

export function weekdayLabel(index: number): string {
  return ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"][index] ?? "";
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function toLocalDateInputValue(date: Date = new Date()): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function shiftLocalDateInputValue(value: string, days: number): string {
  const [year, month, day] = value.split("-").map(Number);
  const next = new Date(year, (month ?? 1) - 1, day ?? 1);
  next.setDate(next.getDate() + days);
  return toLocalDateInputValue(next);
}
