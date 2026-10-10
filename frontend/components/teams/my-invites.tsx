"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ds/button";
import { InlineError } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { teamInviteSchema, type TeamInvite } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { PURPOSE_LABELS, teamSize } from "@/lib/teams/labels";

/** Invites to teams waiting for the person's answer. Nobody joins without their own yes. */
export function MyTeamInvites({ initial }: { initial: TeamInvite[] }) {
  const router = useRouter();
  const [invites, setInvites] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function answer(invite: TeamInvite, accept: boolean) {
    setBusy(true);
    setError(null);
    try {
      await browserApi(`/teams/invites/${invite.id}/respond`, teamInviteSchema, {
        method: "POST",
        body: { accept },
      });
      if (accept) {
        router.push(`/teams/${invite.team.id}`);
        return;
      }
      setInvites((current) => current.filter((item) => item.id !== invite.id));
    } catch (caught) {
      setError(describeError(caught));
    }
    setBusy(false);
  }

  if (!invites.length) return null;

  return (
    <section aria-labelledby="team-invites-h" className="flex flex-col gap-3">
      <h2 id="team-invites-h" className="text-title">
        Invites
      </h2>
      <ul className="border-line border-t">
        {invites.map((invite) => (
          <li
            key={invite.id}
            className="border-line flex flex-wrap items-center justify-between gap-3 border-b py-3"
          >
            <div className="min-w-0">
              <h3 className="text-ink font-semibold break-words">{invite.team.name}</h3>
              <p className="text-meta text-muted">
                {PURPOSE_LABELS[invite.team.purpose]} ·{" "}
                {teamSize(invite.team.member_count, invite.team.max_members)}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="compact"
                disabled={busy}
                onClick={() => answer(invite, true)}
                aria-label={`Join ${invite.team.name}`}
              >
                Join
              </Button>
              <Button
                variant="ghost"
                size="compact"
                disabled={busy}
                onClick={() => answer(invite, false)}
                aria-label={`Decline the invite to ${invite.team.name}`}
              >
                Decline
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {error ? <InlineError announce>{error}</InlineError> : null}
    </section>
  );
}
