import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { WhyBox } from "@/components/ui/why-box";
import type { Match } from "@/lib/api/schemas";
import { hueStyle, personHue } from "@/lib/design/color";

/** The person's colour, with no initials: names are shown only after an accepted intro. */
function PersonDot({ userId }: { userId: string }) {
  return (
    <span
      aria-hidden="true"
      style={hueStyle(personHue(userId))}
      className="inline-flex size-10 shrink-0 rounded-full border-2 border-(--hue-edge) bg-(--hue-tint)"
    />
  );
}

/** One suggested person: what they offer and like, and why they were suggested. */
export function MatchCard({ match }: { match: Match }) {
  const { candidate } = match;
  const hue = personHue(candidate.user_id);
  const title = candidate.summary || "Someone who fits what you asked for";
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <PersonDot userId={candidate.user_id} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="text-small text-muted font-semibold">Match {match.rank}</p>
          <h4 className="text-body text-ink font-bold">{title}</h4>
          {candidate.availability ? (
            <p className="text-small text-muted">Available: {candidate.availability}</p>
          ) : null}
        </div>
      </div>
      {candidate.offers.length ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-small text-muted font-semibold">Offers</p>
          <ul className="flex flex-wrap gap-2">
            {candidate.offers.map((item) => (
              <li key={item}>
                <Tag hue={hue}>{item}</Tag>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {candidate.interests.length ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-small text-muted font-semibold">Into</p>
          <ul className="flex flex-wrap gap-2">
            {candidate.interests.map((item) => (
              <li key={item}>
                <Tag>{item}</Tag>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <WhyBox hue={hue} title="Why this match">
        {match.reason}
      </WhyBox>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" disabled hue={hue}>
          Send intro
        </Button>
        <span className="text-small text-muted">Intros open soon.</span>
      </div>
    </Card>
  );
}
