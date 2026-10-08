import type { Metadata } from "next";

import { Panel } from "@/components/ds/surfaces";
import { AccountActions } from "@/components/auth/account-actions";
import { EmailToggle } from "@/components/profile/email-toggle";
import { TextLink } from "@/components/ui/text-link";
import { withUser } from "@/lib/auth/with-user";
import { getMyProfile } from "@/lib/profile/server";

export const metadata: Metadata = { title: "Account settings" };
export const dynamic = "force-dynamic";

export default async function AccountSettingsPage() {
  const { user, data: profile } = await withUser("/login?next=/settings/account", getMyProfile());

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-headline lg:text-headline-lg">Account settings</h1>
        <p className="text-muted">
          Signed in as <strong className="text-ink break-all">{user.email}</strong>
        </p>
      </header>
      <section aria-labelledby="emails-h" className="flex flex-col gap-3">
        <h2
          id="emails-h"
          className="font-display tracking-display text-[20px] leading-tight font-extrabold"
        >
          Emails
        </h2>
        <Panel className="flex flex-col gap-2">
          {profile ? (
            <EmailToggle initial={profile.email_notifications} />
          ) : (
            <p className="text-meta-lg text-muted">
              Once you create your profile, we&apos;ll email you when someone sends you an intro or
              accepts yours. You can turn that off here.
            </p>
          )}
          <p className="text-meta-lg text-muted">
            Sign-in codes are always emailed when you ask for one.
          </p>
        </Panel>
      </section>
      <p className="flex flex-wrap gap-x-6 gap-y-2">
        <TextLink href="/settings/blocked">Blocked people</TextLink>
        {user.is_moderator ? <TextLink href="/moderation">Moderation</TextLink> : null}
      </p>
      <AccountActions />
    </div>
  );
}
