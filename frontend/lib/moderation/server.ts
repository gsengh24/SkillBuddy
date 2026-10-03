import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import { moderationAccountListSchema, moderationReportPageSchema } from "@/lib/api/schemas";

async function cookieHeader(): Promise<Record<string, string>> {
  return { cookie: (await cookies()).toString() };
}

/** Reports for the moderator, oldest first. */
export async function getModerationReports(status: "open" | "resolved") {
  return apiRequest(
    `/api/v1/moderation/reports?status=${status}&limit=50`,
    moderationReportPageSchema,
    {
      headers: await cookieHeader(),
    },
  );
}

/** Suspended accounts, most recently suspended first. */
export async function getSuspendedAccounts() {
  return apiRequest("/api/v1/moderation/accounts/suspended", moderationAccountListSchema, {
    headers: await cookieHeader(),
  });
}
