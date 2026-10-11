import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import {
  matchListSchema,
  matchRequestPageSchema,
  type Match,
  type MatchRequest,
} from "@/lib/api/schemas";

/** The signed-in user's most recent match requests (newest first). */
export async function getMyRequests(limit = 10): Promise<MatchRequest[]> {
  const cookieStore = await cookies();
  const page = await apiRequest(`/api/v1/requests?limit=${limit}`, matchRequestPageSchema, {
    headers: { cookie: cookieStore.toString() },
  });
  return page.items;
}

/** The people matched to one of the signed-in user's requests (empty while it is pending). */
export async function getRequestMatches(requestId: string): Promise<Match[]> {
  const cookieStore = await cookies();
  const list = await apiRequest(
    `/api/v1/requests/${encodeURIComponent(requestId)}/matches`,
    matchListSchema,
    { headers: { cookie: cookieStore.toString() } },
  );
  return list.items;
}
