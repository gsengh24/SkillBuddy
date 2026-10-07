import type { ReactNode } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Badge, BadgeDot } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HeroPanel } from "@/components/ui/hero-panel";
import {
  BellIcon,
  BookmarkIcon,
  CompassIcon,
  MessageIcon,
  PersonIcon,
} from "@/components/ui/icons";
import { IntentChip } from "@/components/ui/intent-chip";
import { Logo as LegacyLogo } from "@/components/ui/logo";
import { Logo } from "@/components/ds";
import { MatchNumeral } from "@/components/ui/match-numeral";
import { Overline } from "@/components/ui/overline";
import { StrengthBar } from "@/components/ui/strength-bar";
import { Tag, TintPill } from "@/components/ui/tag";
import { TextArea, TextField } from "@/components/ui/text-field";
import { TextLink } from "@/components/ui/text-link";
import { WhyBox } from "@/components/ui/why-box";
import { contrastRatio, personHue } from "@/lib/design/color";
import { COLOUR_PAIRS, MIN_RATIO } from "@/lib/design/pairs";
import {
  badge,
  greenSurfaces,
  HUE_NAMES,
  hues,
  INTENTS,
  intents,
  neutrals,
  type HueName,
} from "@/lib/design/tokens";

import { IntentChipDemo } from "./chip-demo";
import { CynergiGuide } from "./cynergi-guide";

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

function Swatch({ name, hex }: { name: string; hex: string }) {
  return (
    <div className="flex w-28 flex-col gap-1">
      <div className="rounded-why border-line h-12 border" style={{ backgroundColor: hex }} />
      <p className="text-small font-semibold">{name}</p>
      <p className="text-label text-muted font-mono">{hex}</p>
    </div>
  );
}

const SAMPLE_PEOPLE = [
  { id: "sample-person-1", name: "Aarav S.", value: 92 },
  { id: "sample-person-2", name: "Mehak K.", value: 88 },
  { id: "sample-person-3", name: "Rohan D.", value: 81 },
];

function SamplePersonCard({ id, name, value }: { id: string; name: string; value: number }) {
  const hue: HueName = personHue(id);
  return (
    <Card className="flex w-full max-w-sm flex-col gap-4">
      <div className="flex items-start gap-3">
        <Avatar userId={id} name={name} decorative />
        <div className="min-w-0 flex-1">
          <p className="font-bold">{name}</p>
          <p className="text-small text-muted">Sample profile · weekends</p>
        </div>
        <MatchNumeral value={value} hue={hue} />
      </div>
      <StrengthBar value={value} hue={hue} label={`Match strength with ${name}`} />
      <WhyBox hue={hue}>Wants a backend partner for a campus tool. You share civic tech.</WhyBox>
      <div className="flex flex-wrap gap-2">
        <Tag hue={hue}>Figma</Tag>
        <Tag hue={hue}>React</Tag>
      </div>
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="text-small text-muted hover:text-ink min-h-11 font-semibold"
        >
          Save
        </button>
        <Button hue={hue}>Connect →</Button>
      </div>
    </Card>
  );
}

/**
 * Every component and colour pair of the design system: the Cynergi components (ADR 0014)
 * first, then the older components that existing screens still use.
 */
