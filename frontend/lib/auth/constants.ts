/**
 * Must match the backend's SESSION_COOKIE_NAME / CSRF_COOKIE_NAME settings (their defaults).
 * The browser never sees the session token: it is an httpOnly cookie.
 */
export const SESSION_COOKIE = "session";
export const CSRF_COOKIE = "csrf_token";
export const CSRF_HEADER = "X-CSRF-Token";

/** Where people land after signing in, unless a safe `next` path says otherwise. */
export const DEFAULT_SIGNED_IN_PATH = "/home";

/** Seconds before "Resend code" becomes available again. */
export const RESEND_COOLDOWN_SECONDS = 60;
