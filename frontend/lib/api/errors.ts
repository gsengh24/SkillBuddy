import type { ErrorResponse } from "./schemas";

/** A non-2xx API response, carrying the backend's standard error envelope when present. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorResponse | undefined,
    /** The raw JSON body, for endpoints that return data alongside an error status. */
    readonly payload: unknown,
    /** Seconds from the Retry-After header (rate limits), when present. */
    readonly retryAfterSeconds?: number,
  ) {
    super(body?.error.message ?? `API request failed with status ${status}`);
    this.name = "ApiError";
  }

  get code(): string | undefined {
    return this.body?.error.code;
  }
}

export function retryAfterFrom(headers: Headers): number | undefined {
  const value = Number(headers.get("retry-after"));
  return Number.isFinite(value) && value > 0 ? value : undefined;
}
