import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import {
  listedTeamPageSchema,
  messageUpdatesSchema,
  teamInviteListSchema,
  teamListSchema,
  teamMessagePageSchema,
  teamSchema,
  teamSpaceSchema,
  teamSummarySchema,
  type TeamPurpose,
} from "@/lib/api/schemas";

async function cookieHeader(): Promise<Record<string, string>> {
  return { cookie: (await cookies()).toString() };
}

/** The teams the person is in, most recently joined first (ADR 0016). */
export async function getTeams() {
  return apiRequest("/api/v1/teams", teamListSchema, { headers: await cookieHeader() });
}

/** Open invites to the person. */
export async function getTeamInvites() {
  return apiRequest("/api/v1/teams/invites", teamInviteListSchema, {
    headers: await cookieHeader(),
  });
}

/** One team with its members (and, for the owner, its open invites). */
export async function getTeam(teamId: string) {
  return apiRequest(`/api/v1/teams/${encodeURIComponent(teamId)}`, teamSchema, {
    headers: await cookieHeader(),
  });
}

/** A team's goals, skills and newest notes. */
export async function getTeamSpace(teamId: string) {
  return apiRequest(`/api/v1/teams/${encodeURIComponent(teamId)}/space`, teamSpaceSchema, {
    headers: await cookieHeader(),
  });
}

/**
 * The newest messages in a team's chat, plus a polling cursor taken *before* them, so
 * nothing sent while the page loads is missed (the client de-duplicates by id).
 */
export async function getTeamChat(teamId: string) {
  const headers = await cookieHeader();
  const start = await apiRequest("/api/v1/messages/updates", messageUpdatesSchema, { headers });
  const page = await apiRequest(
    `/api/v1/teams/${encodeURIComponent(teamId)}/messages?limit=50`,
    teamMessagePageSchema,
    { headers },
  );
  return { page, cursor: start.cursor };
}

/** The team behind an invite link: name, purpose and size only. */
export async function getTeamByLink(code: string) {
  return apiRequest(`/api/v1/teams/join/${encodeURIComponent(code)}`, teamSummarySchema, {
    headers: await cookieHeader(),
  });
}

/** Teams their owners listed, which the person could ask to join. */
export async function getListedTeams({
  purpose,
  cursor,
}: {
  purpose?: TeamPurpose;
  cursor?: string;
}) {
  const query = new URLSearchParams({
    ...(purpose ? { purpose } : {}),
    ...(cursor ? { cursor } : {}),
  }).toString();
  return apiRequest(`/api/v1/teams/listed${query ? `?${query}` : ""}`, listedTeamPageSchema, {
    headers: await cookieHeader(),
  });
}

/** The person's own open requests to join teams. */
export async function getMyTeamRequests() {
  return apiRequest("/api/v1/teams/requests", teamInviteListSchema, {
    headers: await cookieHeader(),
  });
}
