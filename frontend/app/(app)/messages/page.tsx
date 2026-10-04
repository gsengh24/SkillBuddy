import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { BlockButton } from "@/components/safety/block-button";
import { ReportButton } from "@/components/safety/report-button";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { personHue } from "@/lib/design/color";
import { getConnections } from "@/lib/social/server";

export const metadata: Metadata = { title: "Messages" };
export const dynamic = "force-dynamic";

/** People you're connected with, each with a link to your chat. */
export default async function MessagesPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/messages");
  const connections = await getConnections();

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1">Messages</h1>
        <p className="text-muted">
          People you&apos;re connected with. Only the two of you can read your chat.
        </p>
      </header>
      {connections.items.length ? (
        <ul className="flex flex-col gap-4">
          {connections.items.map(({ id, person, unread_messages }) => (
            <li key={id}>
              <Card className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <h2 className="text-body text-ink font-bold break-words">
                    {person.display_name ?? "Your connection"}
                  </h2>
                  <Badge count={unread_messages} label="unread messages" />
                </div>
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
                <div className="flex flex-wrap items-start gap-3">
                  <ButtonLink href={`/messages/${id}`}>Open chat</ButtonLink>
                  <ButtonLink href={`/spaces/${id}`}>Open pair space</ButtonLink>
                  <ReportButton
                    kind="profile"
                    targetId={person.user_id}
                    blockUserId={person.user_id}
                    blockName={person.display_name ?? "this person"}
                  />
                  <BlockButton
                    userId={person.user_id}
                    name={person.display_name ?? "this person"}
                  />
                </div>
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted">
          No connections yet. When someone accepts your intro (or you accept theirs), they&apos;ll
          appear here.
        </p>
      )}
    </div>
  );
}
