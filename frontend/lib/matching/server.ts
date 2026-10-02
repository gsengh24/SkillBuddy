import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import { matchRequestPageSchema, type MatchRequest } from "@/lib/api/schemas";

/** The signed-in user's most recent match requests (newest first). */
export async function getMyRequests(limit = 10): Promise<MatchRequest[]> {
  const cookieStore = await cookies();
  const page = await apiRequest(`/api/v1/requests?limit=${limit}`, matchRequestPageSchema, {
    headers: { cookie: cookieStore.toString() },
  });
  return page.items;
}
