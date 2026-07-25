export function normalizeApiUrl(value: string | undefined) {
  return value?.trim().replace(/\/+$/, "") ?? "";
}

export const API_URL =
  typeof window === "undefined"
    ? normalizeApiUrl(process.env.INTERNAL_API_URL) || "http://localhost:8000"
    : normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL);

export class PortalApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

function cookie(name: string) {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`))
    ?.split("=")
    .slice(1)
    .join("=");
}

export async function api<T>(
  path: string,
  init: Omit<RequestInit, "body"> & { body?: BodyInit | object | null } = {},
): Promise<T> {
  const method = init.method?.toUpperCase() ?? "GET";
  const headers = new Headers(init.headers);
  let body = init.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = cookie("utag_csrf");
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      body: body as BodyInit | null | undefined,
      headers,
      credentials: "include",
    });
  } catch {
    throw new PortalApiError(
      0,
      "service_unavailable",
      "The portal service is temporarily unavailable. Please try again.",
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = data?.error;
    throw new PortalApiError(
      response.status,
      error?.code ?? "request_failed",
      error?.message ?? "The request could not be completed",
      error?.details,
    );
  }
  return data as T;
}

export async function publicApi<T>(
  path: string,
  fallback: T,
  options: { revalidate?: number | false } = {},
): Promise<T> {
  try {
    const response = await fetch(
      `${API_URL}${path}`,
      options.revalidate === false
        ? { cache: "no-store" }
        : { next: { revalidate: options.revalidate ?? 30 } },
    );
    if (!response.ok) return fallback;
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}
