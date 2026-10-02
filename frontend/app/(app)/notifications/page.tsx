import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { IntroCard } from "@/components/social/intro-card";
import { NotificationList } from "@/components/social/notification-list";
import { getCurrentUser } from "@/lib/auth/session";
import { getNotifications, getReceivedIntros } from "@/lib/social/server";

export const metadata: Metadata = { title: "Notifications" };
export const dynamic = "force-dynamic";

/** Intros waiting for your answer, then everything else that happened. */
export default async function NotificationsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/notifications");
  const [intros, notifications] = await Promise.all([getReceivedIntros(), getNotifications()]);
  const waiting = intros.items.filter((intro) => intro.status === "pending");

  return (
    <div className="flex max-w-2xl flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1">Notifications</h1>
        <p className="text-muted">Intros waiting for your answer, and what happened lately.</p>
      </header>

      <section id="intros" aria-labelledby="intros-h" className="flex flex-col gap-4">
        <h2 id="intros-h" className="text-section">
          Intros for you
        </h2>
        {waiting.length ? (
          <ul className="flex flex-col gap-4">
            {waiting.map((intro) => (
              <li key={intro.id}>
                <IntroCard initial={intro} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted">No intros waiting.</p>
        )}
      </section>

      <section aria-labelledby="activity-h" className="flex flex-col gap-4">
        <h2 id="activity-h" className="text-section">
          Activity
        </h2>
        <NotificationList initial={notifications.items} unread={notifications.unread} />
      </section>
    </div>
  );
}
