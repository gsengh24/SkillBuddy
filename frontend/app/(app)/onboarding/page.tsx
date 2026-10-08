import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ProfileForm } from "@/components/profile/profile-form";
import { Overline } from "@/components/ui/overline";
import { getCurrentUser } from "@/lib/auth/session";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "Create your profile" };
export const dynamic = "force-dynamic";

/** First-run: describe yourself in your own words. Existing profiles go to /profile. */
export default async function OnboardingPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/onboarding");
  const profile = await getMyProfile();
  if (profile) redirect("/profile");

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <Overline tone="green">Step 1 of 2</Overline>
        <h1 className="text-headline lg:text-headline-lg">Tell us about you</h1>
        <p className="text-muted">
          Write it the way you&apos;d say it to a friend. Next, you&apos;ll check what we understood
          and fix anything we got wrong.
        </p>
      </header>
      <ProfileForm profile={null} mode="onboarding" />
    </div>
  );
}
