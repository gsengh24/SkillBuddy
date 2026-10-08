import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AdminHeading } from "@/components/admin/admin-shell";
import { AppealActions, CaseDrawer } from "@/components/admin/safety";
import { cx } from "@/components/ui/cx";
import { getAdminMe, getAppeals, getBlockStats, getCase, getQueue } from "@/lib/admin/server";

export const metadata: Metadata = { title: "Reports and safety" };
export const dynamic = "force-dynamic";

type Search = { tab?: string; status?: string; report?: string };

const STATUSES = [
  { value: "open", label: "Open" },
  { value: "in_review", label: "In review" },
  { value: "resolved", label: "Resolved" },
];

function when(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

function Tabs({ tab, canAppeals }: { tab: string; canAppeals: boolean }) {
  const tabs = [
    { value: "queue", label: "Reports" },
    ...(canAppeals ? [{ value: "appeals", label: "Appeals" }] : []),
    { value: "blocks", label: "Blocks" },
  ];
  return (
    <nav
      aria-label="Safety"
      className="bg-panel border-line mb-3 inline-flex gap-1 rounded-[10px] border p-[3px]"
    >
      {tabs.map((item) => (
        <Link
          key={item.value}
          href={`/admin/reports?tab=${item.value}`}
          aria-current={item.value === tab ? "page" : undefined}
          className={cx(
            "text-meta inline-flex min-h-11 items-center rounded-lg border px-3 pointer-fine:min-h-9",
            item.value === tab
              ? "border-line bg-bg text-ink font-medium"
              : "text-muted hover:text-ink border-transparent",
          )}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}

/** Reports and safety (reference-admin.html): the queue, appeals and block counts. */
export default async function ReportsPage({ searchParams }: { searchParams: Promise<Search> }) {
  const search = await searchParams;
  const me = await getAdminMe();
  const canAppeals = me.permissions.includes("handle_reports");
  const tab =
    search.tab === "appeals" && canAppeals
      ? "appeals"
      : search.tab === "blocks"
        ? "blocks"
        : "queue";
  const status = STATUSES.some((s) => s.value === search.status) ? search.status! : "open";
  const canRead = me.permissions.includes("read_reported_messages");
  const [queue, found, appeals, blocks] = await Promise.all([
    tab === "queue" ? getQueue(status) : Promise.resolve(null),
    tab === "queue" && search.report && canRead
      ? getCase(search.report).catch(() => null)
      : Promise.resolve(null),
    tab === "appeals" ? getAppeals() : Promise.resolve(null),
    tab === "blocks" ? getBlockStats() : Promise.resolve(null),
  ]);
  if (!me.permissions.includes("view_users")) notFound();
  const listHref = `/admin/reports?tab=queue&status=${status}`;

  return (
    <>
      <AdminHeading
        lead="Reports and safety."
        rest="Review, decide, record."
        description="Review the report, the messages the reporter attached, and both users' history. Then decide."
      />
      <Tabs tab={tab} canAppeals={canAppeals} />

      {queue ? (
        <>
          <nav aria-label="Report status" className="mb-3 flex flex-wrap gap-2">
            {STATUSES.map((item) => (
              <Link
                key={item.value}
                href={`/admin/reports?tab=queue&status=${item.value}`}
                aria-current={item.value === status ? "page" : undefined}
                className={cx(
                  "text-meta inline-flex min-h-11 items-center rounded-full border px-3 pointer-fine:min-h-9",
                  item.value === status ? "bg-ink text-bg border-ink" : "border-line text-ink-2",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="border-line bg-bg rounded-panel overflow-hidden border">
            {queue.items.length ? (
              <ul className="divide-line flex flex-col divide-y">
                {queue.items.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-3 py-3"
                  >
                    <div className="min-w-0">
                      <p className="font-semibold">
                        {item.reason} · {item.target}
                      </p>
                      <p className="text-meta text-muted break-all" suppressHydrationWarning>
                        {item.reported?.email ?? "Deleted account"} · {when(item.created_at)}
                        {item.decision ? ` · ${item.decision}` : ""}
                      </p>
                    </div>
                    {canRead ? (
                      <Link
                        href={`${listHref}&report=${item.id}`}
                        scroll={false}
                        className="text-green text-meta-lg inline-flex min-h-11 items-center font-medium underline"
                      >
                        Open case
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted p-7 text-center">No reports here.</p>
            )}
          </div>
        </>
      ) : null}

      {appeals ? (
        <div className="border-line bg-bg rounded-panel overflow-hidden border">
          {appeals.items.length ? (
            <ul className="divide-line flex flex-col divide-y">
              {appeals.items.map((item) => (
                <li key={item.id} className="flex flex-col gap-2 px-3 py-3">
                  <p className="font-semibold break-all">
                    {item.person?.email ?? "Deleted account"} · {item.against}
                  </p>
                  <p className="text-meta-lg text-ink-2 whitespace-pre-wrap">{item.appeal}</p>
                  <AppealActions appealId={item.id} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted p-7 text-center">No open appeals.</p>
          )}
        </div>
      ) : null}

      {blocks ? (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3 sm:max-w-md">
            {[
              ["All blocks", blocks.total],
              ["Last 30 days", blocks.last_30_days],
            ].map(([label, value]) => (
              <div key={label} className="border-line bg-bg rounded-panel border p-4">
                <p className="text-mono text-muted font-mono uppercase">{label}</p>
                <p className="font-display tracking-display text-[30px] font-extrabold">{value}</p>
              </div>
            ))}
          </div>
          <section aria-labelledby="most-h" className="border-line bg-bg rounded-panel border p-4">
            <h2 id="most-h" className="font-display tracking-display text-[17px] font-extrabold">
              Most blocked, last 30 days
            </h2>
            {blocks.most_blocked.length ? (
              <ul className="divide-line mt-2 flex flex-col divide-y">
                {blocks.most_blocked.map((item) => (
                  <li key={item.user_id} className="flex justify-between gap-3 py-2.5">
                    <span className="break-all">
                      {item.email} <span className="text-muted">({item.status})</span>
                    </span>
                    <span className="font-mono">{item.times}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-meta text-muted mt-2">No blocks in the last 30 days.</p>
            )}
          </section>
        </div>
      ) : null}

      {found ? (
        <CaseDrawer found={found} permissions={me.permissions} closeHref={listHref} />
      ) : null}
    </>
  );
}
