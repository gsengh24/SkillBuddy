import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ProfileForm } from "@/components/profile/profile-form";
import { UnderstandingReview } from "@/components/profile/understanding-review";
import { VisibilityToggle } from "@/components/profile/visibility-toggle";
import { Card } from "@/components/ui/card";
import { Overline } from "@/components/ui/overline";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "About you" };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ welcome?: string }> };

/** "About you": what we understood (correctable), visibility, and the profile itself. */
export default async function ProfilePage({ searchParams }: Props) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/profile");
  const profile = await getMyProfile();
  if (!profile) redirect("/onboarding");
  const { welcome } = await searchParams;

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        {welcome ? <Overline tone="green">Step 2 of 2</Overline> : null}
        <h1 className="text-h1">About you</h1>
        <p className="text-muted">
          {welcome
            ? "Check what we understood. Matches use this, so fix anything that's off."
            : "What matches see about you, and how we read it."}
        </p>
      </header>

      <UnderstandingReview key={profile.updated_at} initial={profile} />

      <Card>
        <VisibilityToggle initial={profile.visibility} />
      </Card>

      <section aria-labelledby="edit-heading" className="flex flex-col gap-4">
        <h2 id="edit-heading" className="text-section">
          Your description
        </h2>
        <ProfileForm profile={profile} mode="edit" />
      </section>

      <p>
        <TextLink href="/settings/account">Account settings</TextLink>
      </p>
    </div>
  );
}
