"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ds/button";
import { StepProgress } from "@/components/ds/choices";
import { InlineError, Textarea } from "@/components/ds/fields";
import { ArrowRightIcon, ClockIcon, PersonIcon, SparkIcon } from "@/components/ds/icons";
import { Logo } from "@/components/ds/logo";
import { TwoToneHeadline } from "@/components/ds/page-parts";
import { Skeleton, TopicChip, WhyPanel } from "@/components/ds/surfaces";
import { browserApi } from "@/lib/api/browser";
import { profileSchema, type Profile } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { intents as INTENT_LABELS } from "@/lib/design/tokens";
import { BRANCHES, DAYS, HOURS, YEARS } from "@/lib/onboarding/catalog";

/** The about text's cap (the API's, ADR 0022). */
export const ABOUT_MAX = 500;
/** How often, and how many times, to look for the AI's version before showing the template. */
export const POLL_MS = 1500;
export const MAX_POLLS = 10;

export type CheckState = "loading" | "ready" | "fallback";

/** Which card to show: the AI's (ready), the template's (fallback), or the skeleton. */
export function checkState(profile: Profile | null, gaveUp: boolean): CheckState {
  if (profile === null) return gaveUp ? "fallback" : "loading";
  if (profile.parse_status === "pending") return gaveUp ? "fallback" : "loading";
  return profile.parse_source === "llm" ? "ready" : "fallback";
}

function listed(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
}

/** The card heading: the composed title, or one made from the picks. */
export function cardTitle(profile: Profile): string {
  const title = profile.understanding?.title?.trim();
  if (title) return title;
  if (profile.offer_skills.length) return `Offers ${listed(profile.offer_skills.slice(0, 3))}`;
  if (profile.want_skills.length) return `Looking for ${listed(profile.want_skills.slice(0, 3))}`;
  return "New here";
}

/** "2nd year · Computer Engineering". */
export function cardMeta(profile: Profile): string {
  const year = YEARS.find((y) => y.value === profile.study_year);
  const branch = BRANCHES.find((b) => b.value === profile.branch);
  const yearText = year ? (year.value === "postgrad" ? year.label : `${year.label} year`) : "";
  return [yearText, branch?.label ?? ""].filter(Boolean).join(" · ");
}

/** "Weekends · 4–6 h/week", from the stored availability. */
export function cardAvailability(profile: Profile): string {
  const fromApi = profile.understanding?.availability?.trim();
  if (fromApi) return fromApi;
  const days = new Set(profile.available_days);
  const weekend = days.size === 2 && days.has("sat") && days.has("sun");
  const weekdays = days.size === 5 && !days.has("sat") && !days.has("sun");
  const when =
    days.size === 7
      ? "Any day"
      : weekend
        ? "Weekends"
        : weekdays
          ? "Weekdays"
          : DAYS.filter((d) => days.has(d.value))
              .map((d) => d.short)
              .join(", ");
  const hours = HOURS.find((h) => h.value === profile.weekly_hours);
  return [when, hours ? `${hours.label} h/week` : ""].filter(Boolean).join(" · ");
}

function ChipRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <dt className="text-mono-lg text-muted font-mono uppercase">{label}</dt>
      <dd className="flex flex-wrap gap-1.5">{children}</dd>
    </div>
  );
}

function Anon() {
  return (
    <span className="border-muted-2 bg-panel text-muted grid size-10 shrink-0 place-items-center rounded-full border border-dashed">
      <PersonIcon className="size-[18px]" />
    </span>
  );
}

const CARD = "bg-card border-line grid gap-3.5 rounded-[12px] border p-4 lg:p-6";

function LoadingCard() {
  return (
    <article aria-busy="true" aria-label="Your match card is loading" className={CARD}>
      <div className="flex items-start gap-3">
        <Anon />
        <div className="grid flex-1 gap-2 pt-0.5">
          <Skeleton className="h-3.5 w-[78%] rounded-full" />
          <Skeleton className="h-2.5 w-[42%] rounded-full" />
        </div>
      </div>
      <div className="grid gap-2">
        <Skeleton className="h-3 rounded-full" />
        <Skeleton className="h-3 w-[86%] rounded-full" />
      </div>
      <div className="flex flex-wrap gap-1.5">
        {["w-16", "w-[72px]", "w-14", "w-20"].map((width) => (
          <Skeleton key={width} className={`h-6 rounded-full ${width}`} />
        ))}
      </div>
      <p role="status" className="text-meta-lg text-ink-2 inline-flex items-center gap-2">
        <SparkIcon className="text-green size-4 shrink-0" />
        Reading your profile… this takes a few seconds.
      </p>
    </article>
  );
}

/**
 * The anonymous match card (content rules, ADR 0022): no name, photo or contact details;
 * a heading, one sentence, topic chips, intents and availability.
 */
