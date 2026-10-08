import { Conversation } from "@/components/chat/conversation";
import { Avatar } from "@/components/ds/avatar";
import { ButtonLink } from "@/components/ds/button";
import { MoreMenu } from "@/components/ds/more-menu";
import { BlockButton } from "@/components/safety/block-button";
import { ReportButton } from "@/components/safety/report-button";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import type { Connection, Message } from "@/lib/api/schemas";
import { personHue } from "@/lib/design/color";

/** Where to go after blocking from Home: the messages list. */
export const AFTER_BLOCK = "/home?filter=messages";

/**
 * A chat in Home's detail pane. The header has the person, "Open pair space" and a "⋯" menu
 * with Report and Block (the same components and wording the old Messages card had).
 * What the old card showed about the person (summary, offers, links once connected)
 * follows, then the conversation itself, unchanged.
 */
export function ChatDetail({
  connection,
  meId,
  page,
  cursor,
}: {
  connection: Connection;
  meId: string;
  page: { items: Message[]; retention_days: number };
  cursor: string;
}) {
  const { person } = connection;
  const name = person.display_name ?? "Your connection";
  return (
    <div className="flex flex-col gap-4">
      <header className="border-line flex flex-wrap items-center gap-3 border-b pb-4">
        <Avatar userId={person.user_id} name={name} decorative />
        <div className="min-w-0 flex-1">
          <h2 className="text-title lg:text-title-lg break-words">{name}</h2>
          <p className="text-meta text-muted">Connected</p>
        </div>
        <ButtonLink href={`/spaces/${connection.id}`} variant="outline" size="compact">
          Open pair space
        </ButtonLink>
        <MoreMenu label={`More actions for ${name}`}>
          <ReportButton
            kind="profile"
            targetId={person.user_id}
            attachFrom={connection.id}
            blockUserId={person.user_id}
            blockName={person.display_name ?? "this person"}
          />
          <BlockButton
            userId={person.user_id}
            name={person.display_name ?? "this person"}
            redirectTo={AFTER_BLOCK}
          />
        </MoreMenu>
      </header>

      <div className="flex flex-col gap-3">
        {person.summary ? <p>{person.summary}</p> : null}
        {person.offers.length ? (
          <ul className="flex flex-wrap gap-2" aria-label="Offers">
            {person.offers.map((item) => (
              <li key={item}>
                <Tag hue={personHue(person.user_id)}>{item}</Tag>
              </li>
            ))}
          </ul>
        ) : null}
        {person.links?.length ? (
          <ul className="flex flex-col gap-1" aria-label="Links">
            {person.links.map((link) => (
              <li key={link}>
                <TextLink href={link}>{link}</TextLink>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <Conversation
        connectionId={connection.id}
        meId={meId}
        otherId={person.user_id}
        otherName={name}
        initial={page.items}
        cursor={cursor}
        retentionDays={page.retention_days}
        hasUnread={connection.unread_messages > 0}
      />
    </div>
  );
}
