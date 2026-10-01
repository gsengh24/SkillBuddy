import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { userSchema, type User } from "@/lib/api/schemas";

import { SESSION_COOKIE } from "./constants";

/**
 * The signed-in user for the current request, checked with the API (not just the cookie's
 * presence), or null. Use in server components and route handlers.
 */
export async function getCurrentUser(): Promise<User | null> {
  const cookieStore = await cookies();
  if (!cookieStore.has(SESSION_COOKIE)) return null;
  try {
    return await apiRequest("/api/v1/auth/me", userSchema, {
      headers: { cookie: cookieStore.toString() },
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
