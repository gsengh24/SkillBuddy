import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { ButtonLink } from "@/components/ds/button";
import { SearchIcon } from "@/components/ds/icons";
import { LogoMark } from "@/components/ds/logo";
import { cx } from "@/components/ui/cx";
import { CreateTeam } from "@/components/teams/create-team";
import { MyTeamRequests } from "@/components/teams/ask-to-join";
import { MyTeamInvites } from "@/components/teams/my-invites";
import { SpaceCard, type SpacePerson } from "@/components/teams/space-card";
import { TeamsPaused } from "@/components/teams/teams-paused";
import type { TeamSummary } from "@/lib/api/schemas";
import { startEarly, withUser } from "@/lib/auth/with-user";
import { getFeatures } from "@/lib/features";
import {
  getMyTeamRequests,
  getTeam,
  getTeamInvites,
  getTeamSpace,
  getTeams,
} from "@/lib/teams/server";

export const metadata: Metadata = { title: "Pair spaces" };
export const dynamic = "force-dynamic";

const MONO = "text-mono-lg font-mono uppercase";

/** Who is in a space and how many goals are done; null for a part that fails to load. */
async function spaceDetail(team: TeamSummary) {
  const [members, goals] = await Promise.all([
    getTeam(team.id).then(
      (detail) => detail.members.map((m): SpacePerson => ({ id: m.user_id, name: m.display_name })),
      () => null,
    ),
    getTeamSpace(team.id).then(
      (space) => ({
        done: space.goals.filter((goal) => goal.status === "done").length,
        total: space.goals.length,
      }),
      () => null,
    ),
  ]);
  return { members, goals };
}

function SectionHead({ id, title, aside }: { id: string; title: string; aside?: string }) {
  return (
    <div className="mb-3.5 flex items-baseline justify-between gap-4">
      <h2 id={id} className="font-display text-[20px] leading-[1.2] font-bold tracking-[-0.02em]">
        {title}
      </h2>
      {aside ? <span className={cx(MONO, "text-muted")}>{aside}</span> : null}
    </div>
  );
}

function Limit({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div className="grid justify-items-start gap-1 sm:justify-items-end">
      <span className={MONO}>{label}</span>
      <b className="font-display text-ink text-[30px] leading-none font-extrabold tracking-[-0.04em] tabular-nums">
        {value}
        <small className="text-muted-2 ml-0.5 text-[.5em]">/{max}</small>
      </b>
    </div>
  );
}

function Way({
  href,
  icon,
  title,
  text,
  go,
}: {
  href: string;
  icon: ReactNode;
  title: string;
  text: string;
  go: string;
}) {
  return (
    <Link
      href={href}
      prefetch={false}
      className="border-line bg-card hover:border-line-strong grid content-start gap-2.5 rounded-[16px] border p-[18px] transition-[transform,border-color] duration-200 ease-out motion-safe:hover:-translate-y-[3px]"
    >
      <span
        aria-hidden
        className="border-line-strong text-mint grid size-[38px] place-items-center rounded-[10px] border"
      >
        {icon}
      </span>
      <h3 className="font-display text-[16px] leading-tight font-bold tracking-[-0.01em]">
        {title}
      </h3>
      <p className="text-muted text-[13.5px]">{text}</p>
      <span className="text-ink inline-flex gap-1.5 text-[13.5px] font-semibold">
        {go} <span aria-hidden>→</span>
      </span>
    </Link>
  );
}

function LinkIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      className="size-[18px]"
    >
      <path d="M8.5 11.5a3.5 3.5 0 0 0 5 0l2.5-2.5a3.5 3.5 0 0 0-5-5l-1 1" />
      <path d="M11.5 8.5a3.5 3.5 0 0 0-5 0L4 11a3.5 3.5 0 0 0 5 5l1-1" />
    </svg>
  );
}

