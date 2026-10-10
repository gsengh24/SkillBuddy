"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { InlineError, Input, Textarea } from "@/components/ds/fields";
import { cx } from "@/components/ui/cx";
import { browserApi } from "@/lib/api/browser";
import { teamPurposeSchema, teamSchema, type TeamPurpose } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { PURPOSE_LABELS } from "@/lib/teams/labels";

// The API's limits (TEAM_NAME_MAX_LENGTH, TEAM_DESCRIPTION_MAX_LENGTH).
const NAME_MAX = 60;
const DESCRIPTION_MAX = 300;

export const SELECT = cx(
  "rounded-input border-muted-2 bg-bg text-ink min-h-11 w-full border px-3 text-[16px] sm:text-body",
  "focus:border-green",
);

/** Make a team; its maker becomes the owner and first member (ADR 0016). */
export function CreateTeam() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState<TeamPurpose>("hackathon");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
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

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Input
        label="Team name"
        maxLength={NAME_MAX}
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Hack night crew"
      />
      <label className="flex flex-col gap-1">
        <span className="text-meta-lg text-ink font-medium">What is it for?</span>
        <select
          value={purpose}
          onChange={(event) => setPurpose(teamPurposeSchema.parse(event.target.value))}
          className={SELECT}
        >
          {teamPurposeSchema.options.map((option) => (
            <option key={option} value={option}>
              {PURPOSE_LABELS[option]}
            </option>
          ))}
        </select>
      </label>
      <Textarea
        label="A line about it (optional)"
        rows={2}
        maxLength={DESCRIPTION_MAX}
        showCounter={false}
        value={description}
        onChange={(event) => setDescription(event.target.value)}
      />
      {error ? <InlineError announce>{error}</InlineError> : null}
      <Button
        type="submit"
        variant="primary"
        className="self-start"
        disabled={busy || !name.trim()}
      >
        {busy ? "Creating…" : "Create team"}
      </Button>
    </form>
  );
}
