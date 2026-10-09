import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { Conversation } from "@/components/chat/conversation";
import { MatchCard } from "@/components/discover/match-card";
import { AIStatusView } from "@/components/moderation/ai-status";
import { ReportReview } from "@/components/moderation/report-review";
import { IntroCard } from "@/components/social/intro-card";
import { SpaceView } from "@/components/spaces/space-view";
import type { AIStatus, Intro, Match, Message, ModerationReport, Space } from "@/lib/api/schemas";
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
  title: "UI designer for fintech apps",
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

const SPACE: Space = {
  connection_id: "sample-connection",
  goals: [
    {
      id: "sample-goal-1",
      title: "Ship the first version",
      status: "open",
      due_on: "2026-11-01",
      done_at: null,
      created_by: THEM,
      created_at: "2026-10-05T10:00:00Z",
    },
    {
      id: "sample-goal-2",
      title: "Pick a name",
      status: "done",
      due_on: null,
      done_at: "2026-10-06T10:00:00Z",
      created_by: ME,
      created_at: "2026-10-05T10:00:00Z",
    },
  ],
  skills: [
    { id: "sample-skill-1", name: "React", owner_id: ME, created_at: "2026-10-05T10:00:00Z" },
    { id: "sample-skill-2", name: "Figma", owner_id: THEM, created_at: "2026-10-05T10:00:00Z" },
  ],
  logs: [
    {
      id: "sample-log-1",
      note: "Drew the first screens.",
      author_id: THEM,
      goal_id: "sample-goal-1",
      skill_id: null,
      created_at: "2026-10-06T18:00:00Z",
    },
  ],
  retention_days: 90,
  max_goals: 30,
  max_skills_per_person: 10,
};

const REPORT: ModerationReport = {
  id: "sample-report-1",
  reason: "harassment",
  details: "Sample note from the person reporting.",
  status: "open",
  reporter_id: ME,
  reported_id: THEM,
  reported_status: "active",
  connection_id: "sample-connection",
  target: "message",
  target_id: "sample-message-2",
  messages: [
    {
      id: "sample-message-1",
      label: null,
      sender: "reporter",
      body: "Sample message.",
      sent_at: "2026-10-07T10:00:00Z",
    },
    {
      id: "sample-message-2",
      label: null,
      sender: "reported",
      body: "The sample reported message.",
      sent_at: "2026-10-07T10:01:00Z",
    },
  ],
  created_at: "2026-10-07T10:05:00Z",
  resolved_at: null,
  resolution_note: "",
};

const AI_STATUS: AIStatus = {
  enabled: true,
  providers: [
    {
      name: "groq",
      unit: "tokens",
      daily_budget: 400000,
      used_today: 1200,
      calls: { ok: 12 },
      probes: { ok: 1 },
    },
    {
      name: "cloudflare",
      unit: "neurons",
      daily_budget: 9000,
      used_today: 0,
      calls: {},
      probes: {},
    },
  ],
  fallbacks: { quota: 0 },
  global_calls_today: 12,
  global_cap: 2000,
};

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
      <Section id="screens-space" title="A pair space">
        <div className="max-w-3xl">
          <SpaceView space={SPACE} meId={ME} otherId={THEM} otherName="Aarav R." />
        </div>
      </Section>
      <Section id="screens-moderation" title="Moderation">
        <div className="flex max-w-3xl flex-col gap-6">
          <ReportReview report={REPORT} />
          <AIStatusView status={AI_STATUS} />
        </div>
      </Section>
    </main>
  );
}
