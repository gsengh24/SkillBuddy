import type { Metadata } from "next";
import Link from "next/link";

import { DraftNotice } from "@/components/legal/draft-notice";
import { brand } from "@/lib/brand";

export const metadata: Metadata = { title: "Terms (draft)" };

export default function TermsPage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-16 text-slate-800">
      <h1 className="text-3xl font-bold text-slate-900">{brand.name} Terms (draft)</h1>
      <DraftNotice />
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Who can use {brand.name}</h2>
        <p>You must be 18 or older. You confirm this when you create your account.</p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">What the service does</h2>
        <p>
          {brand.name} suggests people you might want to build, learn or talk with, and explains
          why. Nobody is contacted unless both people agree to the introduction.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Your responsibilities</h2>
        <p>
          Be honest in what you write, respect the people you meet, and do not use the service for
          spam, scams, harassment or anything unlawful. We may suspend accounts that do.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Ending your account</h2>
        <p>
          You can delete your account at any time from Account settings. It is permanently deleted
          30 days after you ask.
        </p>
      </section>
      <p>
        See also the{" "}
        <Link href="/privacy" className="text-indigo-700 underline">
          Privacy Policy (draft)
        </Link>
        .
      </p>
    </main>
  );
}
