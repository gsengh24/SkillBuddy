import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import {
  matchListSchema,
  matchRequestPageSchema,
  matchRequestSchema,
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

/** One of the signed-in user's requests (404 if it is not theirs or does not exist). */
export async function getRequest(requestId: string): Promise<MatchRequest> {
  const cookieStore = await cookies();
  return apiRequest(`/api/v1/requests/${encodeURIComponent(requestId)}`, matchRequestSchema, {
    headers: { cookie: cookieStore.toString() },
  });
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
