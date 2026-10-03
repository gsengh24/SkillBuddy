/** Report reasons, in the words people see. The keys are the API's values. */
export const REPORT_REASONS = [
  { value: "harassment", label: "Harassment or bullying" },
  { value: "spam", label: "Spam or advertising" },
  { value: "scam", label: "Scam or asking for money" },
  { value: "inappropriate", label: "Sexual or inappropriate content" },
  { value: "safety", label: "Safety concern: threats, self-harm, or someone may be under 18" },
  { value: "other", label: "Something else" },
] as const;

export type ReportReason = (typeof REPORT_REASONS)[number]["value"];

/** The API's limit on the optional note (REPORT_DETAILS_MAX_LENGTH). */
export const REPORT_DETAILS_MAX_LENGTH = 500;
