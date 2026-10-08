import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AdminHeading } from "@/components/admin/admin-shell";
import { FlagActions, RuleSwitch } from "@/components/admin/content";
import { cx } from "@/components/ui/cx";
import { getAdminMe, getContentRules, getFlags } from "@/lib/admin/server";
import { CONTENT_RULES } from "@/lib/content-rules";

export const metadata: Metadata = { title: "Content moderation" };
export const dynamic = "force-dynamic";

const CARD = "border-line bg-bg rounded-panel border p-4";
const TITLE = "font-display tracking-display text-[17px] font-extrabold";
const SUB = "text-meta-lg text-ink-2 mb-2";

const ITEMS: Record<string, string> = {
  request: "Request",
  profile: "About text",
  intro: "Intro note",
};

function when(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

/** Content moderation (reference-admin.html): automatic rules flag text for review. */
export default async function ContentPage() {
  const me = await getAdminMe();
  if (!me.permissions.includes("view_users")) notFound();
  const [rules, flags] = await Promise.all([getContentRules(), getFlags()]);
  const canDecide = me.permissions.includes("handle_reports");
  const canSwitch = me.permissions.includes("manage_settings");

  return (
    <>
      <AdminHeading
        lead="Content moderation."
        rest="Flagged, not blocked."
        description="Rules flag requests, bios and intro notes when they're saved. Nothing is hidden until a moderator removes it."
      />

      <section aria-labelledby="queue-h" className={CARD}>
        <h2 id="queue-h" className={TITLE}>
          Flagged text
        </h2>
        <p className={SUB}>Oldest first. Keep it, or remove the text.</p>
        {flags.items.length ? (
          <ul className="divide-line flex flex-col divide-y">
            {flags.items.map((flag) => (
              <li key={flag.id} className="flex flex-col gap-2 py-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold">
                      {CONTENT_RULES[flag.rule]?.label ?? flag.rule} · {ITEMS[flag.item_type]}
                    </p>
                    <p className="text-meta text-muted break-all" suppressHydrationWarning>
                      {flag.email ?? "Deleted account"} · {when(flag.created_at)}
                    </p>
                  </div>
                  {canDecide && flag.flagged_text !== null ? <FlagActions flag={flag} /> : null}
                </div>
                <p
                  className={cx(
                    "bg-panel border-line rounded-card text-meta-lg border px-3 py-2 break-words whitespace-pre-wrap",
                    flag.flagged_text === null && "text-muted",
                  )}
                >
                  {flag.flagged_text ?? "This no longer exists."}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-meta text-muted py-4 text-center">Nothing flagged.</p>
        )}
        {flags.next_cursor ? (
          <p className="text-meta text-muted mt-2">Showing the oldest 50.</p>
        ) : null}
      </section>

      <section aria-labelledby="rules-h" className={cx(CARD, "mt-3")}>
        <h2 id="rules-h" className={TITLE}>
          Automatic rules
        </h2>
        <p className={SUB}>
          Fast checks when text is saved: no AI, nothing blocked.
          {canSwitch ? "" : " Owners and admins can turn them on or off."}
        </p>
        <div className="divide-line flex flex-col divide-y">
          {rules.rules.map((rule) => (
            <RuleSwitch key={rule.key} rule={rule.key} on={rule.on} canChange={canSwitch} />
          ))}
        </div>
      </section>
    </>
  );
}
