import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AdminHeading } from "@/components/admin/admin-shell";
import { EndBanner, NewBanner, RetryEmail, SendTest } from "@/components/admin/comms";
import { cx } from "@/components/ui/cx";
import { getAdminMe, getComms, getEmailSends } from "@/lib/admin/server";
import { BANNER_STYLES } from "@/lib/banner-styles";

export const metadata: Metadata = { title: "Communication" };
export const dynamic = "force-dynamic";

const CARD = "border-line bg-bg rounded-panel border p-4";
const TITLE = "font-display tracking-display text-[17px] font-extrabold";
const SUB = "text-meta-lg text-ink-2 mb-2";

const FILTERS = [
  { value: "", label: "All" },
  { value: "failed", label: "Failed" },
  { value: "delivered", label: "Delivered" },
];

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** Communication (reference-admin.html): banners, email templates and the send log. */
export default async function CommsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const me = await getAdminMe();
  if (!me.permissions.includes("manage_settings")) notFound();
  const { status: asked } = await searchParams;
  const status = asked === "failed" || asked === "delivered" ? asked : null;
  const [comms, sends] = await Promise.all([getComms(), getEmailSends(status)]);
  const live = comms.banners.filter((banner) => banner.live);

  return (
    <>
      <AdminHeading
        lead="Communication."
        rest="Say it once, clearly."
        description="Announcements, email templates and delivery."
      />

      <div className="grid gap-3 md:grid-cols-2">
        <section aria-labelledby="new-h" className={CARD}>
          <h2 id="new-h" className={TITLE}>
            New announcement
          </h2>
          <p className={SUB}>Shows as a banner at the top of the app.</p>
          <NewBanner />
        </section>

        <div className="flex flex-col gap-3">
          <section aria-labelledby="live-h" className={CARD}>
            <h2 id="live-h" className={TITLE}>
              Active banners
            </h2>
            <p className={SUB}>Users can dismiss them.</p>
            {live.length ? (
              <ul className="flex flex-col gap-2">
                {live.map((banner) => (
                  <li key={banner.id} className="flex items-start gap-2">
                    <p
                      className={cx(
                        "rounded-card text-meta-lg min-w-0 flex-1 border px-3 py-2 break-words",
                        BANNER_STYLES[banner.kind],
                      )}
                    >
                      {banner.message}
                      {banner.ends_at ? (
                        <span className="text-meta block opacity-80" suppressHydrationWarning>
                          Ends {when(banner.ends_at)}
                        </span>
                      ) : null}
                    </p>
                    <EndBanner banner={banner} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-meta text-muted">No banner is showing.</p>
            )}
          </section>

          <section aria-labelledby="tpl-h" className={CARD}>
            <h2 id="tpl-h" className={TITLE}>
              Email templates
            </h2>
            <p className={SUB}>Read only. A test goes to your own address with made-up values.</p>
            <ul className="divide-line flex flex-col divide-y">
              {comms.templates.map((template) => (
                <li key={template.key} className="flex items-center justify-between gap-3 py-2">
                  <span className="min-w-0">
                    <span className="block font-semibold">{template.name}</span>
                    <span className="text-meta text-muted">{template.sent_when}</span>
                  </span>
                  <SendTest templateKey={template.key} />
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>

      <section aria-labelledby="log-h" className={cx(CARD, "mt-3")}>
        <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 id="log-h" className={TITLE}>
              Send log
            </h2>
            <p className="text-meta-lg text-ink-2">Last 30 days, newest first. Never the body.</p>
          </div>
          <nav aria-label="Email status" className="flex flex-wrap gap-2">
            {FILTERS.map((filter) => (
              <Link
                key={filter.value}
                href={filter.value ? `/admin/comms?status=${filter.value}` : "/admin/comms"}
                aria-current={(status ?? "") === filter.value ? "page" : undefined}
                className={cx(
                  "text-meta inline-flex min-h-11 items-center rounded-full border px-3 pointer-fine:min-h-9",
                  (status ?? "") === filter.value
                    ? "bg-ink text-bg border-ink"
                    : "border-line text-ink-2",
                )}
              >
                {filter.label}
              </Link>
            ))}
          </nav>
        </div>
        {sends.items.length ? (
          <ul className="divide-line flex flex-col divide-y">
            {sends.items.map((send) => (
              <li
                key={send.id}
                className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-0.5 py-2 md:grid-cols-[auto_minmax(0,1fr)_auto_auto_auto]"
              >
                <span className="text-meta text-muted font-mono" suppressHydrationWarning>
                  {when(send.created_at)}
                </span>
                <span className="min-w-0 break-all md:order-none">{send.to}</span>
                <span className="text-meta-lg text-ink-2">{send.template}</span>
                <span
                  className={cx(
                    "text-meta font-medium",
                    send.status === "failed" ? "text-danger" : "text-green",
                  )}
                  title={send.error ?? undefined}
                >
                  {send.status === "failed" ? "Failed" : "Delivered"}
                  {send.retried_at ? " · retried" : ""}
                </span>
                <span className="justify-self-end">
                  {send.retryable ? <RetryEmail send={send} /> : null}
                </span>
                {send.error ? (
                  <span className="text-meta text-muted col-span-full break-words">
                    {send.error}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-meta text-muted py-4 text-center">No emails here.</p>
        )}
      </section>
    </>
  );
}
