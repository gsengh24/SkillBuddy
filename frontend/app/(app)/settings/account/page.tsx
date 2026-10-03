import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AccountActions } from "@/components/auth/account-actions";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Account settings" };
export const dynamic = "force-dynamic";

export default async function AccountSettingsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/settings/account");

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1">Account settings</h1>
        <p className="text-muted">
          Signed in as <strong className="text-ink break-all">{user.email}</strong>
        </p>
      </header>
      <p className="flex flex-wrap gap-x-6 gap-y-2">
        <TextLink href="/settings/blocked">Blocked people</TextLink>
        {user.is_moderator ? <TextLink href="/moderation">Moderation</TextLink> : null}
      </p>
      <AccountActions />
    </div>
  );
}
