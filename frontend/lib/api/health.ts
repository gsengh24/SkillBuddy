import "server-only";

import { apiRequest } from "./client";
import { ApiError } from "./errors";
import { readinessResponseSchema, type ReadinessResponse } from "./schemas";

export type ApiStatus =
  | { state: "connected"; readiness: ReadinessResponse }
  | { state: "degraded"; readiness: ReadinessResponse }
  | { state: "unreachable"; reason: string };

/** Ask the API whether it and its dependencies are ready. Never throws. */
export async function getApiStatus(): Promise<ApiStatus> {
  try {
    const readiness = await apiRequest("/api/v1/health/ready", readinessResponseSchema, {
      timeoutMs: 3_000,
    });
    return { state: "connected", readiness };
  } catch (error) {
    // 503 still carries the per-dependency report: the API is up, something behind it isn't.
    if (error instanceof ApiError && error.status === 503) {
      const readiness = readinessResponseSchema.safeParse(error.payload);
      if (readiness.success) return { state: "degraded", readiness: readiness.data };
    }
    const reason = error instanceof Error ? error.message : "Unknown error";
    console.error("API status check failed:", reason);
    return { state: "unreachable", reason };
  }
}
