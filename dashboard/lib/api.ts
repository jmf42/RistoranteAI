const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
const API_TIMEOUT_MS = 15000;

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function buildUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
}

function createTimeoutSignal(timeoutMs: number): {
  signal: AbortSignal;
  clear: () => void;
} {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort("timeout"), timeoutMs);
  return {
    signal: controller.signal,
    clear: () => window.clearTimeout(timeoutId),
  };
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const { signal, clear } = createTimeoutSignal(API_TIMEOUT_MS);
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildUrl(path), {
    ...init,
    credentials: "include",
    headers,
    cache: "no-store",
    signal,
  }).finally(clear);

  if (response.status === 204) {
    return undefined as T;
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : typeof payload?.message === "string"
          ? payload.message
          : `Request failed (${response.status})`;
    throw new ApiError(message, response.status, payload);
  }

  if (payload === null) {
    throw new ApiError("Invalid response from server", response.status, null);
  }

  return payload as T;
}

export async function apiDownload(path: string, filename: string): Promise<void> {
  const { signal, clear } = createTimeoutSignal(API_TIMEOUT_MS);
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    cache: "no-store",
    signal,
  }).finally(clear);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : "Download failed";
    throw new ApiError(message, response.status, payload);
  }
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

export function queryString(params: Record<string, string | number | undefined | null>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value));
    }
  });
  const serialized = searchParams.toString();
  return serialized ? `?${serialized}` : "";
}

export { API_BASE_URL, API_TIMEOUT_MS };
