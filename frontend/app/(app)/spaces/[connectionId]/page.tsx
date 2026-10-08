import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SpaceView } from "@/components/spaces/space-view";
import { SpacesPaused } from "@/components/spaces/spaces-paused";
import { ButtonLink } from "@/components/ds/button";
import { TextLink } from "@/components/ui/text-link";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getFeatures } from "@/lib/features";
import { getConnections } from "@/lib/social/server";
import { getSpace } from "@/lib/spaces/server";

export const metadata: Metadata = { title: "Pair space" };
export const dynamic = "force-dynamic";

/** A pair space with one connection. Only the two people in it can open it. */
export default async function SpacePage({ params }: { params: Promise<{ connectionId: string }> }) {
  const { connectionId } = await params;
  // The session, the connections and the space, all at once.
  const featuresCall = getFeatures();
  const spaceCall = startEarly(getSpace(connectionId));
  const { user, data: connections } = await withUser(
    `/login?next=/spaces/${encodeURIComponent(connectionId)}`,
    getConnections(),
  );
  const connection = connections.items.find((item) => item.id === connectionId);
  if (!connection) notFound();
  if (!(await featuresCall).features.pair_spaces) return <SpacesPaused />;
  const space = await spaceCall;
  const name = connection.person.display_name ?? "Your connection";

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <TextLink
          href="/spaces"
          tone="muted"
          className="text-meta-lg inline-flex min-h-11 items-center self-start"
        >
          All pair spaces
        </TextLink>
        <h1 className="text-headline lg:text-headline-lg break-words">You and {name}</h1>
        <p className="text-ink-2">Goals you share, skills you want to grow, and your progress.</p>
        <ButtonLink href={`/messages/${connectionId}`} variant="outline" className="self-start">
          Open chat
        </ButtonLink>
      </header>
      <SpaceView
        space={space}
        meId={user.id}
        otherId={connection.person.user_id}
        otherName={name}
      />
    </div>
  );
}