export function StyleGuide() {
  return (
    <main className="max-w-content mx-auto flex w-full flex-col gap-12 px-4 py-10 lg:px-8">
      <header className="flex flex-col gap-3">
        <Logo />
        <h1 className="text-headline lg:text-headline-lg">Design system</h1>
        <p className="text-ink-2 max-w-2xl">
          Cynergi (ADR 0014). Shown in development and on preview deployments only. Spec:{" "}
          <span className="text-meta-lg font-mono">docs/design/design-spec.md</span>. Narrow the
          window (or use the browser&apos;s device toolbar at 390px) to see the phone layout.
        </p>
      </header>

      <CynergiGuide />

      <section
        aria-labelledby="sg-legacy"
        className="border-line flex flex-col gap-2 border-t pt-8"
      >
        <h2 id="sg-legacy" className="font-display text-headline">
          Legacy components
        </h2>
        <p className="text-ink-2 max-w-2xl">
          The older components (components/ui), still used by screens that haven&apos;t been
          restyled yet. They now take their neutrals and greens from the Cynergi palette.
        </p>
      </section>

      <Section id="sg-neutrals" title="Neutrals">
        <div className="flex flex-wrap gap-4">
          {Object.entries(neutrals).map(([name, hex]) => (
            <Swatch key={name} name={name} hex={hex} />
          ))}
          <Swatch name="green panel" hex={greenSurfaces.panel} />
          <Swatch name="green chip" hex={greenSurfaces.chip} />
          <Swatch name="badge" hex={badge.fill} />
        </div>
      </Section>

      <Section id="sg-hues" title="Hues">
        <p className="text-muted max-w-2xl">
          Base is for dots, bars and fills only, never text. Text on a tint uses the hue&apos;s ink.
        </p>
        <div className="flex flex-col gap-6">
          {HUE_NAMES.map((hue) => (
            <div key={hue} className="flex flex-col gap-2">
              <Overline>{hue}</Overline>
              <div className="flex flex-wrap gap-4">
                {Object.entries(hues[hue]).map(([role, hex]) => (
                  <Swatch key={role} name={role} hex={hex} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section id="sg-pairs" title="Colour pairs and contrast">
        <p className="text-muted max-w-2xl">
          Text needs 4.5:1; borders, focus rings and control states need 3:1. Checked by a test on
          every change.
        </p>
        <div
          role="region"
          aria-label="Colour pairs table"
          tabIndex={0}
          className="rounded-card border-line bg-paper overflow-x-auto border"
        >
          <table className="text-small w-full min-w-[640px] text-left">
            <thead>
              <tr className="border-line border-b">
                <th scope="col" className="px-4 py-2 font-semibold">
                  Pair
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Sample
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Ratio
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Needs
                </th>
              </tr>
            </thead>
            <tbody>
              {COLOUR_PAIRS.map((pair) => {
                const ratio = contrastRatio(pair.foreground, pair.background);
                return (
                  <tr key={pair.name} className="border-line border-b last:border-0">
                    <td className="px-4 py-2">{pair.name}</td>
                    <td className="px-4 py-2">
                      {pair.kind === "ui" ? (
                        <span
                          aria-hidden
                          className="inline-block h-6 w-16 rounded-full border-2"
                          style={{ borderColor: pair.foreground, backgroundColor: pair.background }}
                        />
                      ) : (
                        <span
                          className={
                            pair.kind === "large"
                              ? "inline-block rounded-md px-2 py-0.5 text-[24px] leading-tight font-bold"
                              : "inline-block rounded-md px-2 py-0.5 font-semibold"
                          }
                          style={{ color: pair.foreground, backgroundColor: pair.background }}
                        >
                          Sample text
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 font-mono">{ratio.toFixed(2)}:1</td>
                    <td className="px-4 py-2 font-mono">{MIN_RATIO[pair.kind]}:1</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="sg-type" title="Typography">
        <div className="flex flex-col gap-3">
          <p className="text-h1 font-display">Heading 1 · 26 / 800</p>
          <p className="text-section">Section heading · 19 / 700</p>
          <p className="max-w-xl">
            Body text · 14 / 1.5. The older components, now in Inter on the Cynergi neutrals.
          </p>
          <p className="text-small text-muted">Small text · 13</p>
          <Overline>Label · JetBrains Mono 11 uppercase</Overline>
          <p className="text-numeral">92</p>
        </div>
      </Section>

      <Section id="sg-intents" title="Intents">
        <div className="flex flex-wrap gap-2">
          {INTENTS.map((intent) => (
            <IntentChip key={intent} intent={intent} />
          ))}
        </div>
        <p className="text-small text-muted">Static (above) and selectable (below):</p>
        <IntentChipDemo />
        <p className="text-small text-muted">
          {INTENTS.map((intent) => `${intents[intent].label} = ${intents[intent].hue}`).join(" · ")}
        </p>
      </Section>

      <Section id="sg-buttons" title="Buttons and links">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Find matches →</Button>
          <Button tone="danger">Delete my account</Button>
          <Button hue="coral">Connect →</Button>
          <Button hue="violet">Connect →</Button>
          <Button disabled>Disabled</Button>
          <ButtonLink href="/design">Button-styled link</ButtonLink>
        </div>
        <p>
          A <TextLink href="/design">text link</TextLink> inside a sentence, and a{" "}
          <TextLink href="/design" tone="muted">
            muted link
          </TextLink>
          .
        </p>
      </Section>

      <Section id="sg-people" title="Avatar, strength bar, match numeral, why-box, tags">
        <div className="flex flex-wrap items-center gap-3">
          {HUE_NAMES.map((hue, index) => (
            <Avatar
              key={hue}
              userId={`sample-avatar-${index}`}
              name={`Sample Person ${index + 1}`}
            />
          ))}
          <Avatar userId="sample-avatar-lg" name="Large Avatar" size="lg" />
          <Avatar userId="sample-avatar-sm" name="small@example.com" size="sm" />
        </div>
        <div className="grid max-w-md gap-3">
          {HUE_NAMES.map((hue, index) => (
            <StrengthBar key={hue} hue={hue} value={40 + index * 10} label={`Sample ${hue} bar`} />
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {HUE_NAMES.map((hue) => (
            <Tag key={hue} hue={hue}>
              {hue} tag
            </Tag>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <TintPill hue="blue">Someone to practise aptitude tests with</TintPill>
          <TintPill hue="coral">A guitarist for a weekend jam</TintPill>
          <TintPill hue="violet">A mentor for my first research paper</TintPill>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {SAMPLE_PEOPLE.map((person) => (
            <SamplePersonCard key={person.id} {...person} />
          ))}
        </div>
      </Section>

      <Section id="sg-surfaces" title="Card and hero panel">
        <Card className="max-w-md">
          <p className="font-bold">Card</p>
          <p className="text-muted">Paper (now the panel colour), 1px line border, radius 12.</p>
        </Card>
        <HeroPanel>
          <Overline tone="green">What are you looking for</Overline>
          <p className="text-section max-w-xl">
            I want to build a campus lost-and-found app. I can do the backend; I need someone who
            can design it.
          </p>
        </HeroPanel>
      </Section>

      <Section id="sg-fields" title="Text fields">
        <div className="grid max-w-md gap-6">
          <TextField label="Search people, skills, interests" placeholder="e.g. React, guitar" />
          <TextField label="Email address" hint="We email you a sign-in code." type="email" />
          <TextField label="Sign-in code" error="That code is incorrect or has expired." />
          <TextArea
            label="About you"
            hint="A few sentences about what you can do and want to do."
          />
        </div>
      </Section>

      <Section id="sg-badges" title="Badges, logo and icons">
        <div className="flex flex-wrap items-center gap-6">
          <span className="inline-flex items-center gap-2">
            Messages <Badge count={2} label="unread messages" />
          </span>
          <span className="inline-flex items-center gap-2">
            Many <Badge count={140} label="unread messages" />
          </span>
          <span className="inline-flex items-center gap-2">
            New <BadgeDot label="new activity" />
          </span>
          <LegacyLogo />
          <span className="text-ink inline-flex gap-3">
            <CompassIcon />
            <MessageIcon />
            <BookmarkIcon />
            <PersonIcon />
            <BellIcon />
          </span>
        </div>
      </Section>
    </main>
  );
}
