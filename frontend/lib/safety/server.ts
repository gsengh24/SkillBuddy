import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import { blockListSchema } from "@/lib/api/schemas";

/** People the signed-in user has blocked, newest first. */
export async function getBlocks() {
  return apiRequest("/api/v1/blocks", blockListSchema, {
    headers: { cookie: (await cookies()).toString() },
  });
}
