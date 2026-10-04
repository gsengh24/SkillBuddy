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
  match_not_found: "That match no longer exists.",
  candidate_unavailable: "This person isn't taking new intros right now.",
  already_connected: "You're already connected with this person.",
  intro_exists: "There's already an intro between you two.",
  too_many_pending_intros:
    "You have many intros waiting for an answer. Wait for some replies first.",
  intro_not_found: "That intro no longer exists.",
  intro_not_pending: "This intro has already been answered or has expired.",
  conversation_not_found: "This conversation isn't available.",
  conversation_closed: "This person can't receive messages right now.",
  person_not_found: "We couldn't find that person.",
  block_not_found: "You haven't blocked this person.",
  already_reported: "You've already reported this. Thanks, our moderator has it.",
  message_not_found: "That message no longer exists.",
  cannot_report_own_message: "You can only report messages the other person sent.",
  moderator_only: "Only moderators can do this.",
  space_not_found: "This pair space isn't available.",
  goal_not_found: "That goal no longer exists.",
  skill_not_found: "That skill no longer exists.",
  log_not_found: "That note no longer exists.",
  not_yours: "Only the person who added this can remove it.",
  too_many_goals: "This space has the most goals allowed. Delete or finish some first.",
  too_many_skills: "You have the most skills allowed in this space.",
  skill_exists: "You've already added this skill.",
  report_not_found: "That report no longer exists.",
  report_already_resolved: "This report has already been resolved.",
  account_not_found: "That account no longer exists.",
  cannot_suspend: "This account can't be suspended (it's yours, a moderator's, or not active).",
  not_suspended: "This account isn't suspended.",
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
