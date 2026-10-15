// Same-origin API client. Commands carry an anti-forgery token and an idempotency key that stays the same
// across retries of one user intent, so a reconnect never duplicates work.

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail: Record<string, unknown> = {},
  ) {
    super(message);
  }
  get isConflict() {
    return this.status === 412 || this.code === "STALE_REVISION" || this.code === "SOURCES_CHANGED";
  }
}

let csrfToken = "";
export function setCsrfToken(token: string) {
  csrfToken = token;
}

async function parse(res: Response): Promise<never> {
  let body: {
    error?: { code?: string; message?: string; detail?: Record<string, unknown> };
    detail?: unknown;
  } = {};
  try {
    body = await res.json();
  } catch {
    /* non-JSON error */
  }
  const err = body.error;
  if (err)
    throw new ApiError(
      res.status,
      err.code ?? "ERROR",
      err.message ?? "Request failed",
      err.detail ?? {},
    );
  if (res.status === 422 && Array.isArray(body.detail)) {
    throw new ApiError(422, "INVALID_INPUT", "Some fields are missing or invalid.", {
      fields: body.detail,
    });
  }
  throw new ApiError(
    res.status,
    "HTTP_" + res.status,
    res.status >= 500 ? "The service is temporarily unavailable." : "Request failed",
  );
}

export async function get<T>(
  path: string,
  init?: RequestInit & { etag?: string },
): Promise<{ data: T | null; etag: string | null; status: number }> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (init?.etag) headers["if-none-match"] = init.etag;
  const res = await fetch(`/api${path}`, {
    ...init,
    headers,
    cache: "no-store",
    credentials: "same-origin",
  });
  if (res.status === 304) return { data: null, etag: init?.etag ?? null, status: 304 };
  if (!res.ok) await parse(res);
  return { data: (await res.json()) as T, etag: res.headers.get("etag"), status: res.status };
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const { data } = await get<T>(path, { signal });
  return data as T;
}

export function newKey(prefix = "cmd"): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  return `${prefix}-${rand}`;
}

export async function command<T>(path: string, body: unknown, key: string): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-csrf-token": csrfToken,
      "idempotency-key": key,
    },
    body: JSON.stringify(body ?? {}),
    credentials: "same-origin",
  });
  if (!res.ok) await parse(res);
  return (await res.json()) as T;
}

export async function uploadCommand<T>(path: string, body: FormData, key: string): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "x-csrf-token": csrfToken, "idempotency-key": key },
    body,
    credentials: "same-origin",
  });
  if (!res.ok) await parse(res);
  return (await res.json()) as T;
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
    body: JSON.stringify(body ?? {}),
    credentials: "same-origin",
  });
  if (!res.ok) await parse(res);
  return (await res.json()) as T;
}
