import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import { spaceSchema } from "@/lib/api/schemas";

/** One pair space: its goals, both people's skills and the newest notes. */
export async function getSpace(connectionId: string) {
  return apiRequest(`/api/v1/connections/${encodeURIComponent(connectionId)}/space`, spaceSchema, {
    headers: { cookie: (await cookies()).toString() },
  });
}
