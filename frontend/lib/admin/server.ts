import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";
import type { z } from "zod";

import { apiRequest } from "@/lib/api/client";

import {
  adminMeSchema,
  auditPageSchema,
  permissionTableSchema,
  teamSchema,
  twoStepStatusSchema,
  userDetailSchema,
  userPageSchema,
  appealPageSchema,
  blockStatsSchema,
  caseSchema,
  queueSchema,
} from "./schemas";

async function adminGet<T extends z.ZodType>(path: string, schema: T): Promise<z.infer<T>> {
  return apiRequest(`/api/v1/admin${path}`, schema, {
    headers: { cookie: (await cookies()).toString() },
  });
}

export const getTwoStepStatus = () => adminGet("/two-step", twoStepStatusSchema);
/** Cached per request: the layout and the page both ask. */
export const getAdminMe = cache(() => adminGet("/me", adminMeSchema));
export const getPermissionTable = () => adminGet("/permissions", permissionTableSchema);
export const getTeam = () => adminGet("/team", teamSchema);
export const getAudit = () => adminGet("/audit?limit=50", auditPageSchema);

/** One page of the Users list; ``params`` are the page's own query (q, status, ...). */
export const getUsers = (params: URLSearchParams) =>
  adminGet(`/users?${params.toString()}`, userPageSchema);
export const getUserDetail = (id: string) =>
  adminGet(`/users/${encodeURIComponent(id)}`, userDetailSchema);

export const getQueue = (status: string) =>
  adminGet(`/safety/reports?status=${encodeURIComponent(status)}`, queueSchema);
export const getCase = (id: string) =>
  adminGet(`/safety/reports/${encodeURIComponent(id)}`, caseSchema);
export const getAppeals = () => adminGet("/safety/appeals?status=open", appealPageSchema);
export const getBlockStats = () => adminGet("/safety/blocks", blockStatsSchema);
