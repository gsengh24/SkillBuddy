import { ApiError } from "@/lib/api/errors";

/** Plain-language messages for the backend's stable error codes (ADR 0006). */
const MESSAGES: Record<string, string> = {
  invalid_code:
    "That code is incorrect or has expired. Check your latest email or request a new code.",
  code_locked: "Too many incorrect attempts. Request a new code to try again.",
  consent_required: "To create an account, confirm that you are 18 or older and accept the terms.",
  account_suspended: "This account is suspended. Contact support for help.",
  signups_paused:
    "We're not accepting new sign-ups right now. Please try again later. Existing accounts can still sign in.",
  csrf_failed: "Your session check failed. Reload the page and try again.",
  authentication_required: "Your session has ended. Please sign in again.",
  validation_error: "Please check what you entered and try again.",
  service_unavailable: "The service is temporarily unavailable. Please try again in a moment.",
  email_quota_exhausted:
    "We've sent as many sign-in emails as we can for now. Please try again in a few hours.",
};

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "rate_limited") {
      const minutes = error.retryAfterSeconds ? Math.ceil(error.retryAfterSeconds / 60) : null;
      return minutes
        ? `Too many attempts. Please wait about ${minutes} minute${minutes === 1 ? "" : "s"} and try again.`
        : "Too many attempts. Please wait a few minutes and try again.";
    }
    // The server's message names the scheduled deletion date, so show it as is.
    if (error.code === "account_pending_deletion" && error.body) {
      return error.body.error.message;
    }
    if (error.code && error.code in MESSAGES) {
      return MESSAGES[error.code] ?? error.message;
    }
    return "Something went wrong. Please try again.";
  }
  return "We couldn't reach the server. Check your connection and try again.";
}
