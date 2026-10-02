import { AppShell } from "@/components/shell/app-shell";
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
  const [profile, unread] = await Promise.all([getMyProfile(), getUnreadCount()]);
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
