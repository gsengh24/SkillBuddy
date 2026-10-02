import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { Conversation } from "@/components/chat/conversation";
import { Card } from "@/components/ui/card";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { getConversation } from "@/lib/chat/server";
import { getConnections } from "@/lib/social/server";

export const metadata: Metadata = { title: "Chat" };
export const dynamic = "force-dynamic";

/** A conversation with one connection. Only the two people in it can open it. */
export default async function ConversationPage({
  params,
}: {
  params: Promise<{ connectionId: string }>;
}) {
  const { connectionId } = await params;
  const user = await getCurrentUser();
  if (!user) redirect(`/login?next=/messages/${encodeURIComponent(connectionId)}`);
  const connections = await getConnections();
  const connection = connections.items.find((item) => item.id === connectionId);
  if (!connection) notFound();
  const { page, cursor } = await getConversation(connectionId);
  const name = connection.person.display_name ?? "Your connection";

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <TextLink href="/messages" tone="muted" className="text-small self-start">
          All messages
        </TextLink>
        <h1 className="text-h1 break-words">{name}</h1>
      </header>
      <Card className="p-4 sm:p-6">
        <Conversation
          connectionId={connectionId}
          meId={user.id}
          otherId={connection.person.user_id}
          otherName={name}
          initial={page.items}
          cursor={cursor}
          retentionDays={page.retention_days}
          hasUnread={connection.unread_messages > 0}
        />
      </Card>
    </div>
  );
}
