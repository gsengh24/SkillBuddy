import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PlaceholderPage } from "@/components/shell/placeholder-page";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Saved" };
export const dynamic = "force-dynamic";

export default async function SavedPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/saved");
  return <PlaceholderPage title="Saved" intro="People you save for later will appear here." />;
}
