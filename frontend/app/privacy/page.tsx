import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { DraftNotice } from "@/components/legal/draft-notice";
import { textLinkClasses } from "@/components/ui/text-link";
import { brand } from "@/lib/brand";
import { legal, retention } from "@/lib/legal";

export const metadata: Metadata = { title: "Privacy Policy (draft)" };

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

function Mail() {
  return (
    <a href={`mailto:${legal.contactEmail}`} className={textLinkClasses()}>
      {legal.contactEmail}
    </a>
  );
}

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-12">
      <h1 className="text-h1">{brand.name} Privacy Policy (draft)</h1>
      <p className="text-small text-muted">
        Last updated {legal.updated} (version {legal.version}).
      </p>
      <DraftNotice />

      <Section id="contact" title="Who to contact">
        <p>
          For questions about your data, requests (see &quot;Your rights&quot;) or complaints, email{" "}
          <Mail />.
        </p>
      </Section>

      <Section id="collect" title="What we collect">
        <ul className="flex list-disc flex-col gap-1 pl-5">
          <li>
            <strong>Your account:</strong> your email address, how you sign in (an email code or
            Google), and the date you confirmed you are 18 or older and accepted the terms.
          </li>
          <li>
            <strong>Your profile:</strong> your display name, what you write about yourself, links,
            languages, time zone, and what we understood from your description (skills, interests,
            goals, availability), which you can correct.
          </li>
          <li>
            <strong>Matching:</strong> what you ask for on Discover, the people we suggested and
            why, and intros you send or receive (with your note).
          </li>
          <li>
            <strong>Chat:</strong> the messages you send to people you are connected with.
          </li>
          <li>
            <strong>Safety:</strong> the people you block, reports you make, and copies kept with
            reports about you (see &quot;Reports, blocks and moderation&quot;).
          </li>
          <li>
            <strong>Security and running the service:</strong> a log of sign-in activity (with your
            IP address and browser), and a record of emails we send you (the time and a scrambled
            form of your address, not the email itself).
          </li>
        </ul>
      </Section>

      <Section id="ai" title="How we use AI to match you">
        <p>
          Matching is automated. When you write or change your profile, our servers turn your
          description into numbers (an &quot;embedding&quot;) that let us find people with related
          skills and interests. This step runs on our own servers.
        </p>
        <p>
          To understand your description, choose your best matches and explain each suggestion, we
          also send text to an AI provider: currently Groq, Inc., with Cloudflare, Inc. as a backup.
          We send your description with email addresses, phone numbers, links, social handles and
          your name removed. When someone else asks for matches, a short summary of your profile
          (skills, interests, goals and availability, without your name or contact details) may be
          sent so the AI can compare candidates. We never send your name, email address or contact
          details.
        </p>
        <p>
          These providers process the text only to return a result to us. Their terms don&apos;t
          allow them to use it to train AI models. We have asked Groq not to retain it.
        </p>
        <p>
          We keep the results (your structured profile, your matches and the reasons shown), but not
          the messages exchanged with the AI provider. If the AI service is unavailable, we suggest
          matches using our own scoring and a simpler explanation.
        </p>
        <p>
          Suggestions are only suggestions: nobody can contact you unless you both agree. Deleting
          your account deletes your profile, its embeddings and your matches (see &quot;Deleting
          your data&quot;).
        </p>
        <p>We don&apos;t use AI to read your chat messages.</p>
      </Section>

      <Section id="who-sees" title="Who can see what">
        <ul className="flex list-disc flex-col gap-1 pl-5">
          <li>
            When you are suggested to someone, or send them an intro, they see your summary, skills,
            interests and availability, and why you were matched, but not your name or links.
          </li>
          <li>Your name and links are shown only to people you are connected with.</li>
          <li>Nobody can contact you unless you both agree to the introduction.</li>
          <li>We don&apos;t sell your data or show you advertising.</li>
        </ul>
      </Section>

      <Section id="messages" title="Chat messages">
        <p>
          Only you and the person you&apos;re talking to can read your chat. We don&apos;t use AI to
          read it. Each message is deleted {retention.messageDays} days after it&apos;s sent, and
          the whole conversation is deleted if either of you deletes your account.
        </p>
      </Section>

      <Section id="reports" title="Reports, blocks and moderation">
        <p>
          You can report a message, an intro or a profile. If a message is reported, we keep a copy
          of it and the 10 before it so our moderator can review it. For an intro we keep its
          request and note; for a profile, what the person reporting could see. Only the moderator
          sees this copy. It is deleted {retention.reportDaysAfterResolve} days after the report is
          resolved, even if the account or the original messages were deleted sooner. The reported
          person isn&apos;t told who reported them.
        </p>
        <p>
          If you block someone, neither of you can message the other, and you won&apos;t be
          suggested to each other. They aren&apos;t told. We keep the block until you remove it or
          one of you deletes your account.
        </p>
        <p>
          Our moderator can suspend accounts that break the{" "}
          <Link href="/terms" className={textLinkClasses()}>
            terms
          </Link>
          . We keep a record of each moderation action (who did what and when, without message text)
          for {retention.moderationLogDays} days.
        </p>
      </Section>

      <Section id="emails" title="Emails we send">
        <ul className="flex list-disc flex-col gap-1 pl-5">
          <li>Sign-in codes, whenever you ask for one.</li>
          <li>
            We email you when someone sends you an intro or accepts yours. This is on when you
            create your profile; turn it off in Settings (Account settings, Emails). You&apos;ll
            still see intros in Notifications.
          </li>
        </ul>
        <p>Our emails never name the other person or include message text.</p>
      </Section>

      <Section id="cookies" title="Cookies">
        <p>
          We use two cookies, both required for signing in: a session cookie and a security (CSRF)
          cookie. We do not use advertising or tracking cookies.
        </p>
      </Section>

      <Section id="retention" title="How long we keep things">
        <ul className="flex list-disc flex-col gap-1 pl-5">
          <li>Sign-in activity log: {retention.signInLogDays} days.</li>
          <li>
            What you ask for on Discover, with its suggestions and intros:{" "}
            {retention.matchRequestDays} days.
          </li>
          <li>Notifications: {retention.notificationDays} days.</li>
          <li>Chat messages: {retention.messageDays} days after each is sent.</li>
          <li>
            Report copies: {retention.reportDaysAfterResolve} days after the report is resolved.
          </li>
          <li>Moderation records: {retention.moderationLogDays} days.</li>
          <li>Records of emails sent: {retention.emailLogDays} days.</li>
          <li>
            Your account and profile: until you delete them (see below). Connections and blocks last
            until you remove them or delete your account.
          </li>
        </ul>
      </Section>

      <Section id="deleting" title="Deleting your data">
        <p>
          Deleting your account from Account settings signs you out everywhere and permanently
          removes your account, profile, embeddings, matches, intros, connections and messages{" "}
          {retention.deletionGraceDays} days later. The only exception is copies kept with a report
          (see{" "}
          <a href="#reports" className={textLinkClasses()}>
            Reports, blocks and moderation
          </a>
          ), which are deleted {retention.reportDaysAfterResolve} days after the report is resolved.
        </p>
      </Section>

      <Section id="providers" title="Services we use">
        <ul className="flex list-disc flex-col gap-1 pl-5">
          <li>Render (runs our servers, in Singapore) and Neon (our database, in Singapore).</li>
          <li>Vercel (serves the website).</li>
          <li>Google (sends our emails, and &quot;Sign in with Google&quot; if you use it).</li>
          <li>Groq and Cloudflare (AI processing, as described above).</li>
          <li>Cloudflare (runs our scheduled housekeeping).</li>
        </ul>
      </Section>

      <Section id="rights" title="Your rights">
        <p>
          We intend to meet India&apos;s Digital Personal Data Protection Act 2023 and, for users in
          the EU and UK, the GDPR. You can see and correct your profile in the app, delete your
          account at any time, and email <Mail /> to ask for a copy of your data or to raise a
          concern.
        </p>
      </Section>

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