function MatchCard({ profile, state }: { profile: Profile; state: "ready" | "fallback" }) {
  const meta = cardMeta(profile);
  const availability = cardAvailability(profile);
  const summary = state === "ready" ? profile.understanding?.summary.trim() : "";
  return (
    <article aria-label="Preview of your match card" className={CARD}>
      <div className="flex items-start gap-3">
        <Anon />
        <div>
          <h2 className="text-body lg:text-body-lg font-semibold">{cardTitle(profile)}</h2>
          {meta ? <p className="text-mono-lg text-muted mt-1 font-mono">{meta}</p> : null}
        </div>
      </div>
      {summary ? <p className="text-ink-2 lg:text-body-lg">{summary}</p> : null}
      <dl className="grid gap-3.5">
        {profile.offer_skills.length ? (
          <ChipRow label="Offers">
            {profile.offer_skills.map((skill) => (
              <TopicChip key={skill}>{skill}</TopicChip>
            ))}
          </ChipRow>
        ) : null}
        {profile.want_skills.length ? (
          <ChipRow label="Looking for">
            {profile.want_skills.map((skill) => (
              <TopicChip key={skill}>{skill}</TopicChip>
            ))}
          </ChipRow>
        ) : null}
        {profile.interest_tags.length ? (
          <ChipRow label="Into">
            {profile.interest_tags.map((tag) => (
              <TopicChip key={tag}>{tag}</TopicChip>
            ))}
          </ChipRow>
        ) : null}
        {profile.intents.length ? (
          <ChipRow label="Here for">
            {profile.intents.map((intent) => (
              <span
                key={intent}
                className="bg-green-tint border-green-line text-ink text-meta inline-flex items-center rounded-full border px-2.5 py-1 font-medium"
              >
                {INTENT_LABELS[intent].label}
              </span>
            ))}
          </ChipRow>
        ) : null}
      </dl>
      {availability ? (
        <p className="text-meta-lg text-ink-2 inline-flex items-center gap-2">
          <ClockIcon className="text-green size-4 shrink-0" />
          <span>
            <span className="sr-only">Free: </span>
            {availability}
          </span>
        </p>
      ) : null}
      {state === "ready" ? (
        <WhyPanel title="Why you match">
          <span className="text-meta-lg">
            Each person also sees one line on why you fit them, like “Both into ML hackathons; they
            build backends and want a frontend partner.”
          </span>
        </WhyPanel>
      ) : (
        <p className="text-meta-lg text-muted border-line border-t pt-3">
          We&apos;ll polish this shortly.
        </p>
      )}
    </article>
  );
}

/**
 * Onboarding step 5 (mockup 05): the anonymous card others will see, built in the
 * background from the picks. Polls the profile while the AI writes; if it takes too long or
 * the AI is off, the template version is shown, never an error. "Looks good" keeps the about
 * text (edited or not) and finishes onboarding.
 */
export function ProfileCheck() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [polls, setPolls] = useState(0);
  const [draft, setDraft] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const gaveUp = polls >= MAX_POLLS;
  const state = checkState(profile, gaveUp);
  const waiting = state === "loading";

  useEffect(() => {
    if (!waiting) return;
    const timer = window.setTimeout(
      async () => {
        try {
          const latest = await browserApi("/me/profile", profileSchema);
          setProfile(latest);
        } catch {
          // A failed poll is retried on the next tick; the fallback shows after the last.
        }
        setPolls((count) => count + 1);
      },
      polls === 0 ? 0 : POLL_MS,
    );
    return () => window.clearTimeout(timer);
  }, [waiting, polls]);

  // The text follows the latest version until the person changes it.
  const about = touched ? draft : (profile?.about_text ?? "");

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await browserApi("/me/onboarding/complete", profileSchema, {
        method: "POST",
        body: { about_text: about.trim() },
      });
      router.push("/home");
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  return (
    <div className="bg-bg flex min-h-dvh flex-col">
      <header className="flex items-center justify-between gap-4 px-4 py-3.5 lg:px-8 lg:py-6">
        <Logo />
        <span className="text-mono-lg text-muted font-mono uppercase">Review</span>
      </header>
      <div className="w-full px-4 lg:mx-auto lg:max-w-[640px] lg:px-0">
        <StepProgress step={4} total={4} label="Profile setup" />
      </div>

      <main className="mx-auto grid w-full max-w-[640px] content-start gap-6 px-4 pt-6 pb-6 lg:gap-8 lg:px-0 lg:pt-12 lg:pb-8">
        <div className="grid gap-2">
          <p className="text-mono-lg text-green font-mono uppercase">Your profile</p>
          <TwoToneHeadline as="h1" size="greeting" lead="Here's how others" rest="will see you." />
          <p className="text-muted">
            Matches see this card, never your name. Names show only after you both accept an intro.
          </p>
        </div>

        {state === "loading" || profile === null ? (
          <LoadingCard />
        ) : (
          <MatchCard profile={profile} state={state} />
        )}

        <Textarea
          label="About you"
          hint="Used for matching. We wrote this from your picks. Change anything that's off."
          rows={4}
          maxLength={ABOUT_MAX}
          value={about}
          disabled={profile === null}
          onChange={(event) => {
            setTouched(true);
            setDraft(event.target.value);
          }}
        />
      </main>

      <footer className="border-line bg-bg sticky bottom-0 mt-auto flex flex-col gap-2 border-t px-4 py-3 pb-[max(12px,env(safe-area-inset-bottom))] lg:static lg:mx-auto lg:mb-12 lg:w-full lg:max-w-[640px] lg:border-0 lg:bg-transparent lg:px-0 lg:pt-5">
        {error ? <InlineError announce>{error}</InlineError> : null}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => router.push("/onboarding?step=offers")}
          >
            Edit
          </Button>
          <span className="flex-1" />
          <Button
            variant="primary"
            disabled={busy || profile === null || !about.trim()}
            onClick={confirm}
          >
            Looks good
            <ArrowRightIcon className="size-4" />
          </Button>
        </div>
      </footer>
    </div>
  );
}
