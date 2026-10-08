import { z } from "zod";

/** Responses of /api/v1/admin (ADR 0015). */
export const adminRoleSchema = z.enum(["owner", "admin", "moderator", "readonly"]);
export type AdminRole = z.infer<typeof adminRoleSchema>;

export const twoStepStatusSchema = z.object({
  role: adminRoleSchema,
  two_step_enabled: z.boolean(),
});

export const twoStepSetupSchema = z.object({ secret: z.string(), otpauth_uri: z.string() });

export const adminSessionSchema = z.object({
  expires_at: z.string(),
  recovery_codes: z.array(z.string()).nullable().default(null),
});

export const adminMeSchema = z.object({
  user_id: z.string(),
  email: z.string(),
  name: z.string(),
  role: adminRoleSchema,
  permissions: z.array(z.string()),
});
export type AdminMe = z.infer<typeof adminMeSchema>;

export const permissionTableSchema = z.object({
  roles: z.array(adminRoleSchema),
  rows: z.array(
    z.object({ permission: z.string(), label: z.string(), roles: z.array(adminRoleSchema) }),
  ),
});
export type PermissionTable = z.infer<typeof permissionTableSchema>;

export const auditEntrySchema = z.object({
  id: z.string(),
  created_at: z.string(),
  actor_id: z.string().nullable(),
  actor_role: z.string().nullable(),
  action: z.string(),
  target_type: z.string().nullable(),
  target_id: z.string().nullable(),
  reason: z.string().nullable(),
  ip: z.string().nullable(),
});
export type AuditEntry = z.infer<typeof auditEntrySchema>;
export const auditPageSchema = z.object({
  items: z.array(auditEntrySchema),
  next_cursor: z.string().nullable(),
});
export type AuditPage = z.infer<typeof auditPageSchema>;

export const teamMemberSchema = z.object({
  user_id: z.string(),
  email: z.string(),
  role: adminRoleSchema,
  from_environment: z.boolean(),
  two_step_enabled: z.boolean(),
  last_active_at: z.string().nullable(),
});
export type TeamMember = z.infer<typeof teamMemberSchema>;
export const teamSchema = z.object({ items: z.array(teamMemberSchema) });

export const ROLE_LABELS: Record<AdminRole, string> = {
  owner: "Owner",
  admin: "Admin",
  moderator: "Moderator",
  readonly: "Read-only",
};

export const userStatusSchema = z.enum([
  "active",
  "paused",
  "pending",
  "suspended",
  "banned",
  "pending_deletion",
]);
export type UserStatus = z.infer<typeof userStatusSchema>;

export const STATUS_LABELS: Record<UserStatus, string> = {
  active: "Active",
  paused: "Paused",
  pending: "Pending",
  suspended: "Suspended",
  banned: "Banned",
  pending_deletion: "Deleting",
};

export const userRowSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string().nullable(),
  status: userStatusSchema,
  intents: z.array(z.string()),
  flagged: z.boolean(),
  created_at: z.string(),
  last_login_at: z.string().nullable(),
});
export type UserRow = z.infer<typeof userRowSchema>;
export const userPageSchema = z.object({
  items: z.array(userRowSchema),
  next_cursor: z.string().nullable(),
  total: z.number(),
});

export const noteSchema = z.object({
  id: z.string(),
  author_id: z.string().nullable(),
  body: z.string(),
  created_at: z.string(),
});
export type Note = z.infer<typeof noteSchema>;

export const userDetailSchema = z.object({
  id: z.string(),
  email: z.string(),
  status: userStatusSchema,
  suspended_until: z.string().nullable(),
  deletion_scheduled_for: z.string().nullable(),
  created_at: z.string(),
  last_login_at: z.string().nullable(),
  email_verified_at: z.string().nullable(),
  sign_in_methods: z.array(z.string()),
  profile: z
    .object({
      display_name: z.string(),
      headline: z.string(),
      city: z.string(),
      about_text: z.string(),
      intents: z.array(z.string()),
      visibility: z.string(),
      parse_status: z.string(),
    })
    .nullable(),
  counts: z.record(z.string(), z.number()),
  timeline: z.array(z.object({ at: z.string(), event: z.string() })),
  notes: z.array(noteSchema),
});
export type UserDetail = z.infer<typeof userDetailSchema>;

const personSchema = z.object({ id: z.string(), email: z.string(), status: z.string() });

export const queueItemSchema = z.object({
  id: z.string(),
  status: z.enum(["open", "in_review", "resolved"]),
  reason: z.string(),
  target: z.string(),
  created_at: z.string(),
  decision: z.string().nullable(),
  reported: personSchema.nullable(),
  reporter: personSchema.nullable(),
});
export type QueueItem = z.infer<typeof queueItemSchema>;
export const queueSchema = z.object({
  items: z.array(queueItemSchema),
  next_cursor: z.string().nullable(),
});

export const caseSchema = z.object({
  report: queueItemSchema,
  details: z.string(),
  attached: z.array(
    z.object({
      label: z.string().nullable(),
      sender: z.enum(["reporter", "reported"]),
      body: z.string(),
      sent_at: z.string().nullable(),
    }),
  ),
  resolution_note: z.string(),
  resolved_at: z.string().nullable(),
  reported_history: z.record(z.string(), z.number()),
  reporter_history: z.record(z.string(), z.number()),
});
export type Case = z.infer<typeof caseSchema>;

