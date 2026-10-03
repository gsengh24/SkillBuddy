import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { UnblockButton } from "@/components/safety/block-button";
import { Card } from "@/components/ui/card";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { getBlocks } from "@/lib/safety/server";

export const metadata: Metadata = { title: "Blocked people" };
export const dynamic = "force-dynamic";

/** People you've blocked. Their names aren't shown: blocking ended the connection. */
export default async function BlockedPeoplePage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/settings/blocked");
  const blocks = await getBlocks();

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <TextLink href="/settings/account" tone="muted" className="text-small self-start">
          Account settings
        </TextLink>
        <h1 className="text-h1">Blocked people</h1>
        <p className="text-muted">
          You and the people here can&apos;t message each other, send intros or be matched. They
          aren&apos;t told.
        </p>
      </header>
      {blocks.items.length ? (
        <ul className="flex flex-col gap-4">
          {blocks.items.map(({ user_id, created_at, person }) => (
            <li key={user_id}>
              <Card className="flex flex-col gap-3">
                <p className="text-ink font-bold">{person.summary || "Someone you blocked"}</p>
                <p className="text-small text-muted">
                  Blocked on{" "}
                  <time dateTime={created_at} suppressHydrationWarning>
                    {new Date(created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}
                  </time>
                </p>
                <UnblockButton userId={user_id} />
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted">You haven&apos;t blocked anyone.</p>
      )}
    </div>
  );
}
