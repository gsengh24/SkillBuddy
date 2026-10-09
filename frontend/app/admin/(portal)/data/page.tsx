import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AdminHeading } from "@/components/admin/admin-shell";
import { ProcessRequest, StartCsv } from "@/components/admin/data";
import { cx } from "@/components/ui/cx";
import { getAdminMe, getDataPage } from "@/lib/admin/server";

export const metadata: Metadata = { title: "Data and compliance" };
export const dynamic = "force-dynamic";

const CARD = "border-line bg-bg rounded-panel border p-4";
const TITLE = "font-display tracking-display text-[17px] font-extrabold";
const SUB = "text-meta-lg text-ink-2 mb-2";

const EXPORT_STATUS: Record<string, string> = {
  requested: "Waiting",
  ready: "Sent",
  expired: "Sent, link expired",
  failed: "Failed",
};

const CSV_STATUS: Record<string, string> = {
  queued: "Queued",
  running: "Building",
  ready: "Ready",
  failed: "Failed",
  expired: "Link expired",
};

function day(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" }) : "–";
}

function overdue(iso: string | null): boolean {
  return iso !== null && new Date(iso).getTime() < Date.now();
}

/** Data and compliance (reference-admin.html): handled on time. Owners and admins. */
export default async function DataPage() {
  const me = await getAdminMe();
  if (!me.permissions.includes("delete_data")) notFound();
  const page = await getDataPage();
  const isOwner = me.permissions.includes("manage_admins");
  const percent = page.consent.total
    ? Math.round((page.consent.current / page.consent.total) * 1000) / 10
    : 100;

  return (
    <>
      <AdminHeading
        lead="Data and compliance."
        rest="Handled on time."
        description="Requests from users, retention rules, consent, backups and exports."
      />

      <section aria-labelledby="req-h" className={CARD}>
        <h2 id="req-h" className={TITLE}>
          User data requests
        </h2>
        <p className={SUB}>
          Downloads and deletions asked for on the You page. Aim to finish within 30 days.
        </p>
        <h3 className="text-mono text-muted mt-2 mb-1 font-mono uppercase">Deletions</h3>
        {page.deletions_requested.length ? (
          <ul className="divide-line flex flex-col divide-y">
            {page.deletions_requested.map((item) => (
              <li
                key={item.user_id}
                className="flex flex-wrap items-center justify-between gap-2 py-2.5"
              >
                <div className="min-w-0">
                  <p className="font-semibold break-all">{item.email}</p>
                  <p className="text-meta text-muted" suppressHydrationWarning>
                    Asked {day(item.requested_at)} · deadline{" "}
                    <span className={cx(overdue(item.deadline) && "text-danger font-medium")}>
                      {day(item.deadline)}
                    </span>{" "}
                    · deleted automatically {day(item.scheduled_for)}
                  </p>
                </div>
                <ProcessRequest kind="deletion" id={item.user_id} email={item.email} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-meta text-muted">No account is waiting for deletion.</p>
        )}
        <h3 className="text-mono text-muted mt-4 mb-1 font-mono uppercase">Downloads</h3>
        {page.exports_requested.length ? (
          <ul className="divide-line flex flex-col divide-y">
            {page.exports_requested.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 py-2.5"
              >
                <div className="min-w-0">
                  <p className="font-semibold break-all">{item.email ?? "Deleted account"}</p>
                  <p className="text-meta text-muted" suppressHydrationWarning>
                    {EXPORT_STATUS[item.status]} · asked {day(item.requested_at)}
                    {item.processable ? (
                      <>
                        {" "}
                        · deadline{" "}
                        <span className={cx(overdue(item.deadline) && "text-danger font-medium")}>
                          {day(item.deadline)}
                        </span>
                      </>
                    ) : null}
                  </p>
                </div>
                {item.processable && item.email ? (
                  <ProcessRequest kind="export" id={item.id} email={item.email} />
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-meta text-muted">No download requests in the last 90 days.</p>
        )}
      </section>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <section aria-labelledby="ret-h" className={CARD}>
          <h2 id="ret-h" className={TITLE}>
            Retention rules
          </h2>
          <p className={SUB}>What the server removes on its own, and when.</p>
          <dl className="text-meta-lg divide-line flex flex-col divide-y">
            {page.retention.map((item) => (
              <div key={item.data} className="flex justify-between gap-3 py-1.5">
                <dt className="text-ink-2">{item.data}</dt>
                <dd className="text-right">{item.rule}</dd>
              </div>
            ))}
          </dl>
        </section>

        <div className="flex flex-col gap-3">
          <section aria-labelledby="consent-h" className={CARD}>
            <h2 id="consent-h" className={TITLE}>
              Consent
            </h2>
            <p className={SUB}>Who accepted the current terms ({page.consent.terms_version})</p>
            <p className="font-display tracking-display text-[34px] leading-none font-extrabold">
              {percent}%
            </p>
            <p className="text-meta-lg text-ink-2 mt-2">
              {page.consent.older} of {page.consent.total} accounts accepted an older version.
            </p>
          </section>

          <section aria-labelledby="backup-h" className={CARD}>
            <h2 id="backup-h" className={TITLE}>
              Backups and restore
            </h2>
            <p className="text-meta-lg text-ink-2">
              Neon keeps the backups; this page doesn&apos;t see them. Check them in the Neon
              console under your project&apos;s Restore page; the free plan&apos;s restore window is
              in docs/free-tier-limits.md.
            </p>
            <ol className="text-meta-lg mt-2 list-decimal pl-5">
              <li>Pause the app: switch off chats and intro requests on Settings.</li>
              <li>In Neon, restore to a new branch at the chosen time; never over main first.</li>
              <li>Check the new branch (counts of users, requests and messages).</li>
              <li>Point DATABASE_URL on Render at it, or restore main from it.</li>
              <li>Run Actions, Migrate staging only if the schema is behind.</li>
              <li>Switch the features back on and note what happened in the audit log.</li>
            </ol>
          </section>
        </div>
      </div>

      <section aria-labelledby="csv-h" className={cx(CARD, "mt-3")}>
        <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 id="csv-h" className={TITLE}>
              CSV exports
            </h2>
            <p className="text-meta-lg text-ink-2">
              Built in the background. Each link works for 24 hours.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StartCsv kind="users" label="Export users" />
            {isOwner ? <StartCsv kind="audit" label="Export audit log" /> : null}
          </div>
        </div>
        {page.csv_exports.length ? (
          <ul className="divide-line flex flex-col divide-y">
            {page.csv_exports.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="min-w-0">
                  <span className="font-semibold">
                    {item.kind === "users" ? "Users" : "Audit log"}
                  </span>{" "}
                  <span className="text-meta text-muted" suppressHydrationWarning>
                    {CSV_STATUS[item.status]} · {day(item.created_at)}
                    {item.rows !== null ? ` · ${item.rows.toLocaleString()} rows` : ""}
                  </span>
                </span>
                {item.status === "ready" ? (
                  <a
                    href={`/api/v1/admin/data/csv/${item.id}/download`}
                    className="text-green text-meta-lg inline-flex min-h-11 items-center font-medium underline"
                  >
                    Download
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-meta text-muted">No exports yet.</p>
        )}
      </section>
    </>
  );
}
