import { z } from "zod";

/**
 * Runtime schemas for API responses. They mirror the backend's Pydantic models
 * (backend/app/schemas); every response is parsed, never trusted blindly.
 */

export const errorResponseSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string().nullable(),
    details: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
  }),
});
export type ErrorResponse = z.infer<typeof errorResponseSchema>;

export const livenessResponseSchema = z.object({
  status: z.literal("ok"),
  service: z.string(),
  version: z.string(),
  environment: z.string(),
});
export type LivenessResponse = z.infer<typeof livenessResponseSchema>;

export const dependencyCheckSchema = z.object({
  status: z.enum(["ok", "fail"]),
  latency_ms: z.number(),
  detail: z.string().nullable().optional(),
});
export type DependencyCheck = z.infer<typeof dependencyCheckSchema>;

export const readinessResponseSchema = z.object({
  status: z.enum(["ok", "unavailable"]),
  checks: z.record(z.string(), dependencyCheckSchema),
});
export type ReadinessResponse = z.infer<typeof readinessResponseSchema>;

export const userSchema = z.object({
  id: z.string(),
  email: z.string(),
  created_at: z.string(),
  email_verified_at: z.string().nullable(),
  last_login_at: z.string().nullable(),
  terms_version: z.string().nullable(),
  terms_accepted_at: z.string().nullable(),
});
export type User = z.infer<typeof userSchema>;

export const otpRequestResponseSchema = z.object({
  status: z.literal("sent"),
  message: z.string(),
  expires_in_seconds: z.number(),
});
export type OtpRequestResponse = z.infer<typeof otpRequestResponseSchema>;

export const deletionScheduledSchema = z.object({
  status: z.literal("pending_deletion"),
  deletion_scheduled_for: z.string(),
  message: z.string(),
});
export type DeletionScheduled = z.infer<typeof deletionScheduledSchema>;

/** For endpoints that answer 204 No Content. */
export const noContentSchema = z.undefined();

export const understandingSchema = z.object({
  summary: z.string(),
  offers: z.array(z.string()),
  seeks: z.array(z.string()),
  interests: z.array(z.string()),
  availability: z.string(),
});
export type Understanding = z.infer<typeof understandingSchema>;

export const profileSchema = z.object({
  user_id: z.string(),
  display_name: z.string(),
  about_text: z.string(),
  links: z.array(z.string()),
  timezone: z.string().nullable(),
  languages: z.array(z.string()),
  visibility: z.enum(["matchable", "paused"]),
  parse_status: z.enum(["empty", "pending", "parsed"]),
  parse_source: z.enum(["llm", "template", "user"]).nullable(),
  understanding: understandingSchema.nullable(),
  ai_consent_version: z.string().nullable(),
  ai_consent_at: z.string().nullable(),
  ai_consent_current: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Profile = z.infer<typeof profileSchema>;

export const authMethodsSchema = z.object({
  email_code: z.boolean(),
  google: z.boolean(),
  google_domains: z.array(z.string()),
});
export type AuthMethods = z.infer<typeof authMethodsSchema>;

export const googleStartSchema = z.object({ authorization_url: z.string().url() });

export const intentSchema = z.enum([
  "build_together",
  "skill_exchange",
  "interest_buddy",
  "accountability",
  "mentor",
  "explore",
]);

export const matchRequestSchema = z.object({
  id: z.string(),
  text: z.string(),
  requested_intent: intentSchema.nullable(),
  intent: intentSchema.nullable(),
  status: z.enum(["pending", "ready", "closed", "expired"]),
  match_count: z.number(),
  created_at: z.string(),
  matched_at: z.string().nullable(),
  expires_at: z.string(),
});
export type MatchRequest = z.infer<typeof matchRequestSchema>;

export const matchRequestPageSchema = z.object({
  items: z.array(matchRequestSchema),
  next_cursor: z.string().nullable(),
});

export const matchSchema = z.object({
  id: z.string(),
  rank: z.number(),
  reason: z.string(),
  status: z.enum(["shown", "viewed", "intro_sent", "accepted", "declined", "expired"]),
  candidate: z.object({
    user_id: z.string(),
    summary: z.string(),
    offers: z.array(z.string()),
    seeks: z.array(z.string()),
    interests: z.array(z.string()),
    availability: z.string(),
    languages: z.array(z.string()),
  }),
});
export type Match = z.infer<typeof matchSchema>;

export const matchListSchema = z.object({ items: z.array(matchSchema) });

export const personSchema = z.object({
  user_id: z.string(),
  display_name: z.string().nullable(),
  links: z.array(z.string()).nullable(),
  summary: z.string(),
  offers: z.array(z.string()),
  seeks: z.array(z.string()),
  interests: z.array(z.string()),
  availability: z.string(),
  languages: z.array(z.string()),
});
export type Person = z.infer<typeof personSchema>;

export const introSchema = z.object({
  id: z.string(),
  direction: z.enum(["received", "sent"]),
  status: z.enum(["pending", "accepted", "declined", "withdrawn", "expired"]),
  note: z.string(),
  request_text: z.string(),
  reason: z.string(),
  person: personSchema,
  created_at: z.string(),
  expires_at: z.string(),
  responded_at: z.string().nullable(),
});
export type Intro = z.infer<typeof introSchema>;

export const introPageSchema = z.object({
  items: z.array(introSchema),
  next_cursor: z.string().nullable(),
});

export const connectionSchema = z.object({
  id: z.string(),
  created_at: z.string(),
  person: personSchema,
  unread_messages: z.number(),
  last_message_at: z.string().nullable(),
});
export type Connection = z.infer<typeof connectionSchema>;

export const connectionListSchema = z.object({ items: z.array(connectionSchema) });
export type ConnectionList = z.infer<typeof connectionListSchema>;

export const messageSchema = z.object({
  id: z.string(),
  connection_id: z.string(),
  sender_id: z.string(),
  body: z.string(),
  created_at: z.string(),
});
export type Message = z.infer<typeof messageSchema>;

/** One conversation, newest first (ADR 0012). */
export const messagePageSchema = z.object({
  items: z.array(messageSchema),
  next_cursor: z.string().nullable(),
  retention_days: z.number(),
});
export type MessagePage = z.infer<typeof messagePageSchema>;

/** New messages in all conversations since a cursor, oldest first; may repeat recent ones. */
export const messageUpdatesSchema = z.object({
  items: z.array(messageSchema),
  cursor: z.string(),
  has_more: z.boolean(),
  poll_after_seconds: z.number().nullable(),
});
export type MessageUpdates = z.infer<typeof messageUpdatesSchema>;

export const notificationSchema = z.object({
  id: z.string(),
  kind: z.enum(["intro_received", "intro_accepted", "matches_ready"]),
  intro_id: z.string().nullable(),
  request_id: z.string().nullable(),
  read_at: z.string().nullable(),
  created_at: z.string(),
});
export type AppNotification = z.infer<typeof notificationSchema>;

export const notificationPageSchema = z.object({
  items: z.array(notificationSchema),
  next_cursor: z.string().nullable(),
  unread: z.number(),
});

export const unreadCountSchema = z.object({ unread: z.number() });
export const markedReadSchema = z.object({ marked: z.number() });

/** Someone you blocked: no name or links (ARCHITECTURE.md §8). */
export const blockedSchema = z.object({
  user_id: z.string(),
  created_at: z.string(),
  person: personSchema,
});
export type Blocked = z.infer<typeof blockedSchema>;

export const blockListSchema = z.object({ items: z.array(blockedSchema) });
