import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { AIStatusView } from "@/components/moderation/ai-status";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { getAIStatus } from "@/lib/moderation/server";

export const metadata: Metadata = { title: "AI status" };
export const dynamic = "force-dynamic";

/** Which AI provider answered today: names and counts only. Moderators only. */
export default async function AIStatusPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/moderation/ai");
  if (!user.is_moderator) notFound();
  const status = await getAIStatus();

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <TextLink href="/moderation" tone="muted" className="text-small self-start">
          Moderation
        </TextLink>
        <h1 className="text-h1">AI status</h1>
        <p className="text-muted">
          Which AI provider answered today, and how often the template answered instead. Counts
          only: no keys, no messages, no user data.
        </p>
      </header>
      <AIStatusView status={status} />
    </div>
  );
}
