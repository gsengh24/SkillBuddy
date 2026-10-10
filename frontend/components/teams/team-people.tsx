"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Avatar } from "@/components/ds/avatar";
import { Button } from "@/components/ds/button";
import { InlineError } from "@/components/ds/fields";
import { Panel } from "@/components/ds/surfaces";
import { browserApi } from "@/lib/api/browser";
import {
  noContentSchema,
  teamInviteSchema,
  type Team,
  type TeamInvite,
  type TeamMember,
} from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

import { SELECT } from "./create-team";

export type Invitable = { userId: string; name: string };

/** What to call a teammate: their display name, or a fallback when they haven't set one. */
export function memberName(member: TeamMember | undefined): string {
  return member?.display_name || "A teammate";
}

/**
 * Who is in a team. Anyone can leave; the owner also invites connections, takes back
 * invites, removes members and closes the team (ADR 0016).
 */
export function TeamPeople({
  team,
  meId,
  invitable,
}: {
  team: Team;
  meId: string;
  /** The owner's connections who are not in the team and have no open invite. */
  invitable: Invitable[];
}) {
  const router = useRouter();
  const isOwner = team.owner_id === meId;
  const [members, setMembers] = useState(team.members);
  const [invites, setInvites] = useState<TeamInvite[]>(team.invites);
  const [choices, setChoices] = useState(invitable);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const full = members.length >= team.max_members;

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

  function invite(event: FormEvent) {
    event.preventDefault();
    if (!choice) return;
    void run(async () => {
      const sent = await browserApi(`/teams/${team.id}/invites`, teamInviteSchema, {
        method: "POST",
        body: { user_id: choice },
      });
      setInvites((current) => [...current, sent]);
      setChoices((current) => current.filter((person) => person.userId !== choice));
      setChoice("");
    });
  }

  function takeBack(invite: TeamInvite) {
    void run(async () => {
      await browserApi(`/teams/invites/${invite.id}`, noContentSchema, { method: "DELETE" });
      setInvites((current) => current.filter((item) => item.id !== invite.id));
    });
  }

  function remove(member: TeamMember) {
    void run(async () => {
      await browserApi(`/teams/${team.id}/members/${member.user_id}`, noContentSchema, {
        method: "DELETE",
      });
      setMembers((current) => current.filter((item) => item.user_id !== member.user_id));
    });
  }

  function leave() {
    void run(async () => {
      await browserApi(`/teams/${team.id}/members/${meId}`, noContentSchema, { method: "DELETE" });
      router.push("/teams");
    });
  }

  function close() {
    void run(async () => {
      await browserApi(`/teams/${team.id}`, noContentSchema, { method: "DELETE" });
      router.push("/teams");
    });
  }

  return (
    <Panel className="flex flex-col gap-4">
      <ul className="flex flex-col gap-2">
        {members.map((member) => {
          const name = member.user_id === meId ? "You" : memberName(member);
          return (
            <li key={member.user_id} className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-3">
                <Avatar userId={member.user_id} name={memberName(member)} size="sm" decorative />
                <span className="text-ink break-words">
                  {name}
                  {member.user_id === team.owner_id ? (
                    <span className="text-meta-lg text-muted"> · owner</span>
                  ) : null}
                </span>
              </div>
              {isOwner && member.user_id !== meId ? (
                <Button
                  variant="danger"
                  size="compact"
                  disabled={busy}
                  onClick={() => remove(member)}
                  aria-label={`Remove ${memberName(member)}`}
                >
                  Remove
                </Button>
              ) : null}
            </li>
          );
        })}
      </ul>

      {isOwner ? (
        <div className="flex flex-col gap-3">
          {invites.length ? (
            <div className="flex flex-col gap-2">
              <h3 className="text-title text-ink">Invited</h3>
              <ul className="flex flex-col gap-2">
                {invites.map((invite) => (
                  <li key={invite.id} className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-ink break-words">
                      {invite.display_name || "Someone you invited"}
                      <span className="text-meta-lg text-muted"> · waiting for an answer</span>
                    </span>
                    <Button
                      variant="ghost"
                      size="compact"
                      disabled={busy}
                      onClick={() => takeBack(invite)}
                      aria-label={`Take back the invite to ${invite.display_name || "this person"}`}
                    >
                      Take back
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {full ? (
            <p className="text-meta-lg text-muted">This team is full.</p>
          ) : choices.length ? (
            <form onSubmit={invite} className="flex flex-col gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-meta-lg text-ink font-medium">Invite a connection</span>
                <select
                  value={choice}
                  onChange={(event) => setChoice(event.target.value)}
                  className={SELECT}
                >
                  <option value="">Choose someone</option>
                  {choices.map((person) => (
                    <option key={person.userId} value={person.userId}>
                      {person.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                type="submit"
                variant="outline"
                className="self-start"
                disabled={busy || !choice}
              >
                Send invite
              </Button>
            </form>
          ) : (
            <p className="text-meta-lg text-muted">
              You can invite people you&apos;re connected with. Everyone you&apos;re connected with
              is already here or invited.
            </p>
          )}
        </div>
      ) : null}

      {error ? <InlineError announce>{error}</InlineError> : null}

      <div className="border-line flex flex-wrap gap-3 border-t pt-4">
        <Button variant="outline" size="compact" disabled={busy} onClick={leave}>
          Leave team
        </Button>
        {isOwner ? (
          <Button variant="danger" size="compact" disabled={busy} onClick={close}>
            Close team
          </Button>
        ) : null}
      </div>
    </Panel>
  );
}
