import "server-only";

import type { z } from "zod";

import { getServerEnv } from "@/lib/env";

import { errorResponseSchema, type ErrorResponse } from "./schemas";

/**
 * Typed server-side client for the backend API.
 *
 * Every call names the Zod schema of the expected response; the body is validated
 * before it reaches a component. Non-2xx responses surface as {@link ApiError} with the
 * backend's standard error envelope when one is present.
 *
 * Browser-side calls (with the user's session) arrive with auth in Phase 1.
 */

const DEFAULT_TIMEOUT_MS = 5_000;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorResponse | undefined,
    /** The raw JSON body, for endpoints that return data alongside an error status. */
    readonly payload: unknown,
  ) {
    super(body?.error.message ?? `API request failed with status ${status}`);
    this.name = "ApiError";
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  timeoutMs?: number;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

export async function apiRequest<TSchema extends z.ZodType>(
  path: `/${string}`,
  schema: TSchema,
  options: RequestOptions = {},
): Promise<z.infer<TSchema>> {
  const { method = "GET", body, timeoutMs = DEFAULT_TIMEOUT_MS, signal, headers } = options;
  const timeout = AbortSignal.timeout(timeoutMs);

  const response = await fetch(`${getServerEnv().API_INTERNAL_URL}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    cache: "no-store",
  });

  const payload: unknown = await response.json().catch(() => undefined);

  if (!response.ok) {
    const envelope = errorResponseSchema.safeParse(payload);
    throw new ApiError(response.status, envelope.success ? envelope.data : undefined, payload);
  }
  return schema.parse(payload);
}
