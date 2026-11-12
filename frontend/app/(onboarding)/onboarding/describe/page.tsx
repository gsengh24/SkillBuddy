import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Logo } from "@/components/ds/logo";
import { ProfileForm } from "@/components/profile/profile-form";
import { Overline } from "@/components/ui/overline";
import { isOnboarded } from "@/lib/api/schemas";
import { getCurrentUser } from "@/lib/auth/session";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "Create your profile" };
export const dynamic = "force-dynamic";

/**
 * After steps 1–4: describe yourself in your own words, with the AI consent line, exactly
 * as before (ADR 0022 keeps it until step 5 replaces this page). Saving finishes onboarding.
 */
export default async function DescribePage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/onboarding/describe");
  const profile = await getMyProfile();
  if (isOnboarded(profile)) redirect("/you");

  return (
    <div className="bg-bg min-h-dvh">
      <header className="px-4 py-3.5 lg:px-8 lg:py-6">
        <Logo />
      </header>
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 pt-2 pb-12 lg:pt-8">
        <header className="flex flex-col gap-2">
          <Overline tone="green">Last step</Overline>
          <h1 className="text-headline lg:text-headline-lg">Tell us about you</h1>
          <p className="text-muted">
            Write it the way you&apos;d say it to a friend. Next, you&apos;ll check what we
            understood and fix anything we got wrong.
          </p>
        </header>
        <ProfileForm profile={profile} mode="onboarding" />
      </main>
    </div>
  );
}
