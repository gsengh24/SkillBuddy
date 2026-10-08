import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ButtonLink } from "@/components/ds/button";
import { Panel } from "@/components/ds/surfaces";
import { UnderstandingReview } from "@/components/profile/understanding-review";
import { VisibilityToggle } from "@/components/profile/visibility-toggle";
import { Overline } from "@/components/ui/overline";
import { YouPage, YouWithoutProfile } from "@/components/you/you-page";
import { withUser } from "@/lib/auth/with-user";
import { getDataExports, getSessions } from "@/lib/account/server";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "You" };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ welcome?: string; review?: string }> };

/**
 * You: profile and account settings in one page (design spec section 13). The session,
 * the profile, the devices and the data requests load together. `?welcome=1` (onboarding step 2) and `?review=1` show what
 * was understood from the description, to check and correct it.
 */
export default async function You({ searchParams }: Props) {
  const [{ user, data }, { welcome, review }] = await Promise.all([
    withUser("/login?next=/you", Promise.all([getMyProfile(), getSessions(), getDataExports()])),
    searchParams,
  ]);
  const [profile, sessions, exports] = data;
  const account = {
    email: user.email,
    termsVersion: user.terms_version,
    isModerator: user.is_moderator,
    status: user.status,
    sessions: sessions.items,
    exports: exports.items,
  };
  if (!profile) {
    // Onboarding's step 2 and the review need a profile; the account sections don't.
    if (welcome || review) redirect("/onboarding");
    return <YouWithoutProfile {...account} />;
  }

  if (welcome || review) {
    return (
      <div className="flex max-w-2xl flex-col gap-6">
        <header className="flex flex-col gap-2">
          {welcome ? <Overline tone="green">Step 2 of 2</Overline> : null}
          <h1 className="text-headline lg:text-headline-lg">What we understood</h1>
          <p className="text-muted">
            {welcome
              ? "Check what we understood. Matches use this, so fix anything that's off."
              : "What matches see about you, and how we read it."}
          </p>
        </header>
        <UnderstandingReview key={profile.updated_at} initial={profile} />
        <Panel>
          <VisibilityToggle initial={profile.visibility} />
        </Panel>
        <ButtonLink href="/you" variant="outline" className="self-start">
          {welcome ? "Continue to your profile" : "Back to your profile"}
        </ButtonLink>
      </div>
    );
  }

  return <YouPage profile={profile} account={account} />;
}
