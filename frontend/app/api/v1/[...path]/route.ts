import type { NextRequest } from "next/server";

import { getServerEnv } from "@/lib/env";

/**
 * Same-origin gateway to the API: the browser calls this site's `/api/v1/...` and the
 * Next.js server forwards to API_INTERNAL_URL at request time.
 *
 * Keeping the API behind the web origin means the session and CSRF cookies are first-party
 * wherever the two are hosted, and no CORS is needed.
 */

export const dynamic = "force-dynamic";

const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "authorization",
  "content-type",
  "cookie",
  "user-agent",
  "x-csrf-token",
  "x-request-id",
] as const;

// Hop-by-hop headers, plus encoding/length: fetch already decoded the upstream body.
const DROPPED_RESPONSE_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "set-cookie",
  "transfer-encoding",
]);

const UNAVAILABLE = {
  error: {
    code: "service_unavailable",
    message: "The service is temporarily unavailable. Please try again in a moment.",
    request_id: null,
    details: null,
  },
};

async function forward(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  const target = new URL(
    `${getServerEnv().API_INTERNAL_URL}/api/v1/${path.map(encodeURIComponent).join("/")}`,
  );
  target.search = request.nextUrl.search;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  // Pass the client address on so per-IP rate limits apply to the person, not this server.
  const clientIp = request.headers.get("x-forwarded-for") ?? request.headers.get("x-real-ip");
  if (clientIp) headers.set("x-forwarded-for", clientIp);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    return Response.json(UNAVAILABLE, { status: 503 });
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, name) => {
    if (!DROPPED_RESPONSE_HEADERS.has(name.toLowerCase())) responseHeaders.append(name, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) {
    responseHeaders.append("set-cookie", cookie);
  }
  const body = upstream.status === 204 || upstream.status === 304 ? null : upstream.body;
  return new Response(body, { status: upstream.status, headers: responseHeaders });
}

export { forward as DELETE, forward as GET, forward as PATCH, forward as POST, forward as PUT };
