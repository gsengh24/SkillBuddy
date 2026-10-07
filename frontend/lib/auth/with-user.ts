import "server-only";

import { redirect } from "next/navigation";

import type { User } from "@/lib/api/schemas";

import { getCurrentUser } from "./session";

/**
 * Pass a protected page's data call alongside the session check, so neither waits for the
 * other. The API checks the session on every call anyway, so starting the data call first
 * is safe.
 *
 * Signed-out visitors go to `loginPath`, and the data call's own failure is then ignored.
 * Otherwise a failed data call throws as usual (error.tsx), after the user is known.
 *
 * Callers start `data` before calling this; the session check runs in here.
 */
export async function withUser<T>(
  loginPath: string,
  data: Promise<T>,
): Promise<{ user: User; data: T }> {
  // Mark the rejection as handled: we may redirect before awaiting `data`.
  data.catch(() => undefined);
  const user = await getCurrentUser();
  if (!user) redirect(loginPath);
  return { user, data: await data };
}

/**
 * Start a call whose result a page may never await (for example when the page turns out to
 * be a 404): its failure is handled here and still thrown to anyone who awaits it.
 */
export function startEarly<T>(call: Promise<T>): Promise<T> {
  call.catch(() => undefined);
  return call;
}
