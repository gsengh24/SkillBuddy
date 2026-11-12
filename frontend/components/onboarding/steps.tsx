"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ds/button";
import { ChoiceCard, ChoiceChip, RadioSegments } from "@/components/ds/choices";
import { Input, Select } from "@/components/ds/fields";
import {
  AccountabilityIcon,
  BuddyIcon,
  BuildIcon,
  ExchangeIcon,
  ExploreIcon,
  FileIcon,
  MentorIcon,
  PasteIcon,
  SparkIcon,
} from "@/components/ds/icons";
import { Accordion } from "@/components/ds/accordion";
import { Panel } from "@/components/ds/surfaces";
import type { Onboarding } from "@/lib/api/schemas";
import type { Intent } from "@/lib/design/tokens";
import {
  ALL_LISTED_SKILLS,
  BRANCHES,
  DAYS,
  extraTags,
  HOURS,
  includesTag,
  INTENT_CARDS,
  INTERESTS,
  MAX_TAGS,
  NAME_MAX,
  pairsWellWith,
  SKILL_GROUPS,
  toggleTag,
  WANT_NOTE_MAX,
  YEARS,
  type IntentIconName,
} from "@/lib/onboarding/catalog";

import { SkillSearch } from "./skill-search";

/** What each step edits before it is saved: the same fields the API takes. */
export type Drafts = {
  intents: Intent[];
  offers: string[];
  wants: { skills: string[]; interests: string[]; note: string };
  about: {
    study_year: Onboarding["study_year"];
    branch: Onboarding["branch"];
    available_days: Onboarding["available_days"];
    weekly_hours: Onboarding["weekly_hours"];
    display_name: string;
  };
};

export function draftsFrom(progress: Onboarding): Drafts {
  return {
    intents: progress.intents,
    offers: progress.offer_skills,
    wants: {
      skills: progress.want_skills,
      interests: progress.interest_tags,
      note: progress.want_note,
    },
    about: {
      study_year: progress.study_year,
      branch: progress.branch,
      available_days: progress.available_days,
      weekly_hours: progress.weekly_hours,
      display_name: progress.display_name,
    },
  };
}

const INTENT_ICONS: Record<IntentIconName, ReactNode> = {
  build: <BuildIcon className="size-[26px]" />,
  exchange: <ExchangeIcon className="size-[26px]" />,
  buddy: <BuddyIcon className="size-[26px]" />,
  accountability: <AccountabilityIcon className="size-[26px]" />,
  mentor: <MentorIcon className="size-[26px]" />,
  explore: <ExploreIcon className="size-[26px]" />,
};

function GroupLabel({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <span id={id} className="text-mono-lg text-muted font-mono uppercase">
      {children}
    </span>
  );
}

function ChipGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className="flex flex-col gap-2.5">
      <GroupLabel>{label}</GroupLabel>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

/** Step 1: what brings you here. */
export function IntentsStep({
  value,
  onChange,
}: {
  value: Intent[];
  onChange: (value: Intent[]) => void;
}) {
  return (
    <div
      role="group"
      aria-label="What you're here for"
      className="grid grid-cols-2 gap-2 lg:grid-cols-3 lg:gap-3"
    >
      {INTENT_CARDS.map((card) => {
        const pressed = value.includes(card.value);
        return (
          <ChoiceCard
            key={card.value}
            pressed={pressed}
            onToggle={() =>
              onChange(pressed ? value.filter((v) => v !== card.value) : [...value, card.value])
            }
            icon={INTENT_ICONS[card.icon]}
            title={card.label}
            line={card.line}
          />
        );
      })}
    </div>
  );
}

function add(list: string[], tag: string): string[] {
  return includesTag(list, tag) || list.length >= MAX_TAGS ? list : [...list, tag];
}

function toggle(list: string[], tag: string): string[] {
  return includesTag(list, tag) || list.length < MAX_TAGS ? toggleTag(list, tag) : list;
}

