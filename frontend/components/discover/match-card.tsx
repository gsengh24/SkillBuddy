import { YouIcon } from "@/components/ds/icons";
import { TopicChip, WhyPanel } from "@/components/ds/surfaces";
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

/** A labelled row of tags, cut off at MAX_TAGS with a count of the rest. */
function Tags({ label, items, tone }: { label: string; items: string[]; tone?: "soft" }) {
  if (!items.length) return null;
  const more = items.length - MAX_TAGS;
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-mono-lg text-muted font-mono uppercase">{label}</p>
      <ul className="flex flex-wrap items-center gap-2">
        {items.slice(0, MAX_TAGS).map((item) => (
          <li key={item}>
            <TopicChip tone={tone}>{item}</TopicChip>
          </li>
        ))}
        {more > 0 ? <li className="text-meta-lg text-muted">+{more} more</li> : null}
      </ul>
    </div>
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
  return (
    <article className="border-line bg-bg hover:border-green-line flex flex-col gap-3 rounded-[14px] border p-[18px] transition-colors">
      <div className="flex items-start gap-3">
        <PersonDot />
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="text-mono-lg text-muted font-mono uppercase">Match {match.rank}</p>
          <h3 className="text-title lg:text-title-lg text-ink">{view.title}</h3>
          {view.meta ? <p className="text-meta-lg text-muted">{view.meta}</p> : null}
        </div>
      </div>
      <WhyPanel title="Why this match" className="bg-green-soft rounded-xl px-3.5 py-3">
        {match.reason}
      </WhyPanel>
      {view.summary ? <p className="text-ink-2">{view.summary}</p> : null}
      <Tags label="Can help with" items={view.offers} />
      <Tags label="Interested in" items={view.interests} tone="soft" />
      {teamId ? (
        <InviteMatchToTeam teamId={teamId} matchId={match.id} />
      ) : (
        <SendIntro match={match} />
      )}
      <ReportButton kind="profile" targetId={candidate.user_id} compact />
    </article>
  );
}
