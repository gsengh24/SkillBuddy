import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Conversation } from "@/components/chat/conversation";
import { Avatar } from "@/components/ds/avatar";
import { ButtonLink } from "@/components/ds/button";
import { MoreMenu } from "@/components/ds/more-menu";
import { BlockButton } from "@/components/safety/block-button";
import { ReportButton } from "@/components/safety/report-button";
import { TextLink } from "@/components/ui/text-link";
import { startEarly, withUser } from "@/lib/auth/with-user";
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
  // Three things at once: the session, the connections and the conversation. The
  // conversation keeps its own order (polling cursor first, then the messages).
  const conversation = startEarly(getConversation(connectionId));
  const { user, data: connections } = await withUser(
    `/login?next=/messages/${encodeURIComponent(connectionId)}`,
    getConnections(),
  );
  const connection = connections.items.find((item) => item.id === connectionId);
  if (!connection) notFound();
  const { page, cursor } = await conversation;
  const name = connection.person.display_name ?? "Your connection";

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <TextLink
          href="/home?filter=messages"
          tone="muted"
          className="text-meta-lg inline-flex min-h-11 items-center self-start"
        >
          All messages
        </TextLink>
        <div className="border-line flex flex-wrap items-center justify-between gap-3 border-b pb-4">
          <div className="flex min-w-0 items-center gap-3">
            <Avatar userId={connection.person.user_id} name={name} decorative />
            <div className="min-w-0">
              <h1 className="text-title lg:text-title-lg font-sans break-words">{name}</h1>
              <p className="text-meta text-muted">Connected</p>
            </div>
          </div>
          <div className="flex flex-wrap items-start gap-3">
            <ButtonLink href={`/spaces/${connectionId}`} variant="outline" size="compact">
              Open pair space
            </ButtonLink>
            <MoreMenu label={`More actions for ${name}`}>
              <ReportButton
                kind="profile"
                targetId={connection.person.user_id}
                attachFrom={connection.id}
                blockUserId={connection.person.user_id}
                blockName={connection.person.display_name ?? "this person"}
              />
              <BlockButton
                userId={connection.person.user_id}
                name={name}
                redirectTo="/home?filter=messages"
              />
            </MoreMenu>
          </div>
        </div>
      </header>
      <div>
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
      </div>
    </div>
  );
}
