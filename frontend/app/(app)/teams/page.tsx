import type { Metadata } from "next";

import { ButtonLink } from "@/components/ds/button";
import { Panel } from "@/components/ds/surfaces";
import { CreateTeam } from "@/components/teams/create-team";
import { MyTeamRequests } from "@/components/teams/ask-to-join";
import { MyTeamInvites } from "@/components/teams/my-invites";
import { TeamsPaused } from "@/components/teams/teams-paused";
import { TextLink } from "@/components/ui/text-link";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getFeatures } from "@/lib/features";
import { PURPOSE_LABELS, teamSize } from "@/lib/teams/labels";
import { getMyTeamRequests, getTeamInvites, getTeams } from "@/lib/teams/server";

export const metadata: Metadata = { title: "Teams" };
export const dynamic = "force-dynamic";

/** The person's teams, invites waiting for an answer, and a form to make a team. */
export default async function TeamsPage() {
  const featuresCall = getFeatures();
  const invitesCall = startEarly(getTeamInvites());
  const teamsCall = startEarly(getTeams());
  const requestsCall = startEarly(getMyTeamRequests());
  await withUser("/login?next=/teams", featuresCall);
  if (!(await featuresCall).features.teams) return <TeamsPaused />;
  const [teams, invites, requests] = await Promise.all([teamsCall, invitesCall, requestsCall]);
  const atLimit = teams.items.length >= teams.max_teams;

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <TextLink
          href="/spaces"
          tone="muted"
          className="text-meta-lg inline-flex min-h-11 items-center self-start"
        >
          Spaces
        </TextLink>
        <h1 className="text-headline lg:text-headline-lg">Teams</h1>
        <p className="text-ink-2">
          A group of up to six for a hackathon, a project or anything else: a team chat, shared
          goals, skills you want to grow, and progress notes. Only the people in a team can see it.
        </p>
      </header>

      <MyTeamInvites initial={invites.items} />
      <MyTeamRequests initial={requests.items} />

      <section aria-labelledby="my-teams-h" className="flex flex-col gap-3">
        <h2 id="my-teams-h" className="text-title">
          Your teams
        </h2>
        {teams.items.length ? (
          <ul className="border-line border-t">
            {teams.items.map((team) => (
              <li
                key={team.id}
                className="border-line flex flex-wrap items-center justify-between gap-3 border-b py-3"
              >
                <div className="min-w-0 flex-1">
                  <h3 className="text-ink font-semibold break-words">{team.name}</h3>
                  <p className="text-meta text-muted">
                    {PURPOSE_LABELS[team.purpose]} · {teamSize(team.member_count, team.max_members)}
                    {team.unread ? ` · ${team.unread} new` : null}
                  </p>
                </div>
                <ButtonLink href={`/teams/${team.id}`} variant="outline" size="compact">
                  Open team
                </ButtonLink>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted">You&apos;re not in a team yet. Make one below.</p>
        )}
        <ButtonLink href="/teams/browse" variant="outline" className="self-start">
          Find a team to join
        </ButtonLink>
      </section>

      <section aria-labelledby="new-team-h" className="flex flex-col gap-3">
        <h2 id="new-team-h" className="text-title">
          Make a team
        </h2>
        {atLimit ? (
          <p className="text-muted">
            You&apos;re in {teams.max_teams} teams, the most allowed. Leave one to make another.
          </p>
        ) : (
          <Panel>
            <CreateTeam />
          </Panel>
        )}
      </section>
    </div>
  );
}
