import "server-only";

import { cookies } from "next/headers";

import { apiRequest } from "@/lib/api/client";
import {
  connectionListSchema,
  introPageSchema,
  notificationPageSchema,
  unreadCountSchema,
} from "@/lib/api/schemas";

async function cookieHeader(): Promise<Record<string, string>> {
  return { cookie: (await cookies()).toString() };
}

export async function getReceivedIntros() {
  return apiRequest("/api/v1/intros?box=received&limit=30", introPageSchema, {
    headers: await cookieHeader(),
  });
}

export async function getNotifications() {
  return apiRequest("/api/v1/notifications?limit=30", notificationPageSchema, {
    headers: await cookieHeader(),
  });
}

export async function getConnections() {
  return apiRequest("/api/v1/connections", connectionListSchema, {
    headers: await cookieHeader(),
  });
}

/** Unread notifications for the bell; 0 if the API can't be reached. */
export async function getUnreadCount(): Promise<number> {
  try {
    const { unread } = await apiRequest("/api/v1/notifications/unread-count", unreadCountSchema, {
      headers: await cookieHeader(),
    });
    return unread;
  } catch {
    return 0;
  }
}
