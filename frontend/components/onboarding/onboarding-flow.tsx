"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ds/button";
import { StepProgress } from "@/components/ds/choices";
import { InlineError } from "@/components/ds/fields";
import { ArrowRightIcon, CheckIcon } from "@/components/ds/icons";
import { Logo } from "@/components/ds/logo";
import { TwoToneHeadline } from "@/components/ds/page-parts";
import { cx } from "@/components/ui/cx";
import { browserApi } from "@/lib/api/browser";
import { onboardingSchema, type Onboarding } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { brand } from "@/lib/brand";
import { STEPS, stepAfter, stepNumber, stepToShow, type Step } from "@/lib/onboarding/steps";

import {
  AboutStep,
  draftsFrom,
  IntentsStep,
  OffersStep,
  TradeSummary,
  WantsStep,
  type Drafts,
} from "./steps";

/** Where the last step hands over until "check what we understood" exists (ADR 0022). */
export const DESCRIBE_PATH = "/onboarding/describe";

const HEADINGS: Record<Step, { lead: string; rest: string; eyebrow?: string }> = {
  intents: {
    lead: "What brings you here?",
    rest: "Pick all that fit.",
    eyebrow: `Welcome to ${brand.displayName}`,
  },
  offers: { lead: "What are you good at?", rest: "Tap a few. You can change these later." },
  wants: { lead: "What are you looking for?", rest: "Skills you want to learn or find." },
  about: { lead: "Almost done.", rest: "A few quick details." },
};

/** The body of each step save (PUT /me/onboarding/{step}). */
function bodyFor(step: Step, drafts: Drafts): unknown {
  switch (step) {
    case "intents":
      return { intents: drafts.intents };
    case "offers":
      return { skills: drafts.offers };
    case "wants":
      return {
        skills: drafts.wants.skills,
        interests: drafts.wants.interests,
        note: drafts.wants.note.trim(),
      };
    case "about": {
      const { display_name, ...rest } = drafts.about;
      // An empty name is left as it is (the API needs at least one character).
      return display_name.trim() ? { ...rest, display_name: display_name.trim() } : rest;
    }
  }
}

function countFor(step: Step, drafts: Drafts): number | null {
  if (step === "intents") return drafts.intents.length;
  if (step === "offers") return drafts.offers.length;
  if (step === "wants") return drafts.wants.skills.length + drafts.wants.interests.length;
  return null;
}

/**
 * Onboarding steps 1–4 (mockups 01–04). Each step saves when the person continues or skips,
 * so leaving and coming back resumes at the right step. The step shown follows `?step=`
 * (so the browser's back button works) when the person has reached it, else their progress.
 */
