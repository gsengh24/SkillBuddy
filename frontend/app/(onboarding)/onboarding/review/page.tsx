import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ProfileCheck } from "@/components/onboarding/profile-check";
import { isOnboarded } from "@/lib/api/schemas";
import { getCurrentUser } from "@/lib/auth/session";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "Check your profile" };
export const dynamic = "force-dynamic";

/**
 * Onboarding step 5 (ADR 0022, mockup 05): check the card others will see and the about
 * text written from the picks. Until step 4 is finished there is nothing to check yet.
 */
export default async function ReviewPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/onboarding/review");
  const profile = await getMyProfile();
  if (!profile?.about_text) redirect("/onboarding?step=about");
  if (isOnboarded(profile)) redirect("/home");
  return <ProfileCheck />;
}
