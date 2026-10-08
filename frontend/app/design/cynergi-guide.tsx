import type { ReactNode } from "react";

import {
  Accordion,
  Avatar,
  BottomNav,
  Button,
  ButtonLink,
  CheckIcon,
  CtaBand,
  FadeUp,
  Footer,
  HeroCell,
  HeroGrid,
  HomeIcon,
  InlineError,
  Input,
  LabelChip,
  ListRow,
  Logo,
  NumberedRows,
  Panel,
  PeopleIcon,
  PixelPattern,
  RowTile,
  SavedIcon,
  Skeleton,
  SkeletonGroup,
  StatusBadge,
  Textarea,
  TopBar,
  TopicChip,
  TwoToneHeadline,
  YouIcon,
} from "@/components/ds";
import { colors } from "@/lib/design/tokens";

import { SegmentedDemo, ToastDemo } from "./ds-demos";

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="border-line flex flex-col gap-4 border-t pt-8">
      <h2 id={id} className="font-display text-headline">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Label({ children }: { children: ReactNode }) {
  return <p className="text-mono-lg text-green font-mono uppercase">{children}</p>;
}

const NAV_ITEMS = [
  { href: "/home", label: "Home", icon: <HomeIcon /> },
  { href: "/spaces", label: "Spaces", icon: <PeopleIcon /> },
  { href: "/saved", label: "Saved", icon: <SavedIcon /> },
  { href: "/you", label: "You", icon: <YouIcon /> },
];

const LANDING_LINKS = [
  { href: "/design#how", label: "How it works" },
  { href: "/design#safety", label: "Safety" },
  { href: "/design#faq", label: "FAQ" },
];

