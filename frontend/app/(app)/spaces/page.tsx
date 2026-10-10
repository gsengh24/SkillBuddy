import type { Metadata } from "next";

import { Avatar } from "@/components/ds/avatar";
import { ButtonLink } from "@/components/ds/button";
import { SpacesPaused } from "@/components/spaces/spaces-paused";
import { withUser } from "@/lib/auth/with-user";
import { getFeatures } from "@/lib/features";
import { getConnections } from "@/lib/social/server";

export const metadata: Metadata = { title: "Pair spaces" };
export const dynamic = "force-dynamic";

/** Every connection has a pair space: pick one. */
export default async function SpacesPage() {
  const featuresCall = getFeatures();
  const { data: connections } = await withUser("/login?next=/spaces", getConnections());
  const { features } = await featuresCall;
  if (!features.pair_spaces) return <SpacesPaused />;

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-headline lg:text-headline-lg">Pair spaces</h1>
        <p className="text-ink-2">
          A space with each person you&apos;re connected with: shared goals, skills you want to
          grow, and progress notes. Only the two of you can see it.
        </p>
      </header>
      {features.teams ? (
        <div className="border-line flex flex-wrap items-center justify-between gap-3 border-y py-3">
          <p className="text-ink-2">Working with more than one person? Make a team of up to six.</p>
          <ButtonLink href="/teams" variant="outline" size="compact">
            Open teams
          </ButtonLink>
        </div>
      ) : null}
      {connections.items.length ? (
        <ul className="border-line border-t">
          {connections.items.map(({ id, person }) => {
            const name = person.display_name ?? "Your connection";
            return (
              <li key={id} className="border-line flex items-center gap-3 border-b py-3">
                <Avatar
                  userId={person.user_id}
                  name={name}
                  photoUrl={person.photo_url}
                  decorative
                />
                <div className="min-w-0 flex-1">
                  <h2 className="text-title truncate">{name}</h2>
                  {person.summary ? (
                    <p className="text-meta text-muted truncate">{person.summary}</p>
                  ) : null}
                </div>
                <ButtonLink href={`/spaces/${id}`} variant="outline" size="compact">
                  Open pair space
                </ButtonLink>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="flex flex-col items-start gap-3">
          <p className="text-muted">
            No connections yet. When someone accepts your intro (or you accept theirs), you get a
            pair space together.
          </p>
          <ButtonLink href="/home#new-request" variant="primary">
            Find people
          </ButtonLink>
        </div>
      )}
    </div>
  );
}
