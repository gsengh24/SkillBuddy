"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { InlineError, Textarea } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { matchRequestSchema, teamInviteSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { itemHref } from "@/lib/home/activity";

// The API's limits (REQUEST_TEXT_MIN_LENGTH, REQUEST_TEXT_MAX_LENGTH).
const TEXT_MIN = 10;
const TEXT_MAX = 1000;

/**
 * The owner asks the matcher for a teammate (ADR 0016). It is an ordinary match request
 * tied to the team: people already in the team are left out, and a match can be invited.
 */
export function FindTeammate({ teamId, full }: { teamId: string; full: boolean }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = text.trim().length >= TEXT_MIN;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const created = await browserApi("/requests", matchRequestSchema, {
        method: "POST",
        body: { text: text.trim(), team_id: teamId },
      });
      router.push(itemHref("request", created.id));
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <h3 className="text-title text-ink">Find a teammate</h3>
      {full ? (
        <p className="text-meta-lg text-muted">
          The team is full, so there is no room to add anyone.
        </p>
      ) : (
        <>
          <Textarea
            label="Who does the team need?"
            rows={2}
            maxLength={TEXT_MAX}
            showCounter={false}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="A designer who can prototype fast, free this weekend"
          />
          <p className="text-meta-lg text-muted">
            We suggest people who fit. You can invite a suggestion to the team; they see why they
            were suggested and decide. This counts as one of your requests for today.
          </p>
          {error ? <InlineError announce>{error}</InlineError> : null}
          <Button
            type="submit"
            variant="outline"
            size="compact"
            className="self-start"
            disabled={busy || !ready}
          >
            {busy ? "Asking…" : "Find people"}
          </Button>
        </>
      )}
    </form>
  );
}

/** On a match for a team's request: invite that person to the team. */
export function InviteMatchToTeam({ teamId, matchId }: { teamId: string; matchId: string }) {
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  async function invite() {
    setState("busy");
    setError(null);
    try {
      await browserApi(`/teams/${teamId}/invites`, teamInviteSchema, {
        method: "POST",
        body: { match_id: matchId },
      });
      setState("sent");
    } catch (caught) {
      setError(describeError(caught));
      setState("idle");
    }
  }

  if (state === "sent") {
    return (
      <p className="text-meta-lg text-ink font-medium" role="status">
        Invited to the team. They have 14 days to answer.
      </p>
    );
  }
  return (
    <div className="flex flex-col items-start gap-2">
      <Button variant="outline" disabled={state === "busy"} onClick={invite}>
        Invite to team
      </Button>
      <p className="text-meta-lg text-muted">
        They&apos;ll see the team&apos;s name and size and why they were suggested, not who is in
        it.
      </p>
      {error ? <InlineError announce>{error}</InlineError> : null}
    </div>
  );
}
