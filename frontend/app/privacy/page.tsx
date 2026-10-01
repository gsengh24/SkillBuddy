import type { Metadata } from "next";
import Link from "next/link";

import { DraftNotice } from "@/components/legal/draft-notice";
import { brand } from "@/lib/brand";

export const metadata: Metadata = { title: "Privacy Policy (draft)" };

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-16 text-slate-800">
      <h1 className="text-3xl font-bold text-slate-900">{brand.name} Privacy Policy (draft)</h1>
      <DraftNotice />
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">What we collect</h2>
        <p>
          Your email address, so you can sign in with a one-time code, and the date you accepted the
          terms. We do not ask for your age or date of birth. For security we keep a short log of
          sign-in activity (with your IP address and browser), which is deleted after 90 days.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Cookies</h2>
        <p>
          We use two cookies, both required for signing in: a session cookie and a security (CSRF)
          cookie. We do not use advertising or tracking cookies.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">How matching uses your information</h2>
        <p>
          When matching launches, the text you write about yourself will be used to suggest people
          to you and you to them, partly with automated (AI) processing. You will see why each match
          was suggested.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Deleting your data</h2>
        <p>
          Deleting your account from Account settings signs you out everywhere and permanently
          removes your account and its data 30 days later.
        </p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold">Your rights</h2>
        <p>
          We intend to meet India&apos;s Digital Personal Data Protection Act 2023 and, for users in
          the EU and UK, the GDPR. Contact details for questions and requests will be added here
          before launch.
        </p>
      </section>
      <p>
        See also the{" "}
        <Link href="/terms" className="text-indigo-700 underline">
          Terms (draft)
        </Link>
        .
      </p>
    </main>
  );
}
