/**
 * Details used on the privacy policy and terms pages. This is the only place they are
 * defined: change them here.
 *
 * PLACEHOLDER: `contactEmail` is not a real address. Replace it before launch
 * (docs/pre-launch-checklist.md, item 43).
 */
export const legal = {
  /** Where people send privacy requests and complaints. PLACEHOLDER: replace before launch. */
  contactEmail: "privacy-contact@example.com",
  /** Shown as "Last updated" on both pages. */
  updated: "5 October 2026",
  /** Keep equal to the API's TERMS_VERSION (recorded on each account at sign-up). */
  version: "2026-10-05-draft",
} as const;

/**
 * How long things are kept, as the pages say it. Keep in line with the API's settings
 * (backend/.env.example) and docs/storage-budget.md.
 */
export const retention = {
  signInLogDays: 90, // AUTH_EVENT_RETENTION_DAYS
  matchRequestDays: 90, // MATCH_REQUEST_RETENTION_DAYS
  notificationDays: 90, // NOTIFICATION_RETENTION_DAYS
  messageDays: 90, // MESSAGE_RETENTION_DAYS
  spaceDays: 90, // SPACE_RETENTION_DAYS
  reportDaysAfterResolve: 180, // REPORT_RETENTION_DAYS
  moderationLogDays: 365, // MODERATION_LOG_RETENTION_DAYS
  emailLogDays: 30, // EMAIL_LOG_RETENTION_DAYS
  deletionGraceDays: 30, // ACCOUNT_DELETION_GRACE_DAYS
} as const;
