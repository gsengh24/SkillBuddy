import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import { messagePageSchema, messageUpdatesSchema } from "@/lib/api/schemas";

async function cookieHeader(): Promise<Record<string, string>> {
  return { cookie: (await cookies()).toString() };
}

/**
 * The newest messages in one conversation, plus a polling cursor taken *before* them, so
 * nothing sent while the page loads is missed (a repeat is possible; the client
 * de-duplicates by id).
 */
export async function getConversation(connectionId: string) {
  const headers = await cookieHeader();
  const start = await apiRequest("/api/v1/messages/updates", messageUpdatesSchema, { headers });
  const page = await apiRequest(
    `/api/v1/connections/${encodeURIComponent(connectionId)}/messages?limit=50`,
    messagePageSchema,
    { headers },
  );
  return { page, cursor: start.cursor };
}
