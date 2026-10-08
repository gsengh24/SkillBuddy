import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  ApplicationActions,
  CreateCode,
  DomainList,
  InviteNext,
  ModeSwitch,
  RevokeCode,
} from "@/components/admin/access";
import { AdminHeading } from "@/components/admin/admin-shell";
import { cx } from "@/components/ui/cx";
import type { InviteCode } from "@/lib/admin/schemas";
import { getAccess, getAdminMe, getApplications, getInviteCodes } from "@/lib/admin/server";
import { sourceLabel } from "@/lib/auth/application-sources";

export const metadata: Metadata = { title: "Signup and access" };
export const dynamic = "force-dynamic";

const CARD = "border-line bg-bg rounded-panel border p-4";
const TITLE = "font-display tracking-display text-[17px] font-extrabold";
const SUB = "text-meta-lg text-ink-2 mb-2";

const STATUS_LABEL: Record<InviteCode["status"], string> = {
  active: "Active",
  used_up: "Used up",
  expired: "Expired",
  revoked: "Revoked",
};

function day(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" }) : "Never";
}

/** Signup and access (reference-admin.html): who gets in. Owners and admins only. */
export default async function AccessPage() {
  const me = await getAdminMe();
  if (!me.permissions.includes("manage_signup")) notFound();
  const [access, applications, codes] = await Promise.all([
    getAccess(),
    getApplications(),
    getInviteCodes(),
  ]);

  return (
    <>
      <AdminHeading
        lead="Signup and access."
        rest="Who gets in."
        description="Choose how people join, approve applications and manage invite codes."
      />

      <section aria-labelledby="mode-h" className={CARD}>
        <h2 id="mode-h" className={TITLE}>
          Signup mode
        </h2>
        <p className={SUB}>Applies immediately to new visitors. Existing users are not affected.</p>
        <ModeSwitch mode={access.mode} />
      </section>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <section aria-labelledby="queue-h" className={CARD}>
          <h2 id="queue-h" className={TITLE}>
            Approval queue
          </h2>
          <p className={SUB}>People waiting to join, oldest first</p>
          {applications.items.length ? (
            <ul className="divide-line flex flex-col divide-y">
              {applications.items.map((item) => (
                <li
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="font-semibold break-all">{item.email}</p>
                    <p className="text-meta text-muted" suppressHydrationWarning>
                      {sourceLabel(item.source)} · {day(item.created_at)}
                    </p>
                  </div>
                  <ApplicationActions application={item} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-meta text-muted py-4 text-center">All caught up.</p>
          )}
          {applications.next_cursor ? (
            <p className="text-meta text-muted mt-2">Showing the oldest 50.</p>
          ) : null}
        </section>

        <section aria-labelledby="wait-h" className={CARD}>
          <h2 id="wait-h" className={TITLE}>
            Waitlist
          </h2>
          <p className={SUB}>Applications not yet invited</p>
          <p className="font-display tracking-display mb-3 text-[40px] leading-none font-extrabold">
            {access.waitlist}
          </p>
          <InviteNext waitlist={access.waitlist} />
        </section>
      </div>

      <section aria-labelledby="codes-h" className={cx(CARD, "mt-3")}>
        <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 id="codes-h" className={TITLE}>
              Invite codes
            </h2>
            <p className="text-meta-lg text-ink-2">Create limited codes to share with groups</p>
          </div>
          <CreateCode />
        </div>
        {codes.items.length ? (
          <ul className="divide-line flex flex-col divide-y">
            {codes.items.map((item) => (
              <li
                key={item.id}
                className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 py-2.5 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1.4fr)_auto_auto_auto_auto]"
              >
                <b className="font-mono break-all">{item.code}</b>
                <span className="text-meta text-muted justify-self-end md:hidden">
                  {STATUS_LABEL[item.status]}
                </span>
                <span className="text-meta-lg text-ink-2 col-span-2 break-all md:col-span-1">
                  {item.created_by ?? "Former admin"}
                </span>
                <span className="text-meta-lg font-mono">
                  {item.uses} / {item.max_uses}
                </span>
                <span className="text-meta-lg" suppressHydrationWarning>
                  Expires {day(item.expires_at)}
                </span>
                <span
                  className={cx(
                    "text-meta hidden md:inline",
                    item.status === "active" ? "text-green font-medium" : "text-muted",
                  )}
                >
                  {STATUS_LABEL[item.status]}
                </span>
                <span className="col-span-2 md:col-span-1 md:justify-self-end">
                  {item.status === "active" ? <RevokeCode code={item} /> : null}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-meta text-muted py-4 text-center">No invite codes yet.</p>
        )}
      </section>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <section aria-labelledby="allow-h" className={CARD}>
          <h2 id="allow-h" className={TITLE}>
            Allowed email domains
          </h2>
          <p className={SUB}>Leave empty to allow any domain. New accounts only.</p>
          <DomainList kind="allowed" domains={access.allowed_domains} placeholder="example.edu" />
        </section>
        <section aria-labelledby="block-h" className={CARD}>
          <h2 id="block-h" className={TITLE}>
            Blocked email domains
          </h2>
          <p className={SUB}>Disposable and abusive domains. New accounts only.</p>
          <DomainList
            kind="blocked"
            domains={access.blocked_domains}
            placeholder="mailinator.com"
          />
        </section>
      </div>
    </>
  );
}
