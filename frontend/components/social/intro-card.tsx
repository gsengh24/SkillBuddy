"use client";

import { useId, useState } from "react";

import { BlockButton } from "@/components/safety/block-button";
import { ReportButton } from "@/components/safety/report-button";
import { Button } from "@/components/ds/button";
import { InlineError } from "@/components/ds/fields";
import { TopicChip, WhyPanel } from "@/components/ds/surfaces";
import { TextLink } from "@/components/ui/text-link";
import { browserApi } from "@/lib/api/browser";
import { introSchema, type Intro } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

/**
 * An intro someone sent you: what they asked for, why you were matched, their note and
 * what they offer. You accept or decline; only an accept shares names and links.
 */
export function IntroCard({ initial }: { initial: Intro }) {
  const ids = useId();
  const [intro, setIntro] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
    <article aria-labelledby={`${ids}-h`} className="flex flex-col">
      <p className="text-green font-mono text-[11px] leading-[1.4] font-medium tracking-[0.08em] uppercase">
        Intro
      </p>
      <h2
        id={`${ids}-h`}
        className="font-display mt-1.5 mb-[22px] text-[26px] leading-[1.05] font-extrabold tracking-[-0.03em] text-balance lg:text-[30px]"
      >
        {intro.status === "accepted" && person.display_name
          ? `${person.display_name} wants to meet you.`
          : "Someone wants to meet you."}
      </h2>
      <div className="border-line flex flex-col gap-3.5 rounded-[14px] border p-5">
        <div className="flex flex-col gap-1">
          <span className="text-muted font-mono text-[11px] leading-[1.4] font-medium tracking-[0.08em] uppercase">
            What they asked for
          </span>
          <p>“{intro.request_text}”</p>
        </div>
        {person.summary ? <p className="text-ink-2">{person.summary}</p> : null}
        {person.offers.length ? (
          <ul className="flex flex-wrap gap-2" aria-label="They offer">
            {person.offers.map((item) => (
              <li key={item}>
                <TopicChip>{item}</TopicChip>
              </li>
            ))}
          </ul>
        ) : null}
        <WhyPanel title="Why you were matched" className="bg-green-soft rounded-xl px-3.5 py-3">
          {intro.reason}
        </WhyPanel>
        {intro.note ? (
          <blockquote className="border-green bg-panel text-ink m-0 rounded-r-[10px] border-l-2 px-3.5 py-3 text-[15px]">
            {intro.note}
          </blockquote>
        ) : null}

        {intro.status === "pending" ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2.5">
              <Button type="button" variant="primary" disabled={busy} onClick={() => answer(true)}>
                Accept
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={busy}
                onClick={() => answer(false)}
                className="border-line-strong"
              >
                Decline
              </Button>
            </div>
            <p className="text-muted text-[13px]">
              If you accept, you&apos;ll both see each other&apos;s name and links. If you decline,
              they won&apos;t be told.
            </p>
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
            <p className="text-ink font-medium">You&apos;re connected.</p>
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
        {error ? <InlineError announce>{error}</InlineError> : null}
      </div>
    </article>
  );
}
