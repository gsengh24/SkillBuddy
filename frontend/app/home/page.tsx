import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth/session";
import { brand } from "@/lib/brand";

export const metadata: Metadata = { title: "Home" };
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/home");

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col gap-8 px-6 py-16">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm font-semibold tracking-wide text-indigo-600 uppercase">
          {brand.name}
        </p>
        <nav aria-label="Account">
          <Link href="/settings/account" className="text-sm text-slate-700 underline">
            Account settings
          </Link>
        </nav>
      </header>
      <section className="flex flex-col gap-3">
        <h1 className="text-3xl font-bold text-slate-900">Welcome</h1>
        <p className="text-slate-700">
          You&apos;re signed in as <strong className="break-all">{user.email}</strong>.
        </p>
        <p className="text-slate-600">
          This is a placeholder. Your profile and matches will appear here soon.
        </p>
      </section>
    </main>
  );
}
