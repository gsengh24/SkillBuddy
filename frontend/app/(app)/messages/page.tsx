import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { personHue } from "@/lib/design/color";
import { getConnections } from "@/lib/social/server";

export const metadata: Metadata = { title: "Messages" };
export const dynamic = "force-dynamic";

/** People you're connected with. Chat comes in the next step. */
export default async function MessagesPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/messages");
  const connections = await getConnections();

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1">Messages</h1>
        <p className="text-muted">
          People you&apos;re connected with. Chat opens soon; for now, use the links they shared.
        </p>
      </header>
      {connections.items.length ? (
        <ul className="flex flex-col gap-4">
          {connections.items.map(({ id, person }) => (
            <li key={id}>
              <Card className="flex flex-col gap-3">
                <h2 className="text-body text-ink font-bold">
                  {person.display_name ?? "Your connection"}
                </h2>
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
