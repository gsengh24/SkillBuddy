import "server-only";

import { z } from "zod";

/**
 * Server-side environment, validated on first use.
 *
 * Validation is lazy (not at import time) so `next build` does not need runtime
 * values; a misconfigured server fails on its first request with a clear message.
 * Browser-exposed variables must be prefixed NEXT_PUBLIC_ and are inlined at build.
 */
const serverEnvSchema = z.object({
  /** Base URL the Next.js server uses to reach the API, e.g. http://api:8000 in Docker. */
  API_INTERNAL_URL: z.url().transform((url) => url.replace(/\/+$/, "")),
});

export type ServerEnv = z.infer<typeof serverEnvSchema>;

let cached: ServerEnv | undefined;

export function getServerEnv(): ServerEnv {
  if (cached) return cached;
  const result = serverEnvSchema.safeParse(process.env);
  if (!result.success) {
    throw new Error(`Invalid server environment:\n${z.prettifyError(result.error)}`);
  }
  cached = result.data;
  return cached;
}
