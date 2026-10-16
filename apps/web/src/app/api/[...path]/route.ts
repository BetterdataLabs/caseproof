/**
 * Same-origin proxy to the private CaseProof API.
 * The browser never talks to the API directly. Client-supplied identity headers are dropped. The web
 * forwards cookies and, when configured, a verified IAP assertion together with this service's own identity token.
 */
import { NextRequest } from "next/server";

const API_URL = process.env.CASEPROOF_API_URL ?? "http://127.0.0.1:8400";
const FORWARD_REQUEST = [
  "content-type",
  "cookie",
  "if-none-match",
  "idempotency-key",
  "x-csrf-token",
  "origin",
  "accept",
];
const FORWARD_RESPONSE = [
  "content-type",
  "etag",
  "set-cookie",
  "content-disposition",
  "cache-control",
  "x-export-status",
  "idempotent-replay",
];

async function serviceToken(): Promise<string | null> {
  if (!process.env.CASEPROOF_API_AUDIENCE) return null;
  const url = `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(process.env.CASEPROOF_API_AUDIENCE)}`;
  const res = await fetch(url, {
    headers: { "Metadata-Flavor": "Google" },
    cache: "no-store",
    signal: AbortSignal.timeout(5_000),
  });
  if (!res.ok) throw new Error("Service identity is unavailable.");
  return res.text();
}

async function proxy(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (path[0] === "jobs") return new Response("Not found", { status: 404 });
  const target = `${API_URL}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  for (const name of FORWARD_REQUEST) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const forwarded = request.headers.get("x-forwarded-for");
  const client = forwarded?.split(",").at(-1)?.trim();
  if (client) headers.set("x-caseproof-client", client.slice(0, 80));
  const assertion = request.headers.get("x-goog-iap-jwt-assertion");
  if (assertion && process.env.CASEPROOF_TRUST_IAP === "true")
    headers.set("x-goog-iap-jwt-assertion", assertion);
  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
    cache: "no-store",
  };
  if (!["GET", "HEAD"].includes(request.method)) {
    const upload =
      path.join("/") === "v1/cases/upload" ||
      /^v1\/vendor\/cases(?:\/[^/]+\/inputs)?$/.test(path.join("/")) ||
      /^v1\/cases\/[^/]+\/(inputs|document-checks)$/.test(path.join("/"));
    const limit = upload ? 21 * 1024 * 1024 : 32 * 1024;
    const tooLarge = () =>
      Response.json(
        {
          error: {
            code: "COMMAND_TOO_LARGE",
            message: upload
              ? "Choose files totaling at most 20 MiB."
              : "Commands are limited to 32 KiB.",
          },
        },
        { status: 413 },
      );
    if (Number(request.headers.get("content-length")) > limit) return tooLarge();
    const reader = request.body?.getReader();
    const chunks: Uint8Array<ArrayBuffer>[] = [];
    let size = 0;
    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > limit) {
          await reader.cancel();
          return tooLarge();
        }
        chunks.push(value);
      }
    }
    init.body = new Blob(chunks);
  }
  let upstream: Response;
  try {
    const token = await serviceToken();
    if (token) headers.set("authorization", `Bearer ${token}`);
    upstream = await fetch(target, init);
  } catch {
    return Response.json(
      { error: { code: "API_UNAVAILABLE", message: "The CaseProof service is unavailable." } },
      { status: 503 },
    );
  }
  const out = new Headers();
  for (const name of FORWARD_RESPONSE) {
    if (name === "set-cookie") {
      for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
      continue;
    }
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  return new Response(upstream.status === 304 ? null : upstream.body, {
    status: upstream.status,
    headers: out,
  });
}

export const GET = proxy;
export const POST = proxy;
