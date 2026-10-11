"use client";

import { useRouter } from "next/navigation";
import { useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { Button } from "@/components/ds/button";
import { InlineError } from "@/components/ds/fields";
import { cx } from "@/components/ui/cx";
import { browserApi } from "@/lib/api/browser";
import { teamPurposeSchema, teamSchema, type TeamPurpose } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { SHORT_PURPOSE_LABELS } from "@/lib/teams/labels";

import { SpaceCard, type SpacePerson } from "./space-card";

// The API's limits (TEAM_NAME_MAX_LENGTH, TEAM_DESCRIPTION_MAX_LENGTH). The page shows 200 of
// the 300 allowed: a line, not an essay.
const NAME_MAX = 60;
const NAME_MIN = 2;
const DESCRIPTION_MAX = 200;

const FIELD =
  "rounded-input border-muted-2 bg-panel text-ink placeholder:text-muted-2 focus:border-mint w-full border px-3.5 py-3 text-[16px] outline-none";
const LABEL_ROW = "text-ink-2 mb-[7px] flex justify-between gap-3 text-[13px]";
const COUNT = "text-muted-2 font-mono text-[11px]";

/** A native select, shared with the member list's invite picker. */
export const SELECT = cx(
  "rounded-input border-muted-2 bg-bg text-ink min-h-11 w-full border px-3 text-[16px] sm:text-body",
  "focus:border-green",
);

const PURPOSES = teamPurposeSchema.options;

/**
 * Make a pair space (ADR 0016): name, what it is for and a line about it, with a live
 * preview of the card beside it from 1024px up. Its maker becomes the owner.
 */
export function CreateTeam({ me, maxMembers = 6 }: { me?: SpacePerson; maxMembers?: number }) {
  const router = useRouter();
  const ids = useId();
  const nameId = `${ids}-name`;
  const aboutId = `${ids}-about`;
  const purposeLabelId = `${ids}-purpose`;
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState<TeamPurpose>("hackathon");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const radios = useRef<(HTMLButtonElement | null)[]>([]);

  const ready = name.trim().length >= NAME_MIN;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const team = await browserApi("/teams", teamSchema, {
        method: "POST",
        body: { name: name.trim(), purpose, description: description.trim() },
      });
      router.push(`/teams/${team.id}`);
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  function pick(index: number) {
    const next = PURPOSES[(index + PURPOSES.length) % PURPOSES.length];
    if (!next) return;
    setPurpose(next);
    radios.current[PURPOSES.indexOf(next)]?.focus();
  }

  function onKeyDown(event: KeyboardEvent) {
    const at = PURPOSES.indexOf(purpose);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") pick(at + 1);
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") pick(at - 1);
    else return;
    event.preventDefault();
  }

  return (
    <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <form
        onSubmit={submit}
        noValidate
        className="border-line bg-card grid gap-4 rounded-[16px] border p-5"
      >
        <div>
          <div className={LABEL_ROW}>
            <label htmlFor={nameId}>Pair space name</label>
            <span aria-hidden className={COUNT}>
              {name.length} / {NAME_MAX}
            </span>
          </div>
          <input
            id={nameId}
            maxLength={NAME_MAX}
            autoComplete="off"
            placeholder="Hack night crew"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className={FIELD}
          />
        </div>

        <div>
          <span id={purposeLabelId} className={LABEL_ROW}>
            <span>What is it for?</span>
          </span>
          <div
            role="radiogroup"
            aria-labelledby={purposeLabelId}
            onKeyDown={onKeyDown}
            className="border-muted-2 bg-panel grid grid-cols-2 gap-1.5 rounded-[12px] border p-1 sm:grid-cols-4"
          >
            {PURPOSES.map((option, index) => {
              const on = option === purpose;
              return (
                <button
                  key={option}
                  ref={(node) => {
                    radios.current[index] = node;
                  }}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  tabIndex={on ? 0 : -1}
                  onClick={() => setPurpose(option)}
                  className={cx(
                    "min-h-10 rounded-[9px] px-1.5 py-2.5 text-[14px] transition-colors",
                    on ? "bg-mint text-bg font-semibold" : "text-muted hover:text-ink",
                  )}
                >
                  {SHORT_PURPOSE_LABELS[option]}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div className={LABEL_ROW}>
            <label htmlFor={aboutId}>A line about it (optional)</label>
            <span aria-hidden className={COUNT}>
              {description.length} / {DESCRIPTION_MAX}
            </span>
          </div>
          <textarea
            id={aboutId}
            maxLength={DESCRIPTION_MAX}
            placeholder="Building a campus food-waste tracker for the October hackathon."
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className={cx(FIELD, "min-h-[84px] resize-y")}
          />
        </div>

        {error ? <InlineError announce>{error}</InlineError> : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-mono-lg text-muted font-mono uppercase">
            Up to {maxMembers} people · invite them after
          </span>
          <Button
            type="submit"
            variant="primary"
            className="max-sm:flex-1"
            disabled={busy || !ready}
          >
            {busy ? "Creating…" : "Create pair space"}
          </Button>
        </div>
      </form>

      <div
        aria-hidden
        className="border-line-strong hidden content-start gap-3.5 rounded-[16px] border border-dashed p-[18px] lg:grid"
      >
        <span className="text-mono-lg text-muted font-mono uppercase">Preview</span>
        <SpaceCard
          purpose={purpose}
          name={name}
          description={description || "A line about it shows here."}
          isOwner
          people={me ? [me] : []}
          memberCount={1}
          maxMembers={maxMembers}
        />
      </div>
    </div>
  );
}
