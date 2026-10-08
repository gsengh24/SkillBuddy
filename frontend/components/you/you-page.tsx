"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState, type ReactNode } from "react";

import { DeleteAccount, SignOutActions } from "@/components/auth/account-actions";
import { Avatar } from "@/components/ds/avatar";
import { Button } from "@/components/ds/button";
import { Dialog } from "@/components/ds/dialog";
import { Input, Select, Textarea } from "@/components/ds/fields";
import { TwoToneHeadline } from "@/components/ds/page-parts";
import { SegmentedControl } from "@/components/ds/segmented-control";
import { TopicChip } from "@/components/ds/surfaces";
import { AiConsentText } from "@/components/profile/ai-consent";
import { EmailToggle } from "@/components/profile/email-toggle";
import { VisibilityToggle } from "@/components/profile/visibility-toggle";
import { cx } from "@/components/ui/cx";
import { TextLink } from "@/components/ui/text-link";
import { browserApi } from "@/lib/api/browser";
import { profileSchema, type Profile } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { brand } from "@/lib/brand";
import { ABOUT_MAX, ABOUT_MIN, LANGUAGES, LINK_PATTERN, NAME_MAX } from "@/lib/profile/limits";
import {
  CITY_MAX,
  DAYS,
  EXPERIENCE,
  GOAL_MAX,
  HEADLINE_MAX,
  INTENT_CHOICES,
  LEARN_SUGGESTIONS,
  LINK_ROWS,
  LOCATION_CHOICES,
  OFFER_SUGGESTIONS,
  SECTIONS,
  TIMES,
  TIMEZONES,
  WEEKLY_HOURS,
  WORKING_STYLES,
  draftFrom,
  isDirty,
  savePlan,
  strength,
  type Draft,
  type SectionId,
} from "@/lib/profile/you";

import { SectionNav } from "./section-nav";
import { TagEditor } from "./tag-editor";

const SECTION_TITLE = "font-display tracking-display text-[20px] leading-tight font-extrabold";

