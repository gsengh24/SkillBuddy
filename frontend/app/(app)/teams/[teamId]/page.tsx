import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SpaceView } from "@/components/spaces/space-view";
import { TeamChat } from "@/components/teams/team-chat";
import { memberName, TeamPeople } from "@/components/teams/team-people";
import { TeamsPaused } from "@/components/teams/teams-paused";
import { TextLink } from "@/components/ui/text-link";
import { ApiError } from "@/lib/api/errors";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getFeatures } from "@/lib/features";
import { getConnections } from "@/lib/social/server";
import { PURPOSE_LABELS, teamSize } from "@/lib/teams/labels";
import { getTeam, getTeamChat, getTeamSpace, getTeams } from "@/lib/teams/server";

export const metadata: Metadata = { title: "Team" };
export const dynamic = "force-dynamic";

/** Section headings in the display face, as in a pair space. */
const SECTION_HEADING = "font-display tracking-display text-[20px] leading-tight font-extrabold";

/** One team: its chat, its people, and its goals, skills and notes. Members only. */
export default async function TeamPage({ params }: { params: Promise<{ teamId: string }> }) {
  const { teamId } = await params;
  const featuresCall = getFeatures();
  const teamCall = startEarly(getTeam(teamId));
  const spaceCall = startEarly(getTeamSpace(teamId));
  const chatCall = startEarly(getTeamChat(teamId));
  const teamsCall = startEarly(getTeams());
  const { user, data: connections } = await withUser(
    `/login?next=/teams/${encodeURIComponent(teamId)}`,
    getConnections(),
  );
  const { features, message_max_length } = await featuresCall;
  if (!features.teams) return <TeamsPaused />;
  const team = await teamCall.catch((error: unknown) => {
    // Not a member, closed, or no such team: the API says "not found" for all three.
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  });
  const [space, teams] = await Promise.all([spaceCall, teamsCall]);
  const chat = features.chats ? await chatCall : null;

  const names = Object.fromEntries(
    team.members.map((member) => [member.user_id, memberName(member)]),
  );
  const taken = new Set([
    ...team.members.map((member) => member.user_id),
    ...team.invites.map((invite) => invite.user_id),
  ]);
  const invitable = connections.items
    .filter(({ person }) => !taken.has(person.user_id))
    .map(({ person }) => ({
      userId: person.user_id,
      name: person.display_name ?? "Your connection",
    }));
  const unread = teams.items.find((item) => item.id === team.id)?.unread ?? 0;

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <TextLink
          href="/teams"
          tone="muted"
          className="text-meta-lg inline-flex min-h-11 items-center self-start"
        >
          All teams
        </TextLink>
        <h1 className="text-headline lg:text-headline-lg break-words">{team.name}</h1>
        <p className="text-meta-lg text-muted">
          {PURPOSE_LABELS[team.purpose]} · {teamSize(team.member_count, team.max_members)}
        </p>
        {team.description ? <p className="text-ink-2 break-words">{team.description}</p> : null}
      </header>

      <section aria-labelledby="team-chat-h" className="flex flex-col gap-3">
        <h2 id="team-chat-h" className={SECTION_HEADING}>
          Team chat
        </h2>
        {chat ? (
          <TeamChat
            teamId={team.id}
            teamName={team.name}
            meId={user.id}
            names={names}
            initial={chat.page.items}
            cursor={chat.cursor}
            retentionDays={chat.page.retention_days}
            hasUnread={unread > 0}
            maxLength={message_max_length}
          />
        ) : (
          <p className="text-muted">
            Chats are switched off for everyone for a while. Your messages are kept.
          </p>
        )}
      </section>

      <section aria-labelledby="team-people-h" className="flex flex-col gap-3">
        <h2 id="team-people-h" className={SECTION_HEADING}>
          People
        </h2>
        <TeamPeople team={team} meId={user.id} invitable={invitable} />
      </section>

      <SpaceView
        space={space}
        meId={user.id}
        otherId=""
        otherName="A teammate"
        team={{ base: `/teams/${team.id}/space`, names }}
      />
    </div>
  );
}
