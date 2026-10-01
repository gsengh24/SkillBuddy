import type { z } from "zod";

import { CSRF_COOKIE, CSRF_HEADER } from "@/lib/auth/constants";

import { ApiError, retryAfterFrom } from "./errors";
import { errorResponseSchema } from "./schemas";

/**
 * Typed client for calls made from the browser.
 *
 * Requests go to this site's own `/api/v1/...`, which the Next.js server forwards to the
 * API (`app/api/v1/[...path]/route.ts`), so the session cookie stays first-party and is
 * sent automatically. State-changing requests echo the CSRF cookie in `X-CSRF-Token`
 * (signed double-submit, ADR 0006). Every response is validated with a Zod schema.
 */

const DEFAULT_TIMEOUT_MS = 15_000;

export interface BrowserRequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  timeoutMs?: number;
}

export function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  for (const part of document.cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return undefined;
}

export async function browserApi<TSchema extends z.ZodType>(
  path: `/${string}`,
  schema: TSchema,
  options: BrowserRequestOptions = {},
): Promise<z.infer<TSchema>> {
  const { method = "GET", body, timeoutMs = DEFAULT_TIMEOUT_MS } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers[CSRF_HEADER] = csrf;
  }

  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });

  const payload: unknown =
    response.status === 204 ? undefined : await response.json().catch(() => undefined);

  if (!response.ok) {
    const envelope = errorResponseSchema.safeParse(payload);
    throw new ApiError(
      response.status,
      envelope.success ? envelope.data : undefined,
      payload,
      retryAfterFrom(response.headers),
    );
  }
  return schema.parse(payload);
}
