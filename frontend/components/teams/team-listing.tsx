"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { InlineError, Textarea } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { teamSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

// The API's limit (TEAM_LOOKING_FOR_MAX_LENGTH).
const LOOKING_FOR_MAX = 200;

/**
 * The owner's switch for listing the team (ADR 0016): a listed team can be found by any
 * signed-in person, who may ask to join. The owner still decides who gets in.
 */
export function TeamListing({
  teamId,
  listed,
  lookingFor,
}: {
  teamId: string;
  listed: boolean;
  lookingFor: string;
}) {
  const [on, setOn] = useState(listed);
  const [text, setText] = useState(lookingFor);
  const [saved, setSaved] = useState({ on: listed, text: lookingFor });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const changed = on !== saved.on || text.trim() !== saved.text;

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const team = await browserApi(`/teams/${teamId}`, teamSchema, {
        method: "PATCH",
        body: { listed: on, looking_for: text.trim() },
      });
      setSaved({ on: team.listed, text: team.looking_for });
      setOn(team.listed);
      setText(team.looking_for);
    } catch (caught) {
      setError(describeError(caught));
    }
    setBusy(false);
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-3">
      <h3 className="text-title text-ink">Let people find this team</h3>
      <label className="flex min-h-11 items-start gap-3">
        <input
          type="checkbox"
          checked={on}
          onChange={(event) => setOn(event.target.checked)}
          className="accent-green mt-1 size-4 shrink-0"
        />
        <span className="flex flex-col">
          <span className="text-ink font-medium">List this team</span>
          <span className="text-meta-lg text-muted">
            Anyone signed in can see its name, purpose, size and the line below, and ask to join.
            You decide who gets in.
          </span>
        </span>
      </label>
      <Textarea
        label="Who are you looking for?"
        rows={2}
        maxLength={LOOKING_FOR_MAX}
        showCounter={false}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="A designer who can prototype fast"
      />
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="outline" size="compact" disabled={busy || !changed}>
          Save listing
        </Button>
        <p className="text-meta-lg text-muted" role="status">
          {saved.on ? "This team is listed." : "This team is not listed."}
        </p>
      </div>
    </form>
  );
}
