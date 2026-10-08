import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { UnsuspendButton } from "@/components/moderation/report-review";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { getSuspendedAccounts } from "@/lib/moderation/server";

export const metadata: Metadata = { title: "Suspended accounts" };
export const dynamic = "force-dynamic";

export default async function SuspendedAccountsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/moderation/suspended");
  if (!user.is_moderator) notFound();
  const accounts = await getSuspendedAccounts();

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <TextLink href="/moderation" tone="muted" className="text-meta-lg self-start">
          Moderation
        </TextLink>
        <h1 className="text-headline lg:text-headline-lg">Suspended accounts</h1>
        <p className="text-muted">
          These people can&apos;t sign in, can&apos;t be messaged and aren&apos;t shown in matches.
        </p>
      </header>
      {accounts.items.length ? (
        <ul className="border-line border-t">
          {accounts.items.map((account) => (
            <li key={account.user_id}>
              <div className="border-line flex flex-col gap-2 border-b py-3">
                <p className="text-ink font-bold">
                  {account.display_name ?? (account.person.summary || "No profile")}
                </p>
                <p className="text-meta-lg text-muted">
                  Account {account.user_id}
                  {account.suspended_at ? (
                    <>
                      {" · suspended "}
                      <time dateTime={account.suspended_at} suppressHydrationWarning>
                        {new Date(account.suspended_at).toLocaleDateString(undefined, {
                          dateStyle: "medium",
                        })}
                      </time>
                    </>
                  ) : null}
                </p>
                {account.note ? <p>Note: {account.note}</p> : null}
                <UnsuspendButton userId={account.user_id} />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted">No suspended accounts.</p>
      )}
    </div>
  );
}
