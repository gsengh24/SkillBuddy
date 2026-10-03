import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { ReportReview } from "@/components/moderation/report-review";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { getModerationReports } from "@/lib/moderation/server";

export const metadata: Metadata = { title: "Moderation" };
export const dynamic = "force-dynamic";

/** Reports to review, oldest first. Only for accounts in MODERATOR_EMAILS. */
export default async function ModerationPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string | string[] }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/moderation");
  if (!user.is_moderator) notFound();
  const { status } = await searchParams;
  const resolved = status === "resolved";
  const page = await getModerationReports(resolved ? "resolved" : "open");

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-h1">Moderation</h1>
        <p className="text-muted">
          You see only the copy each report kept, never whole conversations. Every action is logged.
        </p>
        <nav aria-label="Moderation" className="flex flex-wrap gap-x-6 gap-y-2">
          {resolved ? (
            <TextLink href="/moderation">Open reports</TextLink>
          ) : (
            <TextLink href="/moderation?status=resolved">Resolved reports</TextLink>
          )}
          <TextLink href="/moderation/suspended">Suspended accounts</TextLink>
        </nav>
      </header>
      <h2 className="text-section">{resolved ? "Resolved reports" : "Open reports"}</h2>
      {page.items.length ? (
        <ul className="flex flex-col gap-6">
          {page.items.map((report) => (
            <li key={report.id}>
              <ReportReview report={report} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted">{resolved ? "No resolved reports." : "No open reports."}</p>
      )}
      {page.next_cursor ? (
        <p className="text-small text-muted">Showing the first 50. Resolve some to see the rest.</p>
      ) : null}
    </div>
  );
}
