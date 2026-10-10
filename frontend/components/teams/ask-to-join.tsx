"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { InlineError, Textarea } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema, teamInviteSchema, type TeamInvite } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

// The API's limit (TEAM_REQUEST_NOTE_MAX_LENGTH).
const NOTE_MAX = 300;

/** Ask a listed team's owner to let you in, with a short note (ADR 0016). */
export function AskToJoin({
  teamId,
  teamName,
  asked,
}: {
  teamId: string;
  teamName: string;
  /** The person already has an open request for this team. */
  asked: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(asked);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await browserApi(`/teams/${teamId}/requests`, teamInviteSchema, {
        method: "POST",
        body: { note: note.trim() },
      });
      setDone(true);
      setOpen(false);
    } catch (caught) {
      setError(describeError(caught));
    }
    setBusy(false);
  }

  if (done) {
    return (
      <p className="text-meta-lg text-muted" role="status">
        You asked to join. The owner has 14 days to answer.
      </p>
    );
  }
  if (!open) {
    return (
      <Button
        variant="outline"
        size="compact"
        onClick={() => setOpen(true)}
        aria-label={`Ask to join ${teamName}`}
      >
        Ask to join
      </Button>
    );
  }
  return (
    <form onSubmit={send} className="flex w-full flex-col gap-3">
      <Textarea
        label={`A note to the owner of ${teamName} (optional)`}
        rows={2}
        maxLength={NOTE_MAX}
        showCounter={false}
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <p className="text-meta-lg text-muted">
        The owner will see your name and this note. If they say yes, everyone in the team will see
        your name.
      </p>
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="outline" size="compact" disabled={busy}>
          Send request
        </Button>
        <Button variant="ghost" size="compact" disabled={busy} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** The person's own open requests to join, each with a way to take it back. */
export function MyTeamRequests({ initial }: { initial: TeamInvite[] }) {
  const [requests, setRequests] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function takeBack(request: TeamInvite) {
    setBusy(true);
    setError(null);
    try {
      await browserApi(`/teams/invites/${request.id}`, noContentSchema, { method: "DELETE" });
      setRequests((current) => current.filter((item) => item.id !== request.id));
    } catch (caught) {
      setError(describeError(caught));
    }
    setBusy(false);
  }

  if (!requests.length) return null;

  return (
    <section aria-labelledby="team-requests-h" className="flex flex-col gap-3">
      <h2 id="team-requests-h" className="text-title">
        Teams you asked to join
      </h2>
      <ul className="border-line border-t">
        {requests.map((request) => (
          <li
            key={request.id}
            className="border-line flex flex-wrap items-center justify-between gap-3 border-b py-3"
          >
            <div className="min-w-0">
              <h3 className="text-ink font-semibold break-words">{request.team.name}</h3>
              <p className="text-meta text-muted">Waiting for the owner&apos;s answer</p>
            </div>
            <Button
              variant="ghost"
              size="compact"
              disabled={busy}
              onClick={() => takeBack(request)}
              aria-label={`Take back your request to join ${request.team.name}`}
            >
              Take back
            </Button>
          </li>
        ))}
      </ul>
      {error ? <InlineError announce>{error}</InlineError> : null}
    </section>
  );
}
