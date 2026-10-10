import type { Metadata } from "next";

import { ButtonLink } from "@/components/ds/button";
import { JoinByLink } from "@/components/teams/join-by-link";
import { TeamsPaused } from "@/components/teams/teams-paused";
import { ApiError } from "@/lib/api/errors";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getFeatures } from "@/lib/features";
import { PURPOSE_LABELS, teamSize } from "@/lib/teams/labels";
import { getTeamByLink } from "@/lib/teams/server";

export const metadata: Metadata = { title: "Join a team" };
export const dynamic = "force-dynamic";

/** Where an invite link lands: what the team is, and one button to join it. */
export default async function JoinTeamPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const featuresCall = getFeatures();
  const teamCall = startEarly(
    getTeamByLink(code).catch((error: unknown) => {
      // Unknown, expired, turned off or not for this person: the API says only "not found".
      if (error instanceof ApiError && [404, 422].includes(error.status)) return null;
      throw error;
    }),
  );
  await withUser(`/login?next=/teams/join/${encodeURIComponent(code)}`, featuresCall);
  if (!(await featuresCall).features.teams) return <TeamsPaused />;
  const team = await teamCall;

  if (!team) {
    return (
      <div className="flex max-w-2xl flex-col gap-4">
        <h1 className="text-headline lg:text-headline-lg">This invite link doesn&apos;t work</h1>
        <p className="text-ink-2">
          It may have run out or been turned off. Ask the person who sent it for a new one.
        </p>
        <ButtonLink href="/teams" variant="outline" className="self-start">
          Go to Teams
        </ButtonLink>
      </div>
    );
  }

  const full = team.member_count >= team.max_members;
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <p className="text-meta-lg text-muted">You&apos;ve been invited to join a team</p>
      <h1 className="text-headline lg:text-headline-lg break-words">{team.name}</h1>
      <p className="text-meta-lg text-muted">
        {PURPOSE_LABELS[team.purpose]} · {teamSize(team.member_count, team.max_members)}
      </p>
      {team.description ? <p className="text-ink-2 break-words">{team.description}</p> : null}
      <p className="text-ink-2">
        If you join, everyone in the team will see your name and can message you in the team chat.
        You can leave at any time.
      </p>
      {full ? (
        <p className="text-muted">This team is full right now.</p>
      ) : (
        <JoinByLink code={code} teamName={team.name} />
      )}
    </div>
  );
}
