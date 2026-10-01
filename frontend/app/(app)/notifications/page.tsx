import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PlaceholderPage } from "@/components/shell/placeholder-page";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Notifications" };
export const dynamic = "force-dynamic";

export default async function NotificationsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/notifications");
  return (
    <PlaceholderPage title="Notifications" intro="Introductions and replies will be listed here." />
  );
}
