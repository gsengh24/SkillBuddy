import "server-only";

import { getOnboarding } from "@/lib/onboarding/server";
import { HOME_PATH, landingFor } from "@/lib/onboarding/landing";

/**
 * Where to land after sign-in when no deep link was given, from the API's onboarding
 * progress. Any failure goes Home: never an error page or a sign-in loop.
 */
export async function signedInLanding(): Promise<string> {
  try {
    return landingFor(await getOnboarding());
  } catch {
    return HOME_PATH;
  }
}
