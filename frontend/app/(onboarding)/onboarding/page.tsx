import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { OnboardingFlow, DESCRIBE_PATH } from "@/components/onboarding/onboarding-flow";
import { getCurrentUser } from "@/lib/auth/session";
import { getOnboarding } from "@/lib/onboarding/server";

export const metadata: Metadata = { title: "Set up your profile" };
export const dynamic = "force-dynamic";

/**
 * Onboarding steps 1–4 (ADR 0022). Finished profiles go to You; once every step is saved or
 * skipped, the person describes themselves on the next page (until step 5 replaces it).
 */
export default async function OnboardingPage({
  searchParams,
}: {
  searchParams: Promise<{ step?: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/onboarding");
  const [progress, { step }] = await Promise.all([getOnboarding(), searchParams]);
  if (progress.completed_at !== null) redirect("/you");
  if (progress.next_step === "review" && step === undefined) redirect(DESCRIBE_PATH);
  return <OnboardingFlow initial={progress} requested={step ?? null} />;
}
