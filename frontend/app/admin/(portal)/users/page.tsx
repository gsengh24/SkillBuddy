import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AdminHeading } from "@/components/admin/admin-shell";
import { UserDrawer } from "@/components/admin/users";
import { buttonClasses } from "@/components/ds/button";
import { STATUS_LABELS, userStatusSchema } from "@/lib/admin/schemas";
import { brand } from "@/lib/brand";
import { getAdminMe, getUserDetail, getUsers } from "@/lib/admin/server";
import { intents as INTENTS } from "@/lib/design/tokens";

export const metadata: Metadata = { title: "Users" };
export const dynamic = "force-dynamic";

type Search = {
  q?: string;
  status?: string;
  intent?: string;
  flagged?: string;
  cursor?: string;
  user?: string;
};

const FIELD =
  "rounded-input border-muted-2 bg-bg text-ink h-11 border px-3 text-[16px] sm:text-body";

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" }) : "Never";
}

/** The list's own query string, without paging or the open drawer. */
function filtersOf(search: Search): URLSearchParams {
  const params = new URLSearchParams();
  if (search.q?.trim()) params.set("q", search.q.trim());
  if (search.status && userStatusSchema.safeParse(search.status).success) {
    params.set("status", search.status);
  }
  if (search.intent && search.intent in INTENTS) params.set("intent", search.intent);
  if (search.flagged === "true") params.set("flagged", "true");
  return params;
}

function hrefWith(base: URLSearchParams, extra: Record<string, string>): string {
  const params = new URLSearchParams(base);
  for (const [key, value] of Object.entries(extra)) params.set(key, value);
  const query = params.toString();
  return query ? `/admin/users?${query}` : "/admin/users";
}

/** Users (reference-admin.html): search, filters, paging, and the detail drawer. */
export default async function UsersPage({ searchParams }: { searchParams: Promise<Search> }) {
  const search = await searchParams;
  const filters = filtersOf(search);
  const listParams = new URLSearchParams(filters);
  if (search.cursor) listParams.set("cursor", search.cursor);
  const [me, page, detail] = await Promise.all([
    getAdminMe(),
    getUsers(listParams),
    search.user ? getUserDetail(search.user).catch(() => null) : Promise.resolve(null),
  ]);
  if (!me.permissions.includes("view_users")) notFound();
  const here = new URLSearchParams(filters);
  if (search.cursor) here.set("cursor", search.cursor);

  return (
    <>
      <AdminHeading
        lead="Users."
        rest={`Everyone on ${brand.name}.`}
        description="Search, review and act on any account. Every action needs a reason and is recorded."
      />

      <form method="get" className="mb-3 flex flex-wrap items-end gap-2" role="search">
        <label className="flex min-w-[180px] flex-1 flex-col gap-1">
          <span className="text-meta-lg font-medium">Search</span>
          <input
            name="q"
            defaultValue={search.q ?? ""}
            placeholder="Name or email"
            className={FIELD}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-meta-lg font-medium">Status</span>
          <select name="status" defaultValue={filters.get("status") ?? ""} className={FIELD}>
            <option value="">All statuses</option>
            {userStatusSchema.options.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-meta-lg font-medium">Intent</span>
          <select name="intent" defaultValue={filters.get("intent") ?? ""} className={FIELD}>
            <option value="">All intents</option>
            {Object.entries(INTENTS).map(([value, { label }]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-h-11 items-center gap-2">
          <input
            type="checkbox"
            name="flagged"
            value="true"
            defaultChecked={filters.get("flagged") === "true"}
            className="accent-green size-4"
          />
          <span>Flagged only</span>
        </label>
        <button type="submit" className={buttonClasses({ variant: "primary" })}>
          Apply
        </button>
      </form>

      <div className="border-line bg-bg rounded-panel overflow-hidden border">
        <p className="text-meta text-muted border-line border-b px-3 py-2.5" aria-live="polite">
          {page.total} {page.total === 1 ? "person" : "people"}
        </p>
        {page.items.length ? (
          <table className="text-meta-lg w-full border-collapse">
            <thead className="max-md:sr-only">
              <tr>
                {["Person", "Status", "Intents", "Joined", "Last sign-in"].map((heading) => (
                  <th
                    key={heading}
                    scope="col"
                    className="text-mono text-muted bg-panel border-line border-b px-3 py-2.5 text-left font-mono uppercase"
                  >
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.items.map((row) => (
                <tr
                  key={row.id}
                  className="border-line border-b last:border-b-0 max-md:block max-md:px-3 max-md:py-2.5"
                >
                  <td className="px-3 py-2.5 max-md:block max-md:p-0">
                    <Link
                      href={hrefWith(here, { user: row.id })}
                      scroll={false}
                      className="flex min-h-11 flex-col justify-center"
                    >
                      <span className="font-semibold break-all">{row.name ?? "No profile"}</span>
                      <span className="text-meta text-muted break-all">{row.email}</span>
                    </Link>
                  </td>
                  <td className="px-3 py-2.5 max-md:inline-block max-md:p-0 max-md:pr-3">
                    <span className="rounded-chip border-line bg-panel text-ink-2 border px-1.5 py-0.5 font-mono text-[10px] uppercase">
                      {STATUS_LABELS[row.status]}
                    </span>
                    {row.flagged ? (
                      <span className="rounded-chip border-danger text-danger ml-1.5 border px-1.5 py-0.5 font-mono text-[10px] uppercase">
                        Flagged
                      </span>
                    ) : null}
                  </td>
                  <td className="text-ink-2 px-3 py-2.5 max-md:inline-block max-md:p-0 max-md:pr-3">
                    {row.intents
                      .map((i) => INTENTS[i as keyof typeof INTENTS]?.label ?? i)
                      .join(", ") || "None"}
                  </td>
                  <td
                    className="text-muted px-3 py-2.5 max-md:inline-block max-md:p-0 max-md:pr-3"
                    suppressHydrationWarning
                  >
                    <span className="md:hidden">Joined </span>
                    {when(row.created_at)}
                  </td>
                  <td
                    className="text-muted px-3 py-2.5 max-md:inline-block max-md:p-0"
                    suppressHydrationWarning
                  >
                    <span className="md:hidden">Last sign-in </span>
                    {when(row.last_login_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-muted p-7 text-center">Nobody matches these filters.</p>
        )}
        <nav
          aria-label="Pages"
          className="border-line flex justify-between gap-2 border-t px-3 py-2.5"
        >
          {search.cursor ? (
            <Link
              href={hrefWith(filters, {})}
              className={buttonClasses({ variant: "ghost", size: "compact" })}
            >
              First page
            </Link>
          ) : (
            <span />
          )}
          {page.next_cursor ? (
            <Link
              href={hrefWith(filters, { cursor: page.next_cursor })}
              className={buttonClasses({ variant: "outline", size: "compact" })}
            >
              Next page
            </Link>
          ) : null}
        </nav>
      </div>

      {detail ? (
        <UserDrawer user={detail} permissions={me.permissions} closeHref={hrefWith(here, {})} />
      ) : null}
    </>
  );
}