function Section({
  id,
  intro,
  danger = false,
  children,
}: {
  id: SectionId;
  intro?: string;
  danger?: boolean;
  children: ReactNode;
}) {
  const index = SECTIONS.findIndex((s) => s.id === id);
  return (
    <section
      id={id}
      aria-labelledby={`${id}-h`}
      className={cx(
        "rounded-panel bg-bg scroll-mt-20 border p-4 sm:p-6 lg:scroll-mt-8",
        danger ? "border-danger" : "border-line",
      )}
    >
      <div className="mb-4 flex items-start gap-3">
        <span
          aria-hidden
          className="font-display tracking-display text-faint min-w-9 text-[28px] leading-none font-extrabold"
        >
          {String(index + 1).padStart(2, "0")}
        </span>
        <div>
          <h2 id={`${id}-h`} className={SECTION_TITLE}>
            {SECTIONS[index]?.title}
          </h2>
          {intro ? <p className="text-meta-lg text-ink-2 mt-1">{intro}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

/** A row of toggle buttons (intent chips, days), each with aria-pressed. */
function Toggles<T extends string>({
  label,
  options,
  selected,
  onChange,
  variant,
}: {
  label: string;
  options: { value: T; label: string; name?: string }[];
  selected: T[];
  onChange: (next: T[]) => void;
  variant: "chips" | "days";
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={variant === "days" ? "grid grid-cols-7 gap-1.5" : "flex flex-wrap gap-1.5"}
    >
      {options.map((option) => {
        const on = selected.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={on}
            aria-label={option.name}
            onClick={() =>
              onChange(
                on ? selected.filter((v) => v !== option.value) : [...selected, option.value],
              )
            }
            className={cx(
              "min-h-11 border font-medium",
              variant === "chips"
                ? "inline-flex items-center gap-2 rounded-full px-3 text-[13px]"
                : "rounded-input text-meta",
              on
                ? "bg-green border-green text-bg"
                : variant === "chips"
                  ? "border-green-line bg-bg text-ink"
                  : "border-line bg-bg text-ink-2",
            )}
          >
            {variant === "chips" ? (
              <span
                aria-hidden
                className={cx("size-[7px] rounded-full", on ? "bg-mint" : "bg-green")}
              />
            ) : null}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function Label({ children }: { children: string }) {
  return <span className="text-meta-lg text-ink mb-1.5 block font-medium">{children}</span>;
}

/** What a match card shows about you today (MatchCandidateOut), with the draft's edits. */
function PreviewCard({ draft, profile }: { draft: Draft; profile: Profile }) {
  const understanding = profile.understanding;
  const location = draft.location === "city" && draft.city.trim() ? draft.city.trim() : null;
  const languages = LANGUAGES.filter((l) => draft.languages.includes(l.code)).map((l) => l.label);
  const groups: [string, string[], "outline" | "soft"][] = [
    ["Can help with", draft.offers, "soft"],
    ["Wants to learn", draft.seeks, "outline"],
    ["Interests", understanding?.interests ?? [], "outline"],
  ];
  return (
    <div className="bg-panel border-line rounded-card flex flex-col gap-3 border p-4">
      {understanding?.summary ? <p className="text-ink">{understanding.summary}</p> : null}
      {location ? <p className="text-mono text-muted font-mono uppercase">{location}</p> : null}
      {groups.map(([title, items, tone]) =>
        items.length ? (
          <div key={title} className="flex flex-col gap-1.5">
            <p className="text-mono text-muted font-mono uppercase">{title}</p>
            <ul className="flex flex-wrap gap-1.5">
              {items.map((item) => (
                <li key={item}>
                  <TopicChip tone={tone}>{item}</TopicChip>
                </li>
              ))}
            </ul>
          </div>
        ) : null,
      )}
      {understanding?.availability ? (
        <p className="text-meta-lg text-ink-2">Free: {understanding.availability}</p>
      ) : null}
      {languages.length ? (
        <p className="text-meta-lg text-ink-2">Speaks {languages.join(", ")}</p>
      ) : null}
    </div>
  );
}

type Props = {
  profile: Profile;
  email: string;
  termsVersion: string | null;
  isModerator: boolean;
};

/**
 * The You page (design spec section 13, reference-you.html): profile and account settings
 * in ten sections. Most edits wait for the Save bar; the visibility and email switches,
 * signing out and deleting act at once, as before.
 */
export function YouPage({ profile, email, termsVersion, isModerator }: Props) {
  const router = useRouter();
  const ids = useId();
  const [base, setBase] = useState<Draft>(() => draftFrom(profile));
  const [draft, setDraft] = useState<Draft>(base);
  const [visibility, setVisibility] = useState(profile.visibility);
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const dirty = isDirty(base, draft);

  // A refreshed profile (after a save, or a correction elsewhere) replaces the form only
  // when nothing is waiting to be saved: edits are never thrown away.
  const [shown, setShown] = useState(profile);
  if (profile !== shown) {
    setShown(profile);
    if (!dirty) {
      const next = draftFrom(profile);
      // Still being read: keep the skills shown until the new reading is in.
      const fresh = profile.understanding
        ? next
        : { ...next, offers: draft.offers, seeks: draft.seeks };
      setBase(fresh);
      setDraft(fresh);
    }
  }

  useEffect(() => {
    if (!saved) return;
    const timer = setTimeout(() => setSaved(false), 2500);
    return () => clearTimeout(timer);
  }, [saved]);

  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  const plan = savePlan(base, draft);
  const needsConsent = plan.aboutChanged && !profile.ai_consent_current;
  const { percent, missing } = strength(draft);
  const timezones =
    TIMEZONES.some((t) => t.value === draft.timezone) || !draft.timezone
      ? TIMEZONES
      : [{ value: draft.timezone, label: draft.timezone }, ...TIMEZONES];

  function validate(): string | null {
    if (!draft.name.trim()) return "Add the name you'd like matches to see.";
    const about = draft.about.trim().length;
    if (about < ABOUT_MIN)
      return `Write at least ${ABOUT_MIN} characters about yourself, so we can find good matches.`;
    if (about > ABOUT_MAX) return `Keep your description under ${ABOUT_MAX} characters.`;
    if (plan.links.some((l) => !LINK_PATTERN.test(l)))
      return "Links must be full https:// addresses, like https://github.com/you.";
    if (needsConsent && !consent) return "To save, agree to how AI is used to find your matches.";
    return null;
  }

  async function save() {
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (plan.aboutChanged) {
        await browserApi("/me/profile", profileSchema, {
          method: "PUT",
          body: {
            display_name: draft.name.trim(),
            about_text: draft.about.trim(),
            links: plan.links,
            languages: draft.languages,
            timezone: draft.timezone || null,
            visibility,
            ai_consent: needsConsent ? consent : false,
          },
        });
      }
      if (plan.skillsChanged) {
        // After the PUT, so the correction belongs to the new text and isn't re-read.
        const current = profile.understanding;
        await browserApi("/me/profile/understanding", profileSchema, {
          method: "PUT",
          body: {
            summary: current?.summary ?? "",
            offers: draft.offers,
            seeks: draft.seeks,
            interests: current?.interests ?? [],
            availability: current?.availability ?? "",
          },
        });
      }
      if (Object.keys(plan.patch).length) {
        await browserApi("/me/profile", profileSchema, { method: "PATCH", body: plan.patch });
      }
      setBase(draft);
      setConsent(false);
      setSaved(true);
      router.refresh();
    } catch (caught) {
      // The draft stays as it is, so nothing typed is lost; saving again sends it all.
      setError(describeError(caught));
    } finally {
      setSaving(false);
    }
  }

  function discard() {
    setDraft(base);
    setConsent(false);
    setError(null);
  }

  const name = draft.name.trim() || "Your name";

  return (
    <div className="flex flex-col pb-40 lg:pb-28">
      <p className="text-mono-lg text-green mb-2.5 font-mono uppercase">You</p>
      <TwoToneHeadline as="h1" lead="Your profile." rest="Be easy to find." />

      <section
        aria-label="Profile summary"
        className="bg-panel border-line rounded-panel mt-5 flex flex-col gap-4 border p-4 lg:flex-row lg:items-center lg:justify-between lg:gap-8 lg:px-6 lg:py-5"
      >
        <div className="flex items-center gap-3.5 lg:flex-1">
          <Avatar userId={profile.user_id} name={name} size="xl" decorative />
          <div className="min-w-0">
            <p className="font-display tracking-display text-[22px] leading-tight font-extrabold break-words lg:text-[28px]">
              {name}
            </p>
            <p className="text-meta-lg text-ink-2">{draft.headline.trim() || "Add a headline"}</p>
            <p className="text-mono text-muted mt-1.5 font-mono uppercase">
              {[draft.city.trim() || "Add your city", draft.timezone].filter(Boolean).join(" · ")}
            </p>
          </div>
        </div>
        <div className="border-line bg-bg rounded-card border px-3.5 py-3 lg:w-[340px] lg:flex-none">
          <div className="flex items-baseline justify-between">
            <span className="text-mono text-muted font-mono uppercase">Profile strength</span>
            <span className="font-display tracking-display text-[22px] font-extrabold">
              {percent}%
            </span>
          </div>
          <div
            role="meter"
            aria-label="Profile strength"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            className="bg-line my-2 h-1.5 overflow-hidden rounded-full"
          >
            <span className="bg-green block h-full" style={{ width: `${percent}%` }} />
          </div>
          {missing.length ? (
            <ul className="flex flex-wrap gap-1.5" aria-label="To make it stronger">
              {missing.map((item) => (
                <li key={item.label}>
                  <a
                    href={item.href}
                    className="border-green text-green text-meta inline-flex min-h-11 items-center rounded-full border border-dashed px-2.5 pointer-fine:min-h-7"
                  >
                    + {item.label}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-meta-lg text-green font-medium">Complete. You look great.</p>
          )}
        </div>
        <div className="lg:flex lg:flex-col">
          <Button variant="primary" onClick={() => setPreviewOpen(true)}>
            See how others see you
          </Button>
        </div>
      </section>

      <div className="mt-5 lg:mt-8 lg:grid lg:grid-cols-[210px_minmax(0,1fr)] lg:gap-12">
        <SectionNav />
        <div className="mt-4 flex max-w-[760px] min-w-0 flex-col gap-4 lg:mt-0">
          <Section id="s-basics" intro="Your name, where you are and what you do.">
            <div className="grid gap-3.5 lg:grid-cols-2">
              <Input
                label="Your name"
                hint="Shown only to people you are introduced to. It is never sent to an AI."
                autoComplete="given-name"
                maxLength={NAME_MAX}
                value={draft.name}
                onChange={(e) => set("name", e.target.value)}
              />
              <Input
                label="City"
                autoComplete="address-level2"
                maxLength={CITY_MAX}
                value={draft.city}
                onChange={(e) => set("city", e.target.value)}
              />
              <div className="lg:col-span-2">
                <Textarea
                  label="Headline"
                  hint="One line that says what you do or want to do."
                  rows={1}
                  maxLength={HEADLINE_MAX}
                  value={draft.headline}
                  onChange={(e) => set("headline", e.target.value.replace(/\n/g, " "))}
                  className="min-h-11 resize-none"
                />
              </div>
              <div className="flex flex-col gap-3 lg:col-span-2">
                <Textarea
                  label="About you"
                  hint="What you're good at, what you'd like to learn or build, and when you're free."
                  rows={6}
                  maxLength={ABOUT_MAX}
                  value={draft.about}
                  onChange={(e) => set("about", e.target.value)}
                />
                {needsConsent ? (
                  <label className="bg-green-tint border-green-line rounded-card flex items-start gap-3 border p-4">
                    <input
                      type="checkbox"
                      checked={consent}
                      onChange={(event) => setConsent(event.target.checked)}
                      className="accent-green mt-1 size-4 shrink-0"
                    />
                    <span className="text-meta-lg text-ink">
                      <AiConsentText />
                    </span>
                  </label>
                ) : null}
              </div>
              <fieldset className="flex flex-col gap-1 lg:col-span-2">
                <legend className="text-meta-lg text-ink mb-1 font-medium">
                  Languages you speak
                </legend>
                <div className="flex flex-wrap gap-x-5">
                  {LANGUAGES.map((language) => (
                    <label key={language.code} className="flex min-h-11 items-center gap-2">
                      <input
                        type="checkbox"
                        checked={draft.languages.includes(language.code)}
                        onChange={() =>
                          set(
                            "languages",
                            draft.languages.includes(language.code)
                              ? draft.languages.filter((c) => c !== language.code)
                              : [...draft.languages, language.code],
                          )
                        }
                        className="accent-green size-4 shrink-0"
                      />
                      <span>{language.label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <Select
                label="Experience level"
                value={draft.experience}
                onChange={(e) => set("experience", e.target.value as Draft["experience"])}
              >
                <option value="">Not set</option>
                {EXPERIENCE.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </div>
          </Section>

          <Section
            id="s-skills"
            intro="What you can offer, and what you want to learn. Matching uses both."
          >
            <div className="flex flex-col gap-5">
              <TagEditor
                label="I can help with"
                inputLabel="Add a skill you can offer"
                placeholder="Add a skill and press Enter"
                tags={draft.offers}
                suggestions={OFFER_SUGGESTIONS}
                onChange={(tags) => set("offers", tags)}
              />
              <TagEditor
                label="I want to learn"
                inputLabel="Add something you want to learn"
                placeholder="Add a topic and press Enter"
                tags={draft.seeks}
                suggestions={LEARN_SUGGESTIONS}
                variant="learn"
                onChange={(tags) => set("seeks", tags)}
              />
              <p className="text-meta-lg">
                <TextLink href="/you?review=1">
                  Check what we understood from your description
                </TextLink>
              </p>
            </div>
          </Section>

          <Section
            id="s-looking"
            intro={`Pick what you want from ${brand.name}. You can change this any time.`}
          >
            <div className="flex flex-col gap-4">
              <div>
                <Label>Intent</Label>
                <Toggles
                  label="Intent"
                  variant="chips"
                  options={INTENT_CHOICES}
                  selected={draft.intents}
                  onChange={(next) => set("intents", next)}
                />
              </div>
              <Textarea
                label="Your goal right now"
                hint="What you're working towards, in a sentence or two."
                rows={3}
                maxLength={GOAL_MAX}
                value={draft.goal}
                onChange={(e) => set("goal", e.target.value)}
              />
              <div>
                <Label>Working style</Label>
                <SegmentedControl
                  label="Working style"
                  segments={WORKING_STYLES}
                  value={draft.style}
                  onChange={(value) => set("style", value)}
                />
              </div>
              <Select
                label="Time you can give each week"
                value={draft.hours}
                onChange={(e) => set("hours", e.target.value as Draft["hours"])}
              >
                <option value="">Not set</option>
                {WEEKLY_HOURS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </div>
          </Section>

          <Section id="s-avail" intro="When you're usually free.">
            <div className="flex flex-col gap-4">
              <div>
                <Label>Days</Label>
                <Toggles
                  label="Days"
                  variant="days"
                  options={DAYS}
                  selected={draft.days}
                  onChange={(next) => set("days", next)}
                />
              </div>
              <div className="grid grid-cols-2 gap-2.5 sm:gap-3.5">
                <Select
                  label="From"
                  value={draft.from}
                  onChange={(e) => set("from", e.target.value)}
                >
                  <option value="">Not set</option>
                  {TIMES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
                <Select
                  label="Until"
                  value={draft.until}
                  onChange={(e) => set("until", e.target.value)}
                >
                  <option value="">Not set</option>
                  {TIMES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </div>
              <Select
                label="Time zone"
                value={draft.timezone}
                onChange={(e) => set("timezone", e.target.value)}
              >
                <option value="">Not set</option>
                {timezones.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </div>
          </Section>

          <Section
            id="s-links"
            intro="Show your work. Links are optional and shown after an intro is accepted."
          >
            <div className="flex flex-col gap-3">
              {LINK_ROWS.map((row, index) => (
                <div key={row.label} className="grid grid-cols-[36px_1fr] items-center gap-2.5">
                  <span
                    aria-hidden
                    className="border-line bg-panel text-ink-2 rounded-input flex size-9 items-center justify-center border font-mono text-[10px] uppercase"
                  >
                    {row.tile}
                  </span>
                  <Input
                    label={row.label}
                    hideLabel
                    type="url"
                    inputMode="url"
                    placeholder={row.placeholder}
                    value={draft.links[index] ?? ""}
                    onChange={(e) =>
                      set(
                        "links",
                        draft.links.map((l, i) => (i === index ? e.target.value : l)),
                      )
                    }
                  />
                </div>
              ))}
            </div>
          </Section>

          <Section id="s-privacy" intro="Who can find you, and what they see.">
            <div className="flex flex-col gap-4">
              <VisibilityToggle initial={profile.visibility} onSaved={setVisibility} />
              <div>
                <Label>Location shown as</Label>
                <SegmentedControl
                  label="Location shown as"
                  segments={LOCATION_CHOICES}
                  value={draft.location === "country" ? "hidden" : draft.location}
                  onChange={(value) => set("location", value)}
                />
                <p className="text-meta text-muted mt-1.5">
                  {draft.location === "city"
                    ? "People you match or connect with see your city."
                    : "People you match or connect with don't see where you are."}
                </p>
              </div>
            </div>
          </Section>

          <Section id="s-alerts" intro="Email only.">
            <div className="flex flex-col gap-2">
              <EmailToggle initial={profile.email_notifications} />
              <p className="text-meta-lg text-muted">
                Sign-in codes are always emailed when you ask for one.
              </p>
            </div>
          </Section>

          <Section id="s-security" intro="How you sign in.">
            <div className="flex flex-col gap-4">
              <Input
                label="Email"
                value={email}
                readOnly
                className="read-only:bg-panel read-only:text-ink-2"
              />
              <SignOutActions />
              {isModerator ? (
                <p>
                  <TextLink href="/moderation">Moderation</TextLink>
                </p>
              ) : null}
            </div>
          </Section>

          <Section id="s-data" intro="Read what you agreed to, and see who you've blocked.">
            <ul className="divide-line border-line flex flex-col divide-y border-t">
              <li className="flex items-center justify-between gap-4 py-3.5">
                <div>
                  <p className="font-semibold">Terms and privacy policy</p>
                  {termsVersion ? (
                    <p className="text-meta text-muted">You accepted version {termsVersion}.</p>
                  ) : null}
                </div>
                <p className="flex shrink-0 gap-4">
                  <TextLink href="/terms">Terms</TextLink>
                  <TextLink href="/privacy">Privacy policy</TextLink>
                </p>
              </li>
              <li className="flex items-center justify-between gap-4 py-3.5">
                <p className="font-semibold">People you&apos;ve blocked</p>
                <TextLink href="/settings/blocked">Blocked people</TextLink>
              </li>
            </ul>
          </Section>

          <Section id="s-danger" danger>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="font-semibold">Delete account</p>
              <DeleteAccount />
            </div>
          </Section>
        </div>
      </div>

      {dirty ? (
        <div
          role="region"
          aria-label="Unsaved changes"
          className="bg-ink text-bg rounded-panel fixed right-3 bottom-[calc(76px+env(safe-area-inset-bottom))] left-3 z-40 flex flex-col gap-2 py-2.5 pr-2.5 pl-4 sm:flex-row sm:items-center sm:justify-between lg:right-auto lg:bottom-6 lg:left-1/2 lg:w-[560px] lg:-translate-x-1/2"
        >
          <div className="flex flex-col">
            <p className="text-meta-lg">You have unsaved changes</p>
            {error ? (
              <p id={`${ids}-error`} role="alert" className="text-meta-lg text-bg font-medium">
                {error}
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 gap-1.5">
            <button
              type="button"
              onClick={discard}
              disabled={saving}
              className="rounded-control border-bg/40 text-bg hover:bg-ink-hover inline-flex h-11 items-center border px-3 text-[13px] font-medium pointer-fine:h-9"
            >
              Discard
            </button>
            <Button variant="white" size="compact" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </div>
      ) : null}
      <p
        role="status"
        className={cx(
          "bg-green text-bg text-meta-lg fixed bottom-[calc(84px+env(safe-area-inset-bottom))] left-1/2 z-50 -translate-x-1/2 rounded-full px-4 py-2 lg:bottom-24",
          saved ? "block" : "sr-only",
        )}
      >
        {saved ? "Saved." : ""}
      </p>

      <Dialog
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title="How others see you"
        description="This is what your card shows in someone else's matches. Your name and links appear only once you're connected."
      >
        <PreviewCard draft={draft} profile={profile} />
        <div className="flex justify-end">
          <Button variant="primary" onClick={() => setPreviewOpen(false)}>
            Close
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
