import { redirect } from "next/navigation";

import { signedInLanding } from "@/lib/auth/landing";
import { getCurrentUser } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

/**
 * The default landing after sign-in (email code and Google; ADR 0022 "Landing after sign-in"):
 * it renders nothing and redirects, from the API's onboarding progress, to the steps, to step
 * 5, or Home. A sign-in with a deep link goes straight there instead and never comes here.
 */
export default async function StartPage(): Promise<never> {
  const user = await getCurrentUser().catch(() => null);
  if (!user) redirect("/login");
  redirect(await signedInLanding());
}
