import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AdminHeading } from "@/components/admin/admin-shell";
import { StartCsv } from "@/components/admin/data";
import { AuditLog, InviteAdmin, RemoveAdmin } from "@/components/admin/team-actions";
import { ROLE_LABELS } from "@/lib/admin/schemas";
import { getAdminMe, getAudit, getPermissionTable, getTeam } from "@/lib/admin/server";

export const metadata: Metadata = { title: "Team and audit" };
export const dynamic = "force-dynamic";

function when(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "Not yet";
}

const CARD = "border-line bg-bg rounded-panel border p-4";
const CARD_TITLE = "font-display tracking-display text-[17px] font-extrabold";

/** Team and audit (reference-admin.html): admin accounts, the permission table and the log. */
export default async function TeamPage() {
  const me = await getAdminMe();
  if (!me.permissions.includes("manage_admins")) notFound();
  const [team, table, audit] = await Promise.all([getTeam(), getPermissionTable(), getAudit()]);

  return (
    <>
      <AdminHeading
        lead="Team and audit."
        rest="Who can do what."
        description="Admin accounts, roles and the record of everything done in this portal."
        actions={<InviteAdmin />}
      />
      <div className="flex flex-col gap-3">
        <section aria-labelledby="admins-h" className={CARD}>
          <h2 id="admins-h" className={CARD_TITLE}>
            Admin accounts
          </h2>
          <p className="text-meta text-muted mb-3">Two-step login is required for every admin.</p>
          <ul className="divide-line flex flex-col divide-y">
            {team.items.map((member) => (
              <li
                key={member.user_id}
                className="flex flex-wrap items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0">
                  <p className="font-semibold break-all">{member.email}</p>
                  <p className="text-meta text-muted" suppressHydrationWarning>
                    {ROLE_LABELS[member.role]}
                    {member.from_environment ? " (set on the server)" : ""} ·{" "}
                    {member.two_step_enabled ? "Two-step on" : "Two-step not set up"} · Last active{" "}
                    {when(member.last_active_at)}
                  </p>
                </div>
                {member.from_environment ? null : (
                  <RemoveAdmin userId={member.user_id} email={member.email} />
                )}
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="roles-h" className={CARD}>
          <h2 id="roles-h" className={CARD_TITLE}>
            What each role can do
          </h2>
          <p className="text-meta text-muted mb-3">Checked on the server for every request.</p>
          <div className="overflow-x-auto">
            <table className="text-meta-lg w-full border-collapse">
              <thead>
                <tr>
                  <th
                    scope="col"
                    className="text-mono text-muted py-2 pr-3 text-left font-mono uppercase"
                  >
                    Permission
                  </th>
                  {table.roles.map((role) => (
                    <th
                      key={role}
                      scope="col"
                      className="text-mono text-muted px-2 py-2 text-center font-mono uppercase"
                    >
                      {ROLE_LABELS[role]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row) => (
                  <tr key={row.permission} className="border-line border-t">
                    <th scope="row" className="py-2 pr-3 text-left font-normal">
                      {row.label}
                    </th>
                    {table.roles.map((role) => (
                      <td key={role} className="px-2 py-2 text-center">
                        {row.roles.includes(role) ? (
                          <span className="text-green font-semibold">Yes</span>
                        ) : (
                          <span className="text-muted">No</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section aria-labelledby="audit-h" className={CARD}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 id="audit-h" className={CARD_TITLE}>
                Audit log
              </h2>
              <p className="text-meta text-muted mb-1">Entries can&apos;t be edited or deleted.</p>
            </div>
            <StartCsv kind="audit" label="Export CSV" doneHref="/admin/data" />
          </div>
          <AuditLog initial={audit.items} initialCursor={audit.next_cursor} />
        </section>
      </div>
    </>
  );
}
