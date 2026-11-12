import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

import { apiRequest } from "@/lib/api/client";
import {
  currentNudgeSchema,
  demandSchema,
  onboardingSchema,
  type Nudge,
  type Onboarding,
} from "@/lib/api/schemas";

/** The signed-in user's onboarding progress (GET /me/onboarding). Cached per request. */
export const getOnboarding = cache(async (): Promise<Onboarding> => {
  const cookieStore = await cookies();
  return apiRequest("/api/v1/me/onboarding", onboardingSchema, {
    headers: { cookie: cookieStore.toString() },
  });
});

/** Today's in-context nudge on Home (screen 11), or null. Never fails the page. */
export async function getNudge(): Promise<Nudge | null> {
  const cookieStore = await cookies();
  try {
    const { nudge } = await apiRequest("/api/v1/me/nudge", currentNudgeSchema, {
      headers: { cookie: cookieStore.toString() },
    });
    return nudge;
  } catch {
    return null;
  }
}

/** How many people want `skill` this week, or null (below the minimum, or on any error). */
export async function getDemand(skill: string): Promise<number | null> {
  const cookieStore = await cookies();
  try {
    const demand = await apiRequest(
      `/api/v1/stats/demand?skill=${encodeURIComponent(skill)}`,
      demandSchema,
      { headers: { cookie: cookieStore.toString() } },
    );
    return demand.count;
  } catch {
    return null;
  }
}
