import type { Metadata } from "next";
import Link from "next/link";

import { DraftNotice } from "@/components/legal/draft-notice";
import { textLinkClasses } from "@/components/ui/text-link";
import { brand } from "@/lib/brand";

export const metadata: Metadata = { title: "Terms (draft)" };

export default function TermsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-12">
      <h1 className="text-h1">{brand.name} Terms (draft)</h1>
      <DraftNotice />
      <section className="flex flex-col gap-2">
        <h2 className="text-section">Who can use {brand.name}</h2>
        <p>
          You must be 18 or older to use the platform. You confirm this with a tick box when you
          create your account; we do not verify it.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-section">What the service does</h2>
        <p>
          {brand.name} suggests people you might want to build, learn or talk with, and explains
          why. Nobody is contacted unless both people agree to the introduction.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-section">Your responsibilities</h2>
        <p>
          Be honest in what you write, respect the people you meet, and do not use the service for
          spam, scams, harassment or anything unlawful. We may suspend accounts that do.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-section">Ending your account</h2>
        <p>
          You can delete your account at any time from Account settings. It is permanently deleted
          30 days after you ask.
        </p>
      </section>
      <p>
        See also the{" "}
        <Link href="/privacy" className={textLinkClasses()}>
          Privacy Policy (draft)
        </Link>
        .
      </p>
    </main>
  );
}