export const appealSchema = z.object({
  id: z.string(),
  person: personSchema.nullable(),
  against: z.string(),
  appeal: z.string(),
  status: z.enum(["open", "upheld", "overturned"]),
  created_at: z.string(),
  decided_at: z.string().nullable(),
});
export type Appeal = z.infer<typeof appealSchema>;
export const appealPageSchema = z.object({
  items: z.array(appealSchema),
  next_cursor: z.string().nullable(),
});

export const blockStatsSchema = z.object({
  total: z.number(),
  last_30_days: z.number(),
  most_blocked: z.array(
    z.object({ user_id: z.string(), email: z.string(), status: z.string(), times: z.number() }),
  ),
});
export type BlockStats = z.infer<typeof blockStatsSchema>;

export const overviewSchema = z.object({
  days: z.number(),
  generated_at: z.string(),
  kpis: z.array(z.object({ key: z.string(), value: z.number(), previous: z.number() })),
  signups_by_day: z.array(z.object({ day: z.string(), count: z.number() })),
  funnel: z.array(z.object({ step: z.string(), count: z.number() })),
  attention: z.record(z.string(), z.number()),
  activity: z.array(auditEntrySchema),
});
export type Overview = z.infer<typeof overviewSchema>;

export const healthSchema = z.object({
  checks: z.array(z.object({ name: z.string(), status: z.string(), detail: z.string() })),
  checked_at: z.string(),
});
export type Health = z.infer<typeof healthSchema>;

export const signupModeSchema = z.enum(["open", "invite_only", "closed"]);
export type SignupMode = z.infer<typeof signupModeSchema>;

export const accessSchema = z.object({
  mode: signupModeSchema,
  waitlist: z.number(),
  allowed_domains: z.array(z.string()),
  blocked_domains: z.array(z.string()),
});
export type Access = z.infer<typeof accessSchema>;

export const applicationSchema = z.object({
  id: z.string(),
  email: z.string(),
  source: z.string(),
  created_at: z.string(),
});
export type Application = z.infer<typeof applicationSchema>;
export const applicationPageSchema = z.object({
  items: z.array(applicationSchema),
  next_cursor: z.string().nullable(),
});

export const inviteCodeSchema = z.object({
  id: z.string(),
  code: z.string(),
  uses: z.number(),
  max_uses: z.number(),
  expires_at: z.string().nullable(),
  revoked_at: z.string().nullable(),
  created_at: z.string(),
  created_by: z.string().nullable(),
  status: z.enum(["active", "used_up", "expired", "revoked"]),
});
export type InviteCode = z.infer<typeof inviteCodeSchema>;
export const inviteCodePageSchema = z.object({
  items: z.array(inviteCodeSchema),
  next_cursor: z.string().nullable(),
});

export const invitedSchema = z.object({ invited: z.number() });
export const domainSchema = z.object({ domain: z.string() });

export const settingsSchema = z.object({
  server: z.object({ app_name: z.string(), terms_version: z.string(), environment: z.string() }),
  signup_mode: signupModeSchema,
  features: z.array(z.object({ key: z.string(), on: z.boolean() })),
  limits: z.array(
    z.object({
      key: z.string(),
      value: z.number(),
      default: z.number(),
      minimum: z.number(),
      maximum: z.number(),
    }),
  ),
  intents: z.array(z.string()),
});
export type AdminSettings = z.infer<typeof settingsSchema>;
export type LimitState = AdminSettings["limits"][number];

export const contentRulesSchema = z.object({
  rules: z.array(z.object({ key: z.string(), on: z.boolean() })),
});

export const flagSchema = z.object({
  id: z.string(),
  rule: z.string(),
  item_type: z.enum(["request", "profile", "intro"]),
  item_id: z.string(),
  user_id: z.string(),
  email: z.string().nullable(),
  flagged_text: z.string().nullable(),
  created_at: z.string(),
});
export type Flag = z.infer<typeof flagSchema>;
export const flagPageSchema = z.object({
  items: z.array(flagSchema),
  next_cursor: z.string().nullable(),
});

export const aiProviderSchema = z.object({
  name: z.string(),
  role: z.enum(["primary", "fallback"]),
  on: z.boolean(),
  status: z.enum(["ok", "degraded", "idle", "off"]),
  p50_ms: z.number().nullable(),
  p95_ms: z.number().nullable(),
  calls_24h: z.number(),
  error_rate: z.number().nullable(),
  cost_today: z.number(),
  cost_unit: z.string(),
  daily_budget: z.number(),
});
export type AiProvider = z.infer<typeof aiProviderSchema>;

export const aiOverviewSchema = z.object({
  llm_enabled: z.boolean(),
  providers: z.array(aiProviderSchema),
  fallbacks_today: z.record(z.string(), z.number()),
  quality: z.object({
    days: z.number(),
    intros_sent: z.number(),
    accept_rate: z.number().nullable(),
    ignore_rate: z.number().nullable(),
    report_rate: z.number().nullable(),
  }),
  evals: z.object({
    connected: z.boolean(),
    labelled: z.number().nullable(),
    total: z.number().nullable(),
    latest_score: z.number().nullable(),
  }),
});
export type AiOverview = z.infer<typeof aiOverviewSchema>;

export const rerunQueuedSchema = z.object({ request_id: z.string(), status: z.literal("queued") });
export const probeQueuedSchema = z.object({ queued: z.boolean() });
