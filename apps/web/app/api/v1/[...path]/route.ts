import type { NextRequest } from "next/server";

const BODYLESS_METHODS = new Set(["GET", "HEAD"]);
const HOP_BY_HOP_HEADERS = [
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];

type RouteContext = { params: Promise<{ path: string[] }> };

function apiOrigin() {
  return process.env.INTERNAL_API_URL?.trim().replace(/\/+$/, "") || "http://localhost:8000";
}

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const incoming = new URL(request.url);
  const safePath = path.map(encodeURIComponent).join("/");
  const upstreamUrl = new URL(`/api/v1/${safePath}${incoming.search}`, apiOrigin());
  const requestHeaders = new Headers(request.headers);

  for (const header of HOP_BY_HOP_HEADERS) requestHeaders.delete(header);
  requestHeaders.set("x-forwarded-host", incoming.host);
  requestHeaders.set("x-forwarded-proto", incoming.protocol.replace(":", ""));

  try {
    const body = BODYLESS_METHODS.has(request.method) ? undefined : await request.arrayBuffer();
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers: requestHeaders,
      body,
      cache: "no-store",
      redirect: "manual",
    });
    const responseHeaders = new Headers(upstream.headers);
    for (const header of HOP_BY_HOP_HEADERS) responseHeaders.delete(header);
    responseHeaders.delete("content-encoding");

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      {
        error: {
          code: "service_unavailable",
          message: "The portal service is temporarily unavailable. Please try again.",
        },
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}

export const dynamic = "force-dynamic";
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
