import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

import { apiRequest } from "@/lib/api/client";
import { onboardingSchema, type Onboarding } from "@/lib/api/schemas";

/** The signed-in user's onboarding progress (GET /me/onboarding). Cached per request. */
export const getOnboarding = cache(async (): Promise<Onboarding> => {
  const cookieStore = await cookies();
  return apiRequest("/api/v1/me/onboarding", onboardingSchema, {
    headers: { cookie: cookieStore.toString() },
  });
});
