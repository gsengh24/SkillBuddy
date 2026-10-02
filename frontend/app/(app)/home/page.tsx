import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { RequestCard } from "@/components/discover/request-card";
import { RequestComposer } from "@/components/discover/request-composer";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HeroPanel } from "@/components/ui/hero-panel";
import { Overline } from "@/components/ui/overline";
import { TextLink } from "@/components/ui/text-link";
import type { MatchRequest } from "@/lib/api/schemas";
import { getCurrentUser } from "@/lib/auth/session";
import { getMyRequests } from "@/lib/matching/server";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "Discover" };
export const dynamic = "force-dynamic";

/** Discover: ask for the kind of person you want to meet, and see who fits. */
export default async function HomePage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/home");
  const profile = await getMyProfile();
  const requests: MatchRequest[] = profile ? await getMyRequests().catch(() => []) : [];

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1">Discover</h1>
        <p className="text-muted">
          You&apos;re signed in as <strong className="text-ink break-all">{user.email}</strong>.
        </p>
      </header>

      {profile ? (
        <Card className="p-5 sm:p-6">
          <RequestComposer />
        </Card>
      ) : (
        <HeroPanel>
          <Overline tone="green">Start here</Overline>
          <p className="text-section max-w-md">Tell us about you</p>
          <p className="max-w-md">
            A few lines about what you do and what you&apos;re looking for. We use it to find people
            worth meeting.
          </p>
          <ButtonLink href="/onboarding" className="self-start">
            Create your profile
          </ButtonLink>
        </HeroPanel>
      )}

      {requests.length ? (
        <section aria-labelledby="your-requests" className="flex flex-col gap-8">
          <h2 id="your-requests" className="text-section">
            Your requests
          </h2>
          {requests.map((request) => (
            <RequestCard key={request.id} initial={request} />
          ))}
        </section>
      ) : profile ? (
        <p className="text-muted">
          Your matches will appear here: a few people, each with a reason they fit.
        </p>
      ) : null}

      <p>
        <TextLink href="/settings/account">Account settings</TextLink>
      </p>
    </div>
  );
}
