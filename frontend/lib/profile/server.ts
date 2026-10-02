import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

import { apiRequest } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { profileSchema, type Profile } from "@/lib/api/schemas";

/** The signed-in user's profile, or null if they have not created one. Cached per request. */
export const getMyProfile = cache(async (): Promise<Profile | null> => {
  const cookieStore = await cookies();
  try {
    return await apiRequest("/api/v1/me/profile", profileSchema, {
      headers: { cookie: cookieStore.toString() },
    });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 401)) return null;
    throw error;
  }
});
