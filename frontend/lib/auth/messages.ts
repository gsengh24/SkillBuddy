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
  ai_consent_required: "To save, agree to how AI is used to find your matches.",
  profile_not_found: "You haven't created a profile yet.",
  profile_text_required: "Add a description first, then correct what we understood.",
  storage_full: "We can't save changes right now. Please try again later.",
  profile_required: "Create your profile first, so we know who to introduce you to.",
  too_many_open_requests: "You have the most open requests allowed. Close one to start another.",
  match_request_not_found: "That request no longer exists.",
  email_not_allowed: "This email address can't be used to sign in here.",
  account_pending_deletion:
    "This account is scheduled for permanent deletion and can no longer sign in. Contact support if this is a mistake.",
  rate_limited: "Too many attempts. Please wait a few minutes and try again.",
  google_failed: "We couldn't sign you in with Google. Please try again, or use an email code.",
  google_cancelled: "Google sign-in was cancelled.",
  google_state_invalid:
    "That sign-in attempt expired or was already used. Please try Continue with Google again.",
  google_signin_unavailable: "Sign in with Google isn't available right now. Use an email code.",
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

/** The message for an error code passed back in a URL (e.g. /login?error=...), if known. */
export function messageForCode(code: string | undefined): string | null {
  if (!code || !Object.hasOwn(MESSAGES, code)) return null;
  return MESSAGES[code] ?? null;
}
