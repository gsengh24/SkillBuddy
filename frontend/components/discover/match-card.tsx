import { Panel, TopicChip, WhyPanel } from "@/components/ds/surfaces";
import { ReportButton } from "@/components/safety/report-button";
import { SendIntro } from "@/components/social/send-intro";
import type { Match } from "@/lib/api/schemas";

/** A plain dot in place of a face: names (and initials) are shown only after an accepted intro. */
function PersonDot() {
  return (
    <span
      aria-hidden="true"
      className="bg-green-tint border-green-line inline-flex size-[34px] shrink-0 rounded-full border"
    />
  );
}

/** One suggested person: what they offer and like, and why they were suggested. */
export function MatchCard({ match }: { match: Match }) {
  const { candidate } = match;
  const title = candidate.summary || "Someone who fits what you asked for";
  return (
    <Panel interactive className="flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <PersonDot />
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="text-mono-lg text-muted font-mono uppercase">Match {match.rank}</p>
          <h4 className="text-title lg:text-title-lg text-ink">{title}</h4>
          {candidate.availability ? (
            <p className="text-meta-lg text-muted">Available: {candidate.availability}</p>
          ) : null}
        </div>
      </div>
      {candidate.offers.length ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-mono-lg text-muted font-mono uppercase">Offers</p>
          <ul className="flex flex-wrap gap-2">
            {candidate.offers.map((item) => (
              <li key={item}>
                <TopicChip>{item}</TopicChip>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {candidate.interests.length ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-mono-lg text-muted font-mono uppercase">Into</p>
          <ul className="flex flex-wrap gap-2">
            {candidate.interests.map((item) => (
              <li key={item}>
                <TopicChip tone="soft">{item}</TopicChip>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <WhyPanel title="Why this match">{match.reason}</WhyPanel>
      <SendIntro match={match} />
      <ReportButton kind="profile" targetId={candidate.user_id} compact />
    </Panel>
  );
}
