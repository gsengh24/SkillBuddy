import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import { dataExportListSchema, sessionListSchema } from "@/lib/api/schemas";

/** The signed-in user's devices, most recently used first. */
export async function getSessions() {
  return apiRequest("/api/v1/auth/sessions", sessionListSchema, {
    headers: { cookie: (await cookies()).toString() },
  });
}

/** The latest "Download my data" requests, newest first. */
export async function getDataExports() {
  return apiRequest("/api/v1/me/data-exports", dataExportListSchema, {
    headers: { cookie: (await cookies()).toString() },
  });
}
