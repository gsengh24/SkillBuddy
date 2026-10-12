import Link from "next/link";

import { Avatar } from "@/components/ds/avatar";
import { cx } from "@/components/ui/cx";
import type { TeamPurpose } from "@/lib/api/schemas";
import { NO_DESCRIPTION, SHORT_PURPOSE_LABELS } from "@/lib/teams/labels";

export type SpacePerson = { id: string; name: string };

const MONO = "text-mono-lg font-mono uppercase";

/** The purpose tag: a pill with a mint dot. */
export function PurposeTag({ purpose }: { purpose: TeamPurpose }) {
  return (
    <span className="border-line-strong text-ink-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px]">
      <span aria-hidden className="bg-mint size-1.5 rounded-full" />
      {SHORT_PURPOSE_LABELS[purpose]}
    </span>
  );
}

/** Overlapping initials, then a dashed "+" while there is room. */
export function PeopleStack({
  people,
  memberCount,
  maxMembers,
}: {
  people: SpacePerson[];
  memberCount: number;
  maxMembers: number;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span aria-hidden className="flex">
        {people.map((person) => (
          <Avatar
            key={person.id}
            userId={person.id}
            name={person.name}
            decorative
            className="border-card -ml-2 size-[30px]! border-2 text-[11.5px]! first:ml-0"
          />
        ))}
        {memberCount < maxMembers ? (
          <span className="border-muted-2 text-muted -ml-2 inline-flex size-[30px] items-center justify-center rounded-full border-[1.5px] border-dashed text-[12px] first:ml-0">
            +
          </span>
        ) : null}
      </span>
      <span className={cx(MONO, "text-muted")}>
        {memberCount} of {maxMembers}
      </span>
    </div>
  );
}

/**
 * One pair space as a card: purpose, owner mark, name and line, who is in it, goals done
 * and a way in. `goals` is null when they could not be loaded; the row is then left out.
 * With no `href` it is a preview (the make form), with no goals row and no link.
 */
export function SpaceCard({
  href,
  purpose,
  name,
  description,
  isOwner,
  people,
  memberCount,
  maxMembers,
  goals,
  unread = 0,
}: {
  href?: string;
  purpose: TeamPurpose;
  name: string;
  description: string;
  isOwner: boolean;
  people: SpacePerson[];
  memberCount: number;
  maxMembers: number;
  goals?: { done: number; total: number } | null;
  unread?: number;
}) {
  const body = (
    <>
      <div className="flex items-center justify-between gap-2.5">
        <PurposeTag purpose={purpose} />
        <span className="flex items-center gap-2">
          {unread ? <span className={cx(MONO, "text-ink")}>{unread} new</span> : null}
          {isOwner ? <span className={cx(MONO, "text-mint-text")}>Owner</span> : null}
        </span>
      </div>
      <div className="flex flex-col gap-1.5">
        <h3 className="font-display text-[22px] leading-[1.1] font-extrabold tracking-[-0.03em] break-words">
          {name.trim() || <span className="text-muted-2">Your space</span>}
        </h3>
        <p className="text-muted text-[13.5px] break-words">
          {description.trim() || NO_DESCRIPTION}
        </p>
      </div>
      <PeopleStack people={people} memberCount={memberCount} maxMembers={maxMembers} />
      {goals !== undefined && goals !== null ? (
        <div className="flex flex-col gap-1.5">
          <span className={cx(MONO, "text-muted flex justify-between")}>
            <span>Goals</span>
            <span>{goals.total ? `${goals.done} of ${goals.total} done` : "No goals yet"}</span>
          </span>
          <span aria-hidden className="bg-line block h-1 overflow-hidden rounded">
            <span
              className="bg-mint block h-full w-full origin-left"
              style={{ transform: `scaleX(${goals.total ? goals.done / goals.total : 0})` }}
            />
          </span>
        </div>
      ) : null}
      {href ? (
        <span className="text-ink inline-flex items-center gap-1.5 text-[14px] font-semibold">
          Open <span aria-hidden>→</span>
        </span>
      ) : null}
    </>
  );
  const frame =
    "border-line bg-card grid content-start gap-3.5 rounded-[16px] border p-[18px] text-left";
  if (!href) return <div className={frame}>{body}</div>;
  return (
    <Link
      href={href}
      prefetch={false}
      aria-label={`${name}, open pair space`}
      className={cx(
        frame,
        "hover:border-line-strong transition-[transform,border-color] duration-200 ease-out motion-safe:hover:-translate-y-[3px]",
      )}
    >
      {body}
    </Link>
  );
}
