import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/auth/session";
import { getConnections } from "@/lib/social/server";

export const metadata: Metadata = { title: "Pair spaces" };
export const dynamic = "force-dynamic";

/** Every connection has a pair space: pick one. */
export default async function SpacesPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/spaces");
  const connections = await getConnections();

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1">Pair spaces</h1>
        <p className="text-muted">
          A space with each person you&apos;re connected with: shared goals, skills you want to
          grow, and progress notes. Only the two of you can see it.
        </p>
      </header>
      {connections.items.length ? (
        <ul className="flex flex-col gap-4">
          {connections.items.map(({ id, person }) => (
            <li key={id}>
              <Card className="flex flex-col gap-3">
                <h2 className="text-body text-ink font-bold break-words">
                  {person.display_name ?? "Your connection"}
                </h2>
                {person.summary ? <p>{person.summary}</p> : null}
                <ButtonLink href={`/spaces/${id}`} className="self-start">
                  Open pair space
                </ButtonLink>
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted">
          No connections yet. When someone accepts your intro (or you accept theirs), you get a pair
          space together.
        </p>
      )}
    </div>
  );
}
