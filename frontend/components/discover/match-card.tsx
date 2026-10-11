import { YouIcon } from "@/components/ds/icons";
import { WhyPanel } from "@/components/ds/surfaces";
import { ReportButton } from "@/components/safety/report-button";
import { SendIntro } from "@/components/social/send-intro";
import { InviteMatchToTeam } from "@/components/teams/find-teammate";
import type { Match } from "@/lib/api/schemas";
import { MAX_TAGS, presentMatch } from "@/lib/matching/present";

/** A plain dot in place of a face: names (and initials) are shown only after an accepted intro. */
function PersonDot() {
  return (
    <span
      aria-hidden="true"
      className="bg-panel text-muted border-muted-2 inline-flex size-[42px] shrink-0 items-center justify-center rounded-full border border-dashed"
    >
      <YouIcon className="size-[18px]" />
    </span>
  );
}

/**
 * One suggested person, in the platform's words: a short heading, why they were suggested,
 * one line about them, then what they can help with and what they're into. For a team's
 * request (`teamId`) the action is an invite to the team instead of an intro.
 */
export function MatchCard({ match, teamId }: { match: Match; teamId?: string | null }) {
  const { candidate } = match;
  const view = presentMatch(candidate);
  const tags = [...view.offers, ...view.interests];
  return (
    <article className="border-line bg-card hover:border-green-line flex flex-col gap-3 rounded-[14px] border p-[18px] transition-colors">
      <div className="flex items-start gap-3">
        <PersonDot />
        <div className="flex min-w-0 flex-col gap-0.5">
          <h3 className="text-title lg:text-title-lg text-ink">{view.title}</h3>
          {view.meta ? <p className="text-meta-lg text-muted">{view.meta}</p> : null}
        </div>
      </div>
      <WhyPanel title="Why this match" className="bg-green-soft! rounded-xl px-3.5 py-3">
        {match.reason}
      </WhyPanel>
      {view.summary ? <p className="text-ink-2">{view.summary}</p> : null}
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        {tags.length ? (
          <ul aria-label="Skills and interests" className="flex flex-wrap gap-1.5">
            {tags.slice(0, MAX_TAGS).map((tag) => (
              <li
                key={tag}
                className="border-line text-ink-2 rounded-full border px-[9px] py-1 text-[12.5px]"
              >
                {tag}
              </li>
            ))}
            {tags.length > MAX_TAGS ? (
              <li className="text-muted text-[12.5px] leading-[1.9]">
                +{tags.length - MAX_TAGS} more
              </li>
            ) : null}
          </ul>
        ) : null}
        <div className="ml-auto max-w-full [&:has(form)]:w-full">
          {teamId ? (
            <InviteMatchToTeam teamId={teamId} matchId={match.id} />
          ) : (
            <SendIntro match={match} />
          )}
        </div>
      </div>
      <ReportButton kind="profile" targetId={candidate.user_id} compact />
    </article>
  );
}
