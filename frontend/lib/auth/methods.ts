import "server-only";

import { apiRequest } from "@/lib/api/client";
import { authMethodsSchema, type AuthMethods } from "@/lib/api/schemas";

const EMAIL_ONLY: AuthMethods = { email_code: true, google: false, google_domains: [] };

/** Which sign-in methods the API offers. If it can't be reached, show email codes only. */
export async function getAuthMethods(): Promise<AuthMethods> {
  try {
    return await apiRequest("/api/v1/auth/methods", authMethodsSchema);
  } catch {
    return EMAIL_ONLY;
  }
}