/** The Cynergi components (ADR 0014), each in its states. */
export function CynergiGuide() {
  return (
    <div className="flex flex-col gap-10">
      <Section id="ds-palette" title="Cynergi palette">
        <div className="flex flex-wrap gap-4">
          {Object.entries(colors).map(([name, hex]) => (
            <div key={name} className="flex w-28 flex-col gap-1">
              <div
                className="rounded-card border-line h-12 border"
                style={{ backgroundColor: hex }}
              />
              <p className="text-meta-lg font-medium">{name}</p>
              <p className="text-mono-lg text-muted font-mono">{hex}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section id="ds-type" title="Cynergi type">
        <TwoToneHeadline
          as="h3"
          size="hero"
          lead="Say what you're building."
          rest="Meet who can help."
        />
        <TwoToneHeadline as="h3" lead="Skills. Interests. Intent." rest="Matched." />
        <p className="text-title lg:text-title-lg">Row title and person&apos;s name · 14 / 600</p>
        <p className="text-body lg:text-body-lg text-ink-2 max-w-xl">
          Body · Inter 14 on phones, 16 on desktop. Sentence case, contractions, active voice.
        </p>
        <p className="text-meta lg:text-meta-lg text-muted">Small and metadata · 12 / 13</p>
        <Label>Mono label · JetBrains Mono 10 / 11</Label>
      </Section>

      <Section id="ds-buttons" title="Cynergi buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary">Find people</Button>
          <Button variant="outline">See how it works</Button>
          <Button variant="ghost">Sign in</Button>
          <Button variant="danger">Block</Button>
          <Button variant="primary" disabled>
            Disabled
          </Button>
          <Button variant="outline" size="compact">
            Compact
          </Button>
          <ButtonLink href="/design" variant="outline">
            Button-styled link
          </ButtonLink>
        </div>
        <div className="bg-green rounded-panel flex flex-wrap gap-3 p-4">
          <Button variant="white">Open pair spaces</Button>
        </div>
      </Section>

      <Section id="ds-chips" title="Chips and badges">
        <div className="flex flex-wrap items-center gap-3">
          <LabelChip>Safe by default</LabelChip>
          <TopicChip>cybersecurity</TopicChip>
          <TopicChip tone="soft">for builders, learners, explorers</TopicChip>
          <StatusBadge kind="request" />
          <StatusBadge kind="intro" />
        </div>
      </Section>

      <Section id="ds-rows" title="Panels, rows and avatars">
        <div className="grid gap-3 md:grid-cols-3">
          <Panel>
            <p className="text-title">White panel</p>
            <p className="text-ink-2">1px line, radius 14.</p>
          </Panel>
          <Panel tone="panel" interactive>
            <LabelChip>Human chats</LabelChip>
            <p className="text-ink-2 mt-3">
              Panel fill. Its border turns green on hover (desktop).
            </p>
          </Panel>
          <Panel tone="green">
            <p className="text-title">Green tint panel</p>
            <p className="text-ink-2">Secondary text on tint uses ink-2 or muted.</p>
          </Panel>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Avatar userId="sample-avatar-1" name="Aarav R." size="sm" />
          <Avatar userId="sample-avatar-2" name="Meera K." />
          <Avatar userId="sample-avatar-3" name="Rohan D." size="lg" />
          <Avatar userId="sample-avatar-4" name="Sana P." />
        </div>
        <SegmentedDemo />
        <ul className="border-line max-w-md border-t">
          <ListRow
            href="/design#ds-rows"
            leading={<RowTile kind="request" />}
            title="Budgeting app design"
            secondary="4 matches ready to view"
            time="2m"
            badge={<StatusBadge kind="request" />}
          />
          <ListRow
            href="/design#ds-rows"
            leading={<Avatar userId="sample-avatar-1" name="Aarav R." decorative />}
            title="Aarav R."
            secondary="2 new messages"
            time="12m"
            unread
            unreadLabel="Unread messages"
            selected
          />
          <ListRow
            href="/design#ds-rows"
            leading={<RowTile kind="intro" />}
            title="New intro received"
            secondary="Wants help with: React basics"
            time="1h"
            badge={<StatusBadge kind="intro" />}
          />
          <ListRow
            href="/design#ds-rows"
            leading={<Avatar userId="sample-avatar-2" name="Meera K." decorative />}
            title="Meera K."
            secondary="Open chat"
            time="Yesterday"
          />
        </ul>
      </Section>

      <Section id="ds-fields" title="Fields, errors and toasts">
        <div className="grid max-w-md gap-5">
          <Input label="Email address" type="email" hint="We email you a sign-in code." />
          <Input label="Sign-in code" error="That code has expired. Ask for a new one." />
          <Panel tone="green">
            <Textarea
              label="New request"
              maxLength={500}
              placeholder="I'm building a budgeting app and need a design eye."
            />
          </Panel>
          <InlineError>We couldn&apos;t save that. Try again in a moment.</InlineError>
        </div>
        <ToastDemo />
      </Section>

      <Section id="ds-faq" title="Accordion">
        <Accordion
          items={[
            { id: "one", question: "Sample question one", answer: "Sample answer one." },
            { id: "two", question: "Sample question two", answer: "Sample answer two." },
          ]}
        />
      </Section>

      <Section id="ds-motion" title="Motion and loading">
        <p className="text-ink-2 max-w-xl">
          Sections fade up once as they scroll in; hero cells fade up 70ms apart; buttons lift 2px
          on hover and press to 97%. With reduced motion, nothing moves.
        </p>
        <FadeUp>
          <Panel tone="panel">This panel fades up when it first scrolls into view.</Panel>
        </FadeUp>
        <SkeletonGroup className="flex max-w-md flex-col gap-2">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </SkeletonGroup>
      </Section>

      <Section id="ds-landing" title="Hero grid, numbered rows and CTA band">
        <div className="bg-green-tint border-green-line rounded-panel grid overflow-hidden border lg:grid-cols-[1.15fr_1fr]">
          <div className="flex flex-col gap-4 px-4 py-5 lg:px-12 lg:py-14">
            <TopicChip tone="soft" className="self-start">
              for builders, learners, explorers
            </TopicChip>
            <TwoToneHeadline
              as="h3"
              size="hero"
              onTint
              lead="Say what you're building."
              rest="Meet who can help."
            />
          </div>
          <HeroGrid>
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
        <NumberedRows
          rows={[
            { lead: "Skills", rest: "tell you what someone knows." },
            { lead: "Interests", rest: "tell you what they care about." },
            { lead: "Intent", rest: "tells you why you should meet." },
          ]}
        />
        <CtaBand
          headingLevel={3}
          lead="Your next collaborator"
          rest="is one sentence away."
          action={{ href: "/design", label: "Find your people" }}
        />
      </Section>

      <Section id="ds-nav" title="Navigation and footer">
        <Label>Top bar (links show from 1024px)</Label>
        <TopBar
          homeHref="/design"
          links={LANDING_LINKS}
          currentHref="/design#how"
          actions={
            <>
              <ButtonLink href="/design" variant="ghost" size="compact">
                Sign in
              </ButtonLink>
              <ButtonLink href="/design" variant="primary" size="compact">
                Get started
              </ButtonLink>
            </>
          }
        />
        <Label>Bottom nav (phones; hidden from 1024px)</Label>
        <div className="max-w-md">
          <BottomNav items={NAV_ITEMS} />
        </div>
        <Label>Logo</Label>
        <Logo />
        <Footer productLinks={LANDING_LINKS} />
      </Section>
    </div>
  );
}
