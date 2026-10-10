"use client";

import { useState } from "react";

import { Button } from "@/components/ds/button";
import { InlineError, Input } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema, teamLinkSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

function day(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

/**
 * The owner's invite link (ADR 0016). The link is shown only when it is made: the server
 * keeps a hash, not the code. Making a new one stops the old one.
 */
export function InviteLink({
  teamId,
  expiresAt,
  full,
}: {
  teamId: string;
  /** When the current link runs out; null without a live link. */
  expiresAt: string | null;
  full: boolean;
}) {
  const [expires, setExpires] = useState(expiresAt);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(describeError(caught));
    }
    setBusy(false);
  }

  function make() {
    void run(async () => {
      const made = await browserApi(`/teams/${teamId}/invite-link`, teamLinkSchema, {
        method: "POST",
      });
      setLink(`${window.location.origin}/teams/join/${made.code}`);
      setExpires(made.expires_at);
      setCopied(false);
    });
  }

  function turnOff() {
    void run(async () => {
      await browserApi(`/teams/${teamId}/invite-link`, noContentSchema, { method: "DELETE" });
      setLink(null);
      setExpires(null);
    });
  }

  async function copy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setError("Couldn't copy. Select the link and copy it yourself.");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-title text-ink">Invite link</h3>
      <p className="text-meta-lg text-muted">
        Anyone signed in who has the link can join straight away, while there is room. Share it only
        with people you want in the team.
      </p>
      {link ? (
        <div className="flex flex-col gap-2">
          <Input label="Link to share" value={link} readOnly onFocus={(e) => e.target.select()} />
          <p className="text-meta-lg text-muted" role="status">
            {copied ? "Copied. " : null}
            You won&apos;t be shown this link again. It works until {expires ? day(expires) : ""}.
          </p>
        </div>
      ) : expires ? (
        <p className="text-meta-lg text-ink-2">
          A link is active until {day(expires)}. Make a new one to see a link to share; the old one
          then stops working.
        </p>
      ) : null}
      {full ? (
        <p className="text-meta-lg text-muted">The team is full, so nobody can join.</p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {link ? (
          <Button variant="outline" size="compact" disabled={busy} onClick={copy}>
            Copy link
          </Button>
        ) : null}
        <Button variant="outline" size="compact" disabled={busy} onClick={make}>
          {expires ? "Make a new link" : "Make an invite link"}
        </Button>
        {expires ? (
          <Button variant="ghost" size="compact" disabled={busy} onClick={turnOff}>
            Turn off link
          </Button>
        ) : null}
      </div>
      {error ? <InlineError announce>{error}</InlineError> : null}
    </div>
  );
}
