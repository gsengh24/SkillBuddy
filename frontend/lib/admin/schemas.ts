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
