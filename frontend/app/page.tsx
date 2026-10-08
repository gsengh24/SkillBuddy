import type { Metadata } from "next";
import { Suspense } from "react";

import { ApiStatusFallback, ApiStatusIndicator } from "@/components/api-status";
import { Accordion } from "@/components/ds/accordion";
import { ButtonLink } from "@/components/ds/button";
import { CheckIcon, PeopleIcon } from "@/components/ds/icons";
import { FadeUp } from "@/components/ds/motion";
import { CtaBand, Footer, TopBar, TwoToneHeadline } from "@/components/ds/page-parts";
import { PixelPattern } from "@/components/ds/pixel-pattern";
import {
  HeroCell,
  HeroGrid,
  LabelChip,
  NumberedRows,
  Panel,
  TopicChip,
} from "@/components/ds/surfaces";
import { brand } from "@/lib/brand";

// The status block reflects the API right now, so never serve a cached render.
export const dynamic = "force-dynamic";

const TITLE = `${brand.displayName}: say what you're building, meet who can help`;
const DESCRIPTION =
  "Describe your goal in a sentence. We find people with the right skills, interests and intent, and tell you why.";

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    title: TITLE,
    description: DESCRIPTION,
    siteName: brand.displayName,
  },
};

const SECTIONS = [
  { href: "#how", label: "How it works" },
  { href: "#safety", label: "Safety" },
  { href: "#faq", label: "FAQ" },
];

/*
 * Card copy and FAQ answers repeat what /privacy says (design spec 6.1): nothing here
 * claims more than the privacy page. Drafted for the owner's approval.
 */
const CARDS = [
  {
    label: "Safe by default",
    text: "Block or report from any chat. Your name and links stay hidden until you accept.",
  },
  { label: "Human chats", text: "Only the two of you in a chat. No AI reads it." },
  { label: "Pair spaces", text: "Shared goals, skills and progress notes once you connect." },
];

const FAQ = [
  {
    id: "name",
    question: "Who can see my name?",
    answer:
      "Your name and links are shown only to people you are connected with. When you're suggested to someone, or send them an intro, they see your summary, skills, interests and availability, and why you were matched, but not your name or links.",
  },
  {
    id: "ai",
    question: "Does AI read my chats?",
    answer:
      "No. We don't use AI to read your chat messages. Only you and the person you're talking to can read your chat.",
  },
  {
    id: "block",
    question: "What happens when I block someone?",
    answer:
      "Neither of you can message the other, and you won't be suggested to each other. They aren't told.",
  },
];

/** The public landing page (design spec 6.1, reference-landing.html). */
export default function LandingPage() {
  return (
    <div className="max-w-content mx-auto w-full px-4 sm:px-6 lg:px-8">
      <TopBar
        links={SECTIONS}
        actions={
          <>
            <ButtonLink href="/login" variant="ghost" size="compact">
              Sign in
            </ButtonLink>
            <ButtonLink href="/login" variant="primary" size="compact">
              Get started
            </ButtonLink>
          </>
        }
      />

      <main>
        <div className="bg-green-tint border-green-line rounded-panel my-3 grid overflow-hidden border lg:my-4 lg:grid-cols-[1.15fr_1fr]">
          <div className="flex flex-col items-start px-4 py-5 lg:px-12 lg:py-14">
            <TopicChip tone="soft">for builders, learners, explorers</TopicChip>
            <TwoToneHeadline
              as="h1"
              size="hero"
              onTint
              lead="Say what you're building."
              rest="Meet who can help."
              className="mt-3.5 mb-3 lg:mt-5 lg:mb-[18px]"
            />
            <p className="text-ink-2 text-body lg:text-body-lg mb-4 max-w-[46ch]">
              Describe your goal in a sentence. {brand.displayName} finds people with the right
              skills, interests and intent. No feed. No follower counts.
            </p>
            <div className="flex flex-wrap gap-2">
              <ButtonLink href="/login" variant="primary">
                Find your people
              </ButtonLink>
              <ButtonLink href="#how" variant="outline">
                See how it works
              </ButtonLink>
            </div>
          </div>
          <div aria-hidden className="lg:h-full">
            <HeroGrid className="lg:h-full">
              <HeroCell index={0}>
                <TopicChip>cybersecurity</TopicChip>
              </HeroCell>
              <HeroCell index={1}>
                <PeopleIcon className="text-green size-[30px]" />
              </HeroCell>
              <HeroCell index={2} wide>
                <div>
                  <p className="text-mono text-green mb-1 font-mono uppercase">Why this match</p>
                  <p className="font-medium">A close match for what you described.</p>
                </div>
              </HeroCell>
              <HeroCell index={3}>
                <PixelPattern />
              </HeroCell>
              <HeroCell index={4}>
                <span className="text-meta-lg text-green flex items-center gap-1.5">
                  <CheckIcon className="size-4" />
                  Intro sent
                </span>
              </HeroCell>
            </HeroGrid>
          </div>
        </div>

        <FadeUp as="section" id="how" aria-labelledby="how-h" className="pt-10 pb-2 lg:pt-[88px]">
          <p className="text-mono-lg text-green mb-2.5 font-mono uppercase">How it works</p>
          <span id="how-h">
            <TwoToneHeadline lead="Skills. Interests. Intent." rest="Matched." />
          </span>
          <NumberedRows
            className="mt-5"
            rows={[
              { lead: "Skills", rest: "tell you what someone knows." },
              { lead: "Interests", rest: "tell you what they care about." },
              { lead: "Intent", rest: "tells you why you should meet." },
            ]}
          />
        </FadeUp>

        <FadeUp as="section" id="safety" aria-label="Safety" className="pt-8">
          <ul className="grid gap-2.5 sm:grid-cols-3">
            {CARDS.map((card) => (
              <li key={card.label}>
                <Panel tone="panel" interactive className="h-full">
                  <LabelChip>{card.label}</LabelChip>
                  <p className="text-ink-2 mt-3">{card.text}</p>
                </Panel>
              </li>
            ))}
          </ul>
        </FadeUp>

        <FadeUp as="section" id="faq" aria-labelledby="faq-h" className="pt-10 pb-2 lg:pt-[88px]">
          <p className="text-mono-lg text-green mb-2.5 font-mono uppercase">FAQ</p>
          <span id="faq-h">
            <TwoToneHeadline lead="Questions," rest="answered." />
          </span>
          <Accordion className="mt-5" items={FAQ} />
        </FadeUp>

        <FadeUp className="mt-10 mb-3">
          <CtaBand
            lead="Your next collaborator"
            rest="is one sentence away."
            action={{ href: "/login", label: "Find your people" }}
          />
        </FadeUp>

        <section aria-label="System status" className="mt-6">
          <Suspense fallback={<ApiStatusFallback />}>
            <ApiStatusIndicator />
          </Suspense>
        </section>
      </main>

      <Footer productLinks={SECTIONS} />
    </div>
  );
}
