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
