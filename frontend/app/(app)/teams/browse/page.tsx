import type { Metadata } from "next";

import { ButtonLink } from "@/components/ds/button";
import { ReportButton } from "@/components/safety/report-button";
import { AskToJoin } from "@/components/teams/ask-to-join";
import { TeamsPaused } from "@/components/teams/teams-paused";
import { TextLink } from "@/components/ui/text-link";
import { teamPurposeSchema } from "@/lib/api/schemas";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getFeatures } from "@/lib/features";
import { PURPOSE_LABELS, teamSize } from "@/lib/teams/labels";
import { getListedTeams, getMyTeamRequests } from "@/lib/teams/server";

export const metadata: Metadata = { title: "Find a team" };
export const dynamic = "force-dynamic";

/** Teams their owners chose to list. Asking to join is a request the owner answers. */
export default async function BrowseTeamsPage({
  searchParams,
}: {
  searchParams: Promise<{ purpose?: string; cursor?: string }>;
}) {
  const query = await searchParams;
  const purpose = teamPurposeSchema.safeParse(query.purpose).data;
  const featuresCall = getFeatures();
  const teamsCall = startEarly(getListedTeams({ purpose, cursor: query.cursor }));
  const requestsCall = startEarly(getMyTeamRequests());
  await withUser("/login?next=/teams/browse", featuresCall);
  if (!(await featuresCall).features.teams) return <TeamsPaused />;
  const [teams, requests] = await Promise.all([teamsCall, requestsCall]);
  const asked = new Set(requests.items.map((request) => request.team.id));
  const filterHref = (value?: string) =>
    value ? `/teams/browse?purpose=${value}` : "/teams/browse";

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <TextLink
          href="/teams"
          tone="muted"
          className="text-meta-lg inline-flex min-h-11 items-center self-start"
        >
          Your teams
        </TextLink>
        <h1 className="text-headline lg:text-headline-lg">Find a team</h1>
        <p className="text-ink-2">
          Teams that are looking for people. Ask to join and the team&apos;s owner decides. You only
          see who is in a team once you are in it.
        </p>
      </header>

      <nav aria-label="Filter by purpose" className="flex flex-wrap gap-2">
        <ButtonLink
          href={filterHref()}
          variant={purpose ? "ghost" : "outline"}
          size="compact"
          aria-current={purpose ? undefined : "page"}
        >
          All
        </ButtonLink>
        {teamPurposeSchema.options.map((option) => (
          <ButtonLink
            key={option}
            href={filterHref(option)}
            variant={purpose === option ? "outline" : "ghost"}
            size="compact"
            aria-current={purpose === option ? "page" : undefined}
          >
            {PURPOSE_LABELS[option]}
          </ButtonLink>
        ))}
      </nav>

      {teams.items.length ? (
        <ul className="border-line border-t">
          {teams.items.map((team) => {
            const full = team.member_count >= team.max_members;
            return (
              <li key={team.id} className="border-line flex flex-col gap-2 border-b py-4">
                <h2 className="text-title break-words">{team.name}</h2>
                <p className="text-meta text-muted">
                  {PURPOSE_LABELS[team.purpose]} · {teamSize(team.member_count, team.max_members)}
                </p>
                {team.looking_for ? (
                  <p className="text-ink break-words">Looking for: {team.looking_for}</p>
                ) : null}
                {team.description ? (
                  <p className="text-ink-2 break-words">{team.description}</p>
                ) : null}
                <div className="flex flex-wrap items-center gap-3">
                  {full ? (
                    <p className="text-meta-lg text-muted">This team is full.</p>
                  ) : (
                    <AskToJoin teamId={team.id} teamName={team.name} asked={asked.has(team.id)} />
                  )}
                  <ReportButton kind="team" targetId={team.id} compact />
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-muted">No teams are looking for people right now.</p>
      )}

      {teams.next_cursor ? (
        <ButtonLink
          href={`/teams/browse?${new URLSearchParams({
            ...(purpose ? { purpose } : {}),
            cursor: teams.next_cursor,
          }).toString()}`}
          variant="outline"
          className="self-start"
        >
          Older teams
        </ButtonLink>
      ) : null}
    </div>
  );
}
