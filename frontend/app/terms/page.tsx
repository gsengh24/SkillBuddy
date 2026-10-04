import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { DraftNotice } from "@/components/legal/draft-notice";
import { textLinkClasses } from "@/components/ui/text-link";
import { brand } from "@/lib/brand";
import { legal, retention } from "@/lib/legal";

export const metadata: Metadata = { title: "Terms (draft)" };

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="flex scroll-mt-6 flex-col gap-2">
      <h2 id={`${id}-h`} className="text-section">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function TermsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-12">
      <h1 className="text-h1">{brand.name} Terms (draft)</h1>
      <p className="text-small text-muted">
        Last updated {legal.updated} (version {legal.version}).
      </p>
      <DraftNotice />

      <Section id="who" title={`Who can use ${brand.name}`}>
        <p>
          You must be 18 or older to use the platform. You confirm this with a tick box when you
          create your account; we do not verify it.
        </p>
      </Section>

      <Section id="service" title="What the service does">
        <p>
          {brand.name} suggests people you might want to build, learn or talk with, and explains
          why. Nobody is contacted unless both people agree to the introduction. Once you are
          connected, you can chat and share a pair space (goals, skills to grow and progress notes).
          Chat messages are deleted {retention.messageDays} days after they are sent, and progress
          notes {retention.spaceDays} days after they are written.
        </p>
      </Section>

      <Section id="conduct" title="How to behave">
        <p>
          Be honest in what you write and respect the people you meet. Don&apos;t use {brand.name}{" "}
          for anything unlawful, and in particular don&apos;t:
        </p>
        <ul className="flex list-disc flex-col gap-1 pl-5">
          <li>harass or bully anyone;</li>
          <li>send spam or advertising;</li>
          <li>run scams or ask people for money;</li>
          <li>send sexual or inappropriate content;</li>
          <li>threaten anyone, or put anyone&apos;s safety at risk;</li>
          <li>use the service if you are under 18.</li>
        </ul>
      </Section>

      <Section id="blocking" title="Blocking">
        <p>
          You can block anyone you have matched with, had an intro with or connected with. After a
          block, neither of you can message the other, your chat closes for both of you, and you
          won&apos;t be suggested to each other. They aren&apos;t told. You can unblock in Settings,
          but the old chat stays closed: to talk again, one of you needs to send a new intro.
        </p>
      </Section>

      <Section id="reporting" title="Reporting and moderation">
        <p>
          You can report a message, an intro, a profile, or a goal or note in a pair space. Our
          moderator reviews reports, using only the copy kept with each report, never whole
          conversations. We may suspend accounts that break these terms. A suspended account is
          signed out and can&apos;t sign in, be messaged or be suggested to anyone. How long report
          copies are kept is in the{" "}
          <Link href="/privacy#reports" className={textLinkClasses()}>
            Privacy Policy
          </Link>
          .
        </p>
      </Section>

      <Section id="ending" title="Ending your account">
        <p>
          You can delete your account at any time from Account settings. It is permanently deleted{" "}
          {retention.deletionGraceDays} days after you ask.
        </p>
      </Section>

      <Section id="changes" title="Changes and contact">
        <p>
          These terms will change before public launch. Questions:{" "}
          <a href={`mailto:${legal.contactEmail}`} className={textLinkClasses()}>
            {legal.contactEmail}
          </a>
          .
        </p>
      </Section>

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
