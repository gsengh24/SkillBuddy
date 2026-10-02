import { AppShell } from "@/components/shell/app-shell";
import { ApiError } from "@/lib/api/errors";
import { getCurrentUser } from "@/lib/auth/session";
import { profileCompleteness } from "@/lib/profile/limits";
import { getMyProfile } from "@/lib/profile/server";
import { getUnreadCount } from "@/lib/social/server";

/**
 * Signed-in pages share the app shell. Each page redirects signed-out visitors to the
 * login page itself (it knows its own path for ?next=), so without a user this layout
 * renders the page alone.
 */
export default async function SignedInLayout({ children }: { children: React.ReactNode }) {
  const user = await getCurrentUser();
  if (!user) return children;
  const [profile, unread] = await Promise.all([shellProfile(), getUnreadCount()]);
  return (
    <AppShell
      user={{ id: user.id, email: user.email }}
      profileComplete={profileCompleteness(profile)}
      hasNotifications={unread > 0}
    >
      {children}
    </AppShell>
  );
}

/**
 * The profile for the shell's progress card. A server error (5xx) must not take down the
 * shell: pages that need the profile call it again (cached, so the same failure) and show
 * error.tsx inside the shell. Everything else is unchanged: getMyProfile already turns
 * 401 and 404 into null, and any other failure still throws.
 */
async function shellProfile() {
  try {
    return await getMyProfile();
  } catch (error) {
    if (error instanceof ApiError && error.status >= 500) return null;
    throw error;
  }
}
