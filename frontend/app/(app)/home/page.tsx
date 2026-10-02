import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ButtonLink } from "@/components/ui/button";
import { HeroPanel } from "@/components/ui/hero-panel";
import { Overline } from "@/components/ui/overline";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "Home" };
export const dynamic = "force-dynamic";

/** Discover, for now a placeholder: the real screen comes in a later step. */
export default async function HomePage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/home");
  const profile = await getMyProfile();

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1">Welcome</h1>
        <p className="text-muted">
          You&apos;re signed in as <strong className="text-ink break-all">{user.email}</strong>.
        </p>
      </header>
      {profile ? null : (
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
      <HeroPanel>
        <Overline tone="green">Coming soon</Overline>
        <p className="text-section max-w-md">Your matches will appear here.</p>
        <p className="max-w-md">
          Describe what you want to do, and we will introduce you to a few people worth meeting.
        </p>
      </HeroPanel>
      <p>
        <TextLink href="/settings/account">Account settings</TextLink>
      </p>
    </div>
  );
}
