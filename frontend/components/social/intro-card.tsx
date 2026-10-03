"use client";

import { useId, useState } from "react";

import { BlockButton } from "@/components/safety/block-button";
import { ReportButton } from "@/components/safety/report-button";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { TextLink } from "@/components/ui/text-link";
import { WhyBox } from "@/components/ui/why-box";
import { browserApi } from "@/lib/api/browser";
import { introSchema, type Intro } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { personHue } from "@/lib/design/color";

/**
 * An intro someone sent you: what they asked for, why you were matched, their note and
 * what they offer. You accept or decline; only an accept shares names and links.
 */
export function IntroCard({ initial }: { initial: Intro }) {
  const ids = useId();
  const [intro, setIntro] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hue = personHue(intro.person.user_id);
  const { person } = intro;

  async function answer(accept: boolean) {
    setBusy(true);
    setError(null);
    try {
      setIntro(
        await browserApi(`/intros/${intro.id}/respond`, introSchema, {
          method: "POST",
          body: { accept },
        }),
      );
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-4" role="article" aria-labelledby={`${ids}-h`}>
      <div className="flex flex-col gap-1">
        <h3 id={`${ids}-h`} className="text-body text-ink font-bold">
          {intro.status === "accepted" && person.display_name
            ? `${person.display_name} wants to meet you`
            : "Someone wants to meet you"}
        </h3>
        <p className="text-small text-muted">They&apos;re looking for: “{intro.request_text}”</p>
      </div>
      {person.summary ? <p>{person.summary}</p> : null}
      {person.offers.length ? (
        <ul className="flex flex-wrap gap-2" aria-label="They offer">
          {person.offers.map((item) => (
            <li key={item}>
              <Tag hue={hue}>{item}</Tag>
            </li>
          ))}
        </ul>
      ) : null}
      <WhyBox hue={hue} title="Why you were matched">
        {intro.reason}
      </WhyBox>
      {intro.note ? (
        <blockquote className="border-line text-ink border-l-2 pl-3">{intro.note}</blockquote>
      ) : null}

      {intro.status === "pending" ? (
        <div className="flex flex-col gap-3">
          <p className="text-small text-muted">
            If you accept, you&apos;ll both see each other&apos;s name and links. If you decline,
            they won&apos;t be told.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button type="button" hue={hue} disabled={busy} onClick={() => answer(true)}>
              Accept
            </Button>
            <Button type="button" disabled={busy} onClick={() => answer(false)}>
              Decline
            </Button>
          </div>
          {intro.direction === "received" ? (
            <div className="flex flex-wrap items-start gap-3">
              <ReportButton kind="intro" targetId={intro.id} blockUserId={person.user_id} />
              <BlockButton userId={person.user_id} name="this person" />
            </div>
          ) : null}
        </div>
      ) : null}
      {intro.status === "accepted" ? (
        <div className="flex flex-col gap-1" role="status">
          <p className="text-ink font-semibold">You&apos;re connected.</p>
          {person.links?.length ? (
            <ul className="flex flex-col gap-1">
              {person.links.map((link) => (
                <li key={link}>
                  <TextLink href={link}>{link}</TextLink>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {intro.status === "declined" ? (
        <p role="status" className="text-muted">
          Declined. They won&apos;t be told.
        </p>
      ) : null}
      {intro.status === "expired" ? <p className="text-muted">This intro has expired.</p> : null}
      {error ? (
        <p role="alert" className="text-small text-coral-ink font-semibold">
          {error}
        </p>
      ) : null}
    </Card>
  );
}
