import type { Metadata } from "next";
import Link from "next/link";

import { AdminHeading } from "@/components/admin/admin-shell";
import { Attention, Funnel, HealthList, Kpis, SignupChart } from "@/components/admin/overview";
import { cx } from "@/components/ui/cx";
import { getHealth, getOverview } from "@/lib/admin/server";

export const metadata: Metadata = { title: "Overview" };
export const dynamic = "force-dynamic";

const RANGES = [7, 30, 90] as const;
const CARD = "border-line bg-bg rounded-panel border p-4";
const TITLE = "font-display tracking-display text-[17px] font-extrabold";

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** Overview (reference-admin.html): what needs you today. */
export default async function AdminOverviewPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const { days: asked } = await searchParams;
  const days = RANGES.find((range) => String(range) === asked) ?? 7;
  const [overview, health] = await Promise.all([getOverview(days), getHealth()]);
  const today = new Date().toLocaleDateString(undefined, { dateStyle: "full" });

  return (
    <>
      <p className="text-mono text-green mb-1 font-mono uppercase" suppressHydrationWarning>
        {today}
      </p>
      <AdminHeading
        lead="Overview."
        rest="What needs you today."
        actions={
          <nav
            aria-label="Range"
            className="bg-panel border-line inline-flex gap-1 rounded-[10px] border p-[3px]"
          >
            {RANGES.map((range) => (
              <Link
                key={range}
                href={`/admin?days=${range}`}
                aria-current={range === days ? "page" : undefined}
                className={cx(
                  "text-meta inline-flex min-h-11 items-center rounded-lg border px-3 pointer-fine:min-h-8",
                  range === days
                    ? "border-line bg-bg text-ink font-medium"
                    : "text-muted hover:text-ink border-transparent",
                )}
              >
                {range} days
              </Link>
            ))}
          </nav>
        }
      />
      <div className="flex flex-col gap-3">
        <Kpis overview={overview} />
        <div className="grid gap-3 lg:grid-cols-[2fr_1fr]">
          <section aria-labelledby="signups-h" className={CARD}>
            <h2 id="signups-h" className={TITLE}>
              New sign-ups
            </h2>
            <p className="text-meta text-muted mb-3">Per day, last {days} days</p>
            <SignupChart overview={overview} />
          </section>
          <section aria-labelledby="attention-h" className={CARD}>
            <h2 id="attention-h" className={TITLE}>
              Needs attention
            </h2>
            <p className="text-meta text-muted mb-2">Open items across the portal</p>
            <Attention overview={overview} />
          </section>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          <section aria-labelledby="funnel-h" className={CARD}>
            <h2 id="funnel-h" className={TITLE}>
              From request to chat
            </h2>
            <p className="text-meta text-muted mb-3">How far people get, last {days} days</p>
            <Funnel overview={overview} />
          </section>
          <section aria-labelledby="health-h" className={CARD}>
            <h2 id="health-h" className={TITLE}>
              System health
            </h2>
            <p className="text-meta text-muted mb-2">Checked at most once a minute</p>
            <HealthList health={health} />
          </section>
        </div>
        <section aria-labelledby="activity-h" className={CARD}>
          <h2 id="activity-h" className={TITLE}>
            Recent admin activity
          </h2>
          <p className="text-meta text-muted mb-2">The latest entries from the audit log</p>
          {overview.activity.length ? (
            <ul className="divide-line flex flex-col divide-y">
              {overview.activity.map((entry) => (
                <li key={entry.id} className="flex flex-wrap justify-between gap-x-3 py-2.5">
                  <span className="font-mono text-[13px]">{entry.action}</span>
                  <span className="text-mono text-muted font-mono" suppressHydrationWarning>
                    {entry.actor_role ?? "system"} · {when(entry.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-meta text-muted">Nothing yet.</p>
          )}
        </section>
      </div>
    </>
  );
}