/** Step 2: what you're good at. */
export function OffersStep({
  value,
  onChange,
}: {
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const extra = extraTags(value, ALL_LISTED_SKILLS);
  return (
    <>
      <Panel tone="green" className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <p className="font-display text-[18px] leading-[1.1] font-extrabold tracking-[-0.02em]">
          Skip the typing
        </p>
        <div className="grid grid-cols-2 gap-2 lg:row-span-2 lg:flex">
          {/* Resume import and paste arrive with the next onboarding change. */}
          <Button variant="outline" disabled className="px-2.5">
            <FileIcon className="size-4" />
            Import resume (PDF)
          </Button>
          <Button variant="outline" disabled className="px-2.5">
            <PasteIcon className="size-4" />
            Paste text
          </Button>
        </div>
        <p className="text-meta text-muted lg:text-meta-lg">Coming soon.</p>
      </Panel>
      <SkillSearch
        label="Search skills"
        placeholder="Search skills, e.g. Python"
        picked={value}
        disabled={value.length >= MAX_TAGS}
        onAdd={(skill) => onChange(add(value, skill))}
      />
      {extra.length ? (
        <ChipGroup label="Added">
          {extra.map((skill) => (
            <ChoiceChip key={skill} pressed onToggle={() => onChange(toggleTag(value, skill))}>
              {skill}
            </ChoiceChip>
          ))}
        </ChipGroup>
      ) : null}
      {SKILL_GROUPS.map((group) => (
        <ChipGroup key={group.label} label={group.label}>
          {group.skills.map((skill) => (
            <ChoiceChip
              key={skill}
              pressed={includesTag(value, skill)}
              onToggle={() => onChange(toggle(value, skill))}
            >
              {skill}
            </ChoiceChip>
          ))}
        </ChipGroup>
      ))}
    </>
  );
}

/** "You offer ⇄ You want": the exchange so far, beside the picks on desktop. */
export function TradeSummary({
  offers,
  wants,
  onEditOffers,
  className,
}: {
  offers: string[];
  wants: string[];
  onEditOffers: () => void;
  className?: string;
}) {
  const tag = (text: string, tone: "green" | "ink") => (
    <li
      key={text}
      className={
        tone === "green"
          ? "border-green-line bg-green-tint text-green text-mono-lg rounded-full border px-2.5 py-1 font-mono uppercase"
          : "border-line-strong bg-page-soft text-ink text-mono-lg rounded-full border px-2.5 py-1 font-mono uppercase"
      }
    >
      {text}
    </li>
  );
  return (
    <Panel tone="panel" className={className}>
      <section aria-label="Your exchange so far" className="grid content-start gap-3.5">
        <div className="grid gap-2">
          <div className="flex items-baseline justify-between gap-2">
            <GroupLabel>You offer</GroupLabel>
            <button
              type="button"
              onClick={onEditOffers}
              className="text-green text-meta-lg min-h-11 underline-offset-2 hover:underline pointer-fine:min-h-0"
            >
              Edit
            </button>
          </div>
          {offers.length ? (
            <ul className="flex flex-wrap gap-1.5">{offers.map((o) => tag(o, "green"))}</ul>
          ) : (
            <p className="text-meta text-muted">Nothing yet</p>
          )}
        </div>
        <div aria-hidden className="text-muted-2 flex items-center gap-2.5">
          <span className="bg-line h-px flex-1" />
          <ExchangeIcon className="size-[18px] rotate-90" />
          <span className="bg-line h-px flex-1" />
        </div>
        <div className="grid gap-2">
          <div className="flex items-baseline justify-between gap-2">
            <GroupLabel>You want</GroupLabel>
            <span className="text-mono-lg text-muted font-mono uppercase">
              {wants.length} picked
            </span>
          </div>
          {wants.length ? (
            <ul className="flex flex-wrap gap-1.5">{wants.map((w) => tag(w, "ink"))}</ul>
          ) : (
            <p className="text-meta text-muted">Pick at least one below</p>
          )}
        </div>
        <p className="text-meta text-muted border-line hidden border-t pt-3 lg:block">
          We look for people whose offers and wants line up both ways.
        </p>
      </section>
    </Panel>
  );
}

/** Step 3: what you're looking for. Want chips are ink; offer chips (step 2) are green. */
export function WantsStep({
  offers,
  value,
  onChange,
}: {
  offers: string[];
  value: Drafts["wants"];
  onChange: (value: Drafts["wants"]) => void;
}) {
  const pairs = pairsWellWith(offers);
  const rest = SKILL_GROUPS.map((group) => ({
    ...group,
    skills: group.skills.filter((skill) => !includesTag(pairs, skill)),
  })).filter((group) => group.skills.length > 0);
  const restCount = rest.reduce((sum, group) => sum + group.skills.length, 0);
  const extra = extraTags(value.skills, ALL_LISTED_SKILLS);
  const setSkills = (skills: string[]) => onChange({ ...value, skills });
  const wantChip = (skill: string) => (
    <ChoiceChip
      key={skill}
      tone="ink"
      pressed={includesTag(value.skills, skill)}
      onToggle={() => setSkills(toggle(value.skills, skill))}
    >
      {skill}
    </ChoiceChip>
  );
  const offerNames = offers.slice(0, 2).join(" and ");

  return (
    <>
      {pairs.length ? (
        <section
          aria-labelledby="pairs-heading"
          className="rounded-panel border-line-strong bg-card grid gap-3.5 border p-4 lg:p-5"
        >
          <div className="flex items-start gap-2.5">
            <SparkIcon className="text-green mt-0.5 size-[18px] shrink-0" />
            <div>
              <h2 id="pairs-heading" className="text-title lg:text-title-lg">
                Pairs well with what you offer
              </h2>
              <p className="text-meta text-muted">
                People who know {offerNames} often look for these.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">{pairs.map(wantChip)}</div>
        </section>
      ) : null}
      {extra.length ? <ChipGroup label="Added">{extra.map(wantChip)}</ChipGroup> : null}
      <Accordion
        headingLevel={2}
        items={[
          {
            id: "browse",
            question: `Browse all skills · ${rest.length} groups · ${restCount} more`,
            answer: (
              <div className="grid gap-[18px] pt-1">
                {rest.map((group) => (
                  <ChipGroup key={group.label} label={group.label}>
                    {group.skills.map(wantChip)}
                  </ChipGroup>
                ))}
              </div>
            ),
          },
        ]}
      />
      <SkillSearch
        label="Search skills you want"
        placeholder="Not listed? Search, e.g. Django"
        picked={value.skills}
        disabled={value.skills.length >= MAX_TAGS}
        onAdd={(skill) => setSkills(add(value.skills, skill))}
      />
      <Input
        label="Anything specific? (optional)"
        placeholder="e.g. a designer for my app, a gym partner for mornings"
        maxLength={WANT_NOTE_MAX}
        value={value.note}
        onChange={(event) => onChange({ ...value, note: event.target.value })}
        hint={`One line is plenty. We'll use it to find people. ${value.note.length} / ${WANT_NOTE_MAX}`}
      />
      <ChipGroup label="Interests">
        {INTERESTS.map((interest) => (
          <ChoiceChip
            key={interest}
            pressed={includesTag(value.interests, interest)}
            onToggle={() => onChange({ ...value, interests: toggle(value.interests, interest) })}
          >
            {interest}
          </ChoiceChip>
        ))}
      </ChipGroup>
    </>
  );
}

/** Step 4: a bit about you. Every field is optional. */
export function AboutStep({
  value,
  onChange,
}: {
  value: Drafts["about"];
  onChange: (value: Drafts["about"]) => void;
}) {
  return (
    <>
      <div className="flex flex-col gap-1.5">
        <span id="year-label" className="text-meta-lg text-ink font-medium">
          Year
        </span>
        <RadioSegments
          label="Year"
          options={YEARS}
          value={value.study_year}
          onChange={(study_year) => onChange({ ...value, study_year })}
        />
      </div>
      <Select
        label="Branch"
        value={value.branch ?? ""}
        onChange={(event) =>
          onChange({
            ...value,
            branch: (event.target.value || null) as Drafts["about"]["branch"],
          })
        }
      >
        <option value="">Choose your branch</option>
        {BRANCHES.map((branch) => (
          <option key={branch.value} value={branch.value}>
            {branch.label}
          </option>
        ))}
      </Select>
      <div className="grid gap-6 lg:grid-cols-2 lg:gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-meta-lg text-ink font-medium">Days you&apos;re usually free</span>
          <div
            role="group"
            aria-label="Days you're usually free"
            className="grid grid-cols-7 gap-1.5"
          >
            {DAYS.map((day) => {
              const pressed = value.available_days.includes(day.value);
              return (
                <ChoiceChip
                  key={day.value}
                  label={day.label}
                  pressed={pressed}
                  className="justify-center px-0 [&>span:first-child]:hidden"
                  onToggle={() =>
                    onChange({
                      ...value,
                      available_days: pressed
                        ? value.available_days.filter((d) => d !== day.value)
                        : [...value.available_days, day.value],
                    })
                  }
                >
                  {day.short}
                </ChoiceChip>
              );
            })}
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-meta-lg text-ink font-medium">Hours a week</span>
          <RadioSegments
            label="Hours a week"
            options={HOURS}
            value={value.weekly_hours}
            onChange={(weekly_hours) => onChange({ ...value, weekly_hours })}
          />
        </div>
      </div>
      <Input
        label="Display name"
        maxLength={NAME_MAX}
        value={value.display_name}
        onChange={(event) => onChange({ ...value, display_name: event.target.value })}
        hint="Shown only to people you are introduced to. It is never sent to an AI."
      />
    </>
  );
}
