import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { AccountActions } from "@/components/auth/account-actions";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Account settings" };
export const dynamic = "force-dynamic";

export default async function AccountSettingsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/settings/account");

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col gap-8 px-6 py-16">
      <nav aria-label="Breadcrumb">
        <Link href="/home" className="text-sm text-slate-700 underline">
          Back to home
        </Link>
      </nav>
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold text-slate-900">Account settings</h1>
        <p className="text-slate-600">
          Signed in as <strong className="break-all">{user.email}</strong>
        </p>
      </header>
      <AccountActions />
    </main>
  );
}
