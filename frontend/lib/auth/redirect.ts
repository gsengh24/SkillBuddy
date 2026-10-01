import { DEFAULT_SIGNED_IN_PATH } from "./constants";

/**
 * Only same-site relative paths are allowed after sign-in, so a crafted
 * `/login?next=https://evil.example` link cannot redirect elsewhere.
 */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) {
    return DEFAULT_SIGNED_IN_PATH;
  }
  if (raw.startsWith("/login") || raw.startsWith("/api/")) {
    return DEFAULT_SIGNED_IN_PATH;
  }
  return raw;
}