/** The person's pair spaces, then a form to make one and the other ways in. */
export default async function TeamsPage() {
  const featuresCall = getFeatures();
  const invitesCall = startEarly(getTeamInvites());
  const teamsCall = startEarly(getTeams());
  const requestsCall = startEarly(getMyTeamRequests());
  const { user } = await withUser("/login?next=/teams", featuresCall);
  if (!(await featuresCall).features.teams) return <TeamsPaused />;
  const [teams, invites, requests] = await Promise.all([teamsCall, invitesCall, requestsCall]);
  const details = await Promise.all(teams.items.map(spaceDetail));

  const owned = teams.items.filter((team) => team.owner_id === user.id).length;
  const maxMembers = teams.items[0]?.max_members ?? 6;
  const me: SpacePerson = { id: user.id, name: user.email };
  const canMake = owned < teams.max_owned && teams.items.length < teams.max_teams;

  return (
    <div className="flex flex-col pb-8">
      <header className="border-line grid items-end gap-6 border-b pb-7 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div>
          <p className={cx(MONO, "text-mint-text mb-2.5")}>Spaces</p>
          <h1 className="font-display text-[clamp(40px,6vw,64px)] leading-[.95] font-extrabold tracking-[-0.04em]">
            Pair spaces
          </h1>
          <p className="text-ink-2 mt-3.5 max-w-[60ch]">
            A group of up to six for a hackathon, a project or anything else: a chat, shared goals,
            skills you want to grow, and progress notes. Only the people in a pair space can see it.
          </p>
        </div>
        <div className="text-muted flex gap-[22px]" role="group" aria-label="Your limits">
          <Limit label="Joined" value={teams.items.length} max={teams.max_teams} />
          <Limit label="You own" value={owned} max={teams.max_owned} />
        </div>
      </header>

      {invites.items.length || requests.items.length ? (
        <div className="mt-8 flex flex-col gap-4">
          <MyTeamInvites initial={invites.items} />
          <MyTeamRequests initial={requests.items} />
        </div>
      ) : null}

      <section aria-labelledby="my-teams-h" className="pt-[34px]">
        <SectionHead
          id="my-teams-h"
          title="Your pair spaces"
          aside={teams.items.length ? `${teams.items.length} of ${teams.max_teams}` : undefined}
        />
        {teams.items.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {teams.items.map((team, index) => {
              const { members, goals } = details[index] ?? { members: null, goals: null };
              return (
                <SpaceCard
                  key={team.id}
                  href={`/teams/${team.id}`}
                  purpose={team.purpose}
                  name={team.name}
                  description={team.description}
                  isOwner={team.owner_id === user.id}
                  people={members ?? []}
                  memberCount={team.member_count}
                  maxMembers={team.max_members}
                  goals={goals}
                  unread={team.unread}
                />
              );
            })}
            {canMake ? (
              <a
                href="#make-h"
                className="border-line-strong text-muted hover:border-muted grid min-h-[200px] place-content-center justify-items-center gap-2.5 rounded-[16px] border border-dashed p-[18px] text-center"
              >
                <span
                  aria-hidden
                  className="border-muted-2 text-mint grid size-10 place-items-center rounded-full border-[1.5px] border-dashed text-[20px]"
                >
                  +
                </span>
                <b className="font-display text-ink text-[16px] leading-tight font-bold">
                  Make another
                </b>
                <span>You can own up to {teams.max_owned}.</span>
              </a>
            ) : null}
          </div>
        ) : (
          <div className="border-line bg-card grid items-center gap-[22px] rounded-[16px] border p-[18px] sm:grid-cols-[200px_minmax(0,1fr)]">
            {/* eslint-disable-next-line @next/next/no-img-element -- a fixed local picture */}
            <img
              src="/art/home/home_pair_space.jpg"
              alt=""
              width={200}
              height={200}
              className="aspect-[16/10] w-full rounded-[12px] object-cover sm:aspect-square"
            />
            <div>
              <h3 className="font-display mb-1.5 text-[24px] leading-[1.1] font-extrabold tracking-[-0.03em]">
                You&apos;re not in a pair space yet.
              </h3>
              <p className="text-ink-2 mb-4 max-w-[46ch]">
                Make one for your next hackathon or project, or find one that&apos;s looking for
                people.
              </p>
              <div className="flex flex-wrap gap-2.5">
                <ButtonLink href="#make-h" variant="primary" className="max-sm:flex-1">
                  Make a pair space
                </ButtonLink>
                <ButtonLink
                  href="/teams/browse"
                  variant="outline"
                  className="border-line-strong! text-ink! max-sm:flex-1"
                >
                  Find one to join
                </ButtonLink>
              </div>
            </div>
          </div>
        )}
      </section>

      <section aria-labelledby="make-h" className="pt-[34px]">
        <SectionHead id="make-h" title="Make a pair space" aside="You'll be the owner" />
        {canMake ? (
          <CreateTeam me={me} maxMembers={maxMembers} />
        ) : (
          <p className="text-muted">
            {owned >= teams.max_owned
              ? `You own ${teams.max_owned} pair spaces, the most allowed. Hand one over or close one first.`
              : `You're in ${teams.max_teams} pair spaces, the most allowed. Leave one first.`}
          </p>
        )}
      </section>

      <section aria-labelledby="ways-h" className="pt-[34px]">
        <SectionHead id="ways-h" title="Other ways in" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Way
            href="/teams/browse"
            icon={<SearchIcon className="size-[18px]" />}
            title="Find a pair space to join"
            text="Browse spaces that are looking for people and ask to join with a short note."
            go="Browse"
          />
          <Way
            href="/teams/browse"
            icon={<LinkIcon />}
            title="Have an invite link?"
            text="Open it to see the space and say yes. Links last 7 days."
            go="How links work"
          />
          <Way
            href="/home#new-request"
            icon={<LogoMark className="size-[18px]" />}
            title="Let the matcher find teammates"
            text="Post a request for your space from Home and invite the people it suggests."
            go="Go to Home"
          />
        </div>
        <p className="text-muted mt-[18px] text-[13px]">
          Everyone joins by saying yes. Anyone can leave, block or report at any time.
        </p>
      </section>
    </div>
  );
}
