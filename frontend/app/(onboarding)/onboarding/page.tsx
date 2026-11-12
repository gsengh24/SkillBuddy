import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { OnboardingFlow, REVIEW_PATH } from "@/components/onboarding/onboarding-flow";
import { getCurrentUser } from "@/lib/auth/session";
import { getOnboarding } from "@/lib/onboarding/server";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "Set up your profile" };
export const dynamic = "force-dynamic";

/**
 * Onboarding steps 1–4 (ADR 0022). Finished profiles go to You; once every step is saved or
 * skipped, the person checks their card on step 5.
 */
export default async function OnboardingPage({
  searchParams,
}: {
  searchParams: Promise<{ step?: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/onboarding");
  const [progress, profile, { step }] = await Promise.all([
    getOnboarding(),
    getMyProfile(),
    searchParams,
  ]);
  if (progress.completed_at !== null) redirect("/you");
  if (progress.next_step === "review" && step === undefined && profile?.about_text) {
    redirect(REVIEW_PATH);
  }
  return (
    <OnboardingFlow
      initial={progress}
      requested={step ?? (progress.next_step === "review" ? "about" : null)}
      needsConsent={!profile?.ai_consent_current}
    />
  );
}
