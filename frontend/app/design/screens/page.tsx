import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { Conversation } from "@/components/chat/conversation";
import { MatchCard } from "@/components/discover/match-card";
import { IntroCard } from "@/components/social/intro-card";
import type { Intro, Match, Message } from "@/lib/api/schemas";
import { isStyleGuideEnabled } from "@/lib/env";

export const metadata: Metadata = {
  title: "Screens",
  robots: { index: false, follow: false },
};

/*
 * The match, intro and chat screens with synthetic data, for review and screenshots (the
 * Smoke job captures this page at 390 and 1280px). Same flag as /design: development and
 * Vercel previews only. No real people; the buttons are live but this page has no session,
 * so nothing they send is accepted.
 */

const ME = "00000000-0000-4000-8000-00000000000a";
const THEM = "00000000-0000-4000-8000-00000000000b";

const CANDIDATE = {
  user_id: THEM,
  summary: "Final-year design student who likes fintech.",
  offers: ["UI design", "Figma", "User research"],
  seeks: ["A side project"],
  interests: ["Personal finance", "Chess"],
  availability: "Weekends",
  languages: ["English", "Hindi"],
};

const MATCHES: Match[] = [
  {
    id: "sample-match-1",
    rank: 1,
    reason: "They design mobile apps and want a side project; you need a design eye.",
    status: "shown",
    candidate: CANDIDATE,
  },
  {
    id: "sample-match-2",
    rank: 2,
    reason: "You both care about personal finance tools.",
    status: "intro_sent",
    candidate: { ...CANDIDATE, user_id: "00000000-0000-4000-8000-00000000000c" },
  },
];

const INTRO: Intro = {
  id: "sample-intro-1",
  direction: "received",
  status: "pending",
  note: "Hi! I'm building a budgeting app and would love your design eye.",
  request_text: "A designer for my budgeting app",
  reason: "You design mobile apps; they're building one.",
  person: { ...CANDIDATE, display_name: null, links: null },
  created_at: "2026-10-07T10:00:00Z",
  expires_at: "2026-10-14T10:00:00Z",
  responded_at: null,
};

const MESSAGES: Message[] = [
  ["m3", THEM, "Happy to look at your wireframes.", "2026-10-07T10:12:00Z"],
  [
    "m2",
    ME,
    "Hi Aarav, I'm building a budgeting app and would love your design eye.",
    "2026-10-07T10:05:00Z",
  ],
  ["m1", THEM, "Thanks for the intro!", "2026-10-07T10:01:00Z"],
].map(([id, sender, body, at]) => ({
  id: id as string,
  connection_id: "sample-connection",
  sender_id: sender as string,
  body: body as string,
  created_at: at as string,
}));

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <h2 id={id} className="text-section">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function ScreensPage() {
  if (!isStyleGuideEnabled()) notFound();
  return (
    <main className="max-w-content mx-auto flex w-full flex-col gap-10 px-4 py-8 lg:px-8">
      <h1 className="text-h1">Screens</h1>
      <Section id="screens-matches" title="Match cards">
        <ul className="grid gap-4 md:grid-cols-2">
          {MATCHES.map((match) => (
            <li key={match.id}>
              <MatchCard match={match} />
            </li>
          ))}
        </ul>
      </Section>
      <Section id="screens-intro" title="An intro you received">
        <div className="max-w-2xl">
          <IntroCard initial={INTRO} />
        </div>
      </Section>
      <Section id="screens-chat" title="A chat">
        <div className="max-w-2xl">
          <Conversation
            connectionId="sample-connection"
            meId={ME}
            otherId={THEM}
            otherName="Aarav R."
            initial={MESSAGES}
            cursor="sample-cursor"
            retentionDays={90}
            hasUnread={false}
          />
        </div>
      </Section>
    </main>
  );
}
