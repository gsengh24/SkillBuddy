import type { Metadata } from "next";
import Link from "next/link";

import { DraftNotice } from "@/components/legal/draft-notice";
import { textLinkClasses } from "@/components/ui/text-link";
import { brand } from "@/lib/brand";

export const metadata: Metadata = { title: "Privacy Policy (draft)" };

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-12">
      <h1 className="text-h1">{brand.name} Privacy Policy (draft)</h1>
      <DraftNotice />
      <section className="flex flex-col gap-2">
        <h2 className="text-section">What we collect</h2>
        <p>
          Your email address, so you can sign in with a one-time code, and the date you confirmed
          you are 18 or older and accepted the terms. For security we keep a short log of sign-in
          activity (with your IP address and browser), which is deleted after 90 days.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-section">Cookies</h2>
        <p>
          We use two cookies, both required for signing in: a session cookie and a security (CSRF)
          cookie. We do not use advertising or tracking cookies.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-section">How matching uses your information</h2>
        <p>
          When matching launches, the text you write about yourself will be used to suggest people
          to you and you to them, partly with automated (AI) processing. You will see why each match
          was suggested.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-section">Deleting your data</h2>
        <p>
          Deleting your account from Account settings signs you out everywhere and permanently
          removes your account and its data 30 days later.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-section">Your rights</h2>
        <p>
          We intend to meet India&apos;s Digital Personal Data Protection Act 2023 and, for users in
          the EU and UK, the GDPR. Contact details for questions and requests will be added here
          before launch.
        </p>
      </section>
      <p>
        See also the{" "}
        <Link href="/terms" className={textLinkClasses()}>
          Terms (draft)
        </Link>
        .
      </p>
    </main>
  );
}
