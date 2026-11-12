import { ButtonLink } from "@/components/ds/button";
import { BuddyIcon, CheckIcon } from "@/components/ds/icons";
import { cx } from "@/components/ui/cx";
import type { Onboarding } from "@/lib/api/schemas";

const STEPS: Record<Onboarding["steps"][number]["step"], { label: string; time: string }> = {
  intents: { label: "What brings you here", time: "10 sec" },
  offers: { label: "What you're good at", time: "20 sec" },
  wants: { label: "What you're looking for", time: "20 sec" },
  about: { label: "A bit about you", time: "15 sec" },
};

/**
 * Home with an unfinished profile (ADR 0022, screen 8): in place of the empty inbox, the
 * strength meter, the steps left and one way on. The social-proof line under it is an
 * aggregate count from the API, shown only when it is high enough to say.
 */
export function FinishProfile({
  progress,
  demand,
}: {
  progress: Onboarding;
  /** People who want the person's first offered skill this week, or null to hide it. */
  demand: { skill: string; count: number } | null;
}) {
  const percent = progress.strength?.percent ?? 0;
  const left = progress.steps.filter((step) => step.state !== "saved").length;
  return (
    <>
      <section
        aria-labelledby="finish-h"
        className="bg-green-tint border-green-line text-ink rounded-panel flex flex-col gap-3.5 border p-4"
      >
        <div>
          <p className="text-mono-lg text-green font-mono uppercase">Your profile</p>
          <h3 id="finish-h" className="text-title-lg mt-1">
            Finish your profile. <span className="text-ink-2">Then we can match you.</span>
          </h3>
        </div>
        <div>
          <div className="flex items-baseline justify-between">
            <span className="text-mono text-muted font-mono uppercase">Profile strength</span>
            <span className="font-display tracking-display text-[22px] font-extrabold">
              {percent}
              <small className="text-[13px]">%</small>
            </span>
          </div>
          <div
            role="meter"
            aria-label="Profile strength"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            className="bg-green-line mt-2 h-1.5 overflow-hidden rounded-full"
          >
            <span className="bg-green block h-full" style={{ width: `${percent}%` }} />
          </div>
        </div>
        <ul className="flex flex-col gap-2" aria-label="Steps">
          {progress.steps.map(({ step, state }) => {
            const done = state === "saved";
            return (
              <li key={step} className="text-meta-lg flex items-center gap-2.5">
                <span
                  className={cx(
                    "grid size-5 shrink-0 place-items-center rounded-full border",
                    done ? "bg-green border-green text-bg" : "border-muted-2",
                  )}
                >
                  {done ? <CheckIcon className="size-3" /> : null}
                </span>
                <span className={cx("flex-1", done && "text-ink-2")}>
                  {STEPS[step].label}
                  <span className="sr-only">{done ? ", done" : ", to do"}</span>
                </span>
                {done ? null : (
                  <span className="text-mono text-muted font-mono">{STEPS[step].time}</span>
                )}
              </li>
            );
          })}
        </ul>
        <p className="text-mono text-muted font-mono uppercase">
          {left === 0
            ? "Just check your card"
            : `${left} quick ${left === 1 ? "step" : "steps"} left`}
        </p>
        <ButtonLink href="/onboarding" variant="primary" className="w-full">
          Finish in 60 seconds
        </ButtonLink>
      </section>
      {demand ? (
        <p className="text-on-dark-2 flex items-start gap-2.5 text-[13px] leading-snug">
          <BuddyIcon className="text-on-dark mt-0.5 size-4 shrink-0" />
          <span>
            <b className="text-on-dark">{demand.count} people</b> are looking for {demand.skill}{" "}
            skills this week. Finish your profile to be matched.
          </span>
        </p>
      ) : null}
    </>
  );
}
