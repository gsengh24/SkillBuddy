import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PlaceholderPage } from "@/components/shell/placeholder-page";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Messages" };
export const dynamic = "force-dynamic";

export default async function MessagesPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/messages");
  return (
    <PlaceholderPage
      title="Messages"
      intro="Conversations with people you agreed to meet will appear here."
    />
  );
}