export function OnboardingFlow({
  initial,
  requested = null,
}: {
  initial: Onboarding;
  /** The `?step=` the page was opened with. */
  requested?: string | null;
}) {
  const router = useRouter();
  const [asked, setAsked] = useState(requested);
  const [progress, setProgress] = useState(initial);
  const [drafts, setDrafts] = useState(() => draftsFrom(initial));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const shown = stepToShow(asked, progress);

  // The browser's back and forward buttons move between steps.
  useEffect(() => {
    const onPop = () => setAsked(new URLSearchParams(window.location.search).get("step"));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const step: Step = shown === "review" ? "about" : shown;
  const number = stepNumber(step);
  const heading = HEADINGS[step];
  const count = countFor(step, drafts);
  const blocked = step === "intents" && drafts.intents.length === 0;

  function go(next: Step | "review") {
    setError(null);
    if (next === "review") {
      router.push(DESCRIBE_PATH);
      return;
    }
    window.history.pushState(null, "", `?step=${next}`);
    setAsked(next);
    window.scrollTo({ top: 0 });
  }

  async function save(kind: "save" | "skip") {
    setBusy(true);
    setError(null);
    try {
      const saved =
        kind === "save"
          ? await browserApi(`/me/onboarding/${step}`, onboardingSchema, {
              method: "PUT",
              body: bodyFor(step, drafts),
            })
          : await browserApi(`/me/onboarding/${step}/skip`, onboardingSchema, {
              method: "POST",
            });
      setProgress(saved);
      go(stepAfter(step));
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  const set =
    <K extends keyof Drafts>(key: K) =>
    (value: Drafts[K]) =>
      setDrafts((current) => ({ ...current, [key]: value }));

  const wide = step === "wants";

  return (
    <div className="bg-bg flex min-h-dvh flex-col">
      <header className="flex items-center justify-between gap-4 px-4 py-3.5 lg:px-8 lg:py-6">
        <Logo />
        <span className="text-mono-lg text-muted font-mono uppercase">
          Step {number} of {STEPS.length}
        </span>
      </header>
      <div
        className={cx(
          "w-full px-4 lg:mx-auto lg:px-0",
          wide ? "lg:max-w-[960px]" : "lg:max-w-[640px]",
        )}
      >
        <StepProgress step={number} total={STEPS.length} label="Profile setup" />
      </div>

      <main
        key={step}
        className={cx(
          "mx-auto grid w-full content-start gap-6 px-4 pt-6 pb-6 lg:gap-8 lg:px-0 lg:pt-12 lg:pb-8",
          wide
            ? "max-w-[640px] lg:max-w-[960px] lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start lg:gap-x-12"
            : "max-w-[640px]",
        )}
      >
        <div className={cx("grid gap-6 lg:gap-8", wide && "lg:col-start-1")}>
          <div>
            {heading.eyebrow ? (
              <p className="text-mono-lg text-green font-mono uppercase">{heading.eyebrow}</p>
            ) : null}
            <TwoToneHeadline as="h1" size="greeting" lead={heading.lead} rest={heading.rest} />
          </div>
          {wide ? (
            <TradeSummary
              className="lg:hidden"
              offers={drafts.offers}
              wants={drafts.wants.skills}
              onEditOffers={() => go("offers")}
            />
          ) : null}
          {step === "intents" ? (
            <IntentsStep value={drafts.intents} onChange={set("intents")} />
          ) : step === "offers" ? (
            <OffersStep value={drafts.offers} onChange={set("offers")} />
          ) : step === "wants" ? (
            <WantsStep offers={drafts.offers} value={drafts.wants} onChange={set("wants")} />
          ) : (
            <AboutStep value={drafts.about} onChange={set("about")} />
          )}
        </div>
        {wide ? (
          <TradeSummary
            className="hidden lg:sticky lg:top-6 lg:col-start-2 lg:row-start-1 lg:block"
            offers={drafts.offers}
            wants={drafts.wants.skills}
            onEditOffers={() => go("offers")}
          />
        ) : null}
      </main>

      <footer
        className={cx(
          "border-line bg-bg sticky bottom-0 mt-auto flex flex-col gap-2 border-t px-4 py-3 pb-[max(12px,env(safe-area-inset-bottom))]",
          "lg:static lg:mx-auto lg:mb-12 lg:w-full lg:border-0 lg:bg-transparent lg:px-0 lg:pt-5",
          wide ? "lg:max-w-[960px]" : "lg:max-w-[640px]",
        )}
      >
        {error ? <InlineError announce>{error}</InlineError> : null}
        <div className="flex items-center gap-2">
          {step === "intents" ? null : (
            <Button variant="ghost" disabled={busy} onClick={() => save("skip")}>
              Skip for now
            </Button>
          )}
          <span className="flex-1" />
          {count === null ? null : (
            <span
              role="status"
              aria-live="polite"
              className="text-mono-lg text-muted font-mono uppercase"
            >
              {count} selected
            </span>
          )}
          <Button variant="primary" disabled={busy || blocked} onClick={() => save("save")}>
            {step === "about" ? "Finish" : "Continue"}
            {step === "about" ? (
              <CheckIcon className="size-4" />
            ) : (
              <ArrowRightIcon className="size-4" />
            )}
          </Button>
        </div>
      </footer>
    </div>
  );
}
