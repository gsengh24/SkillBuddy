import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AdminHeading } from "@/components/admin/admin-shell";
import { FeatureSwitch, LimitField } from "@/components/admin/settings";
import { cx } from "@/components/ui/cx";
import { getAdminMe, getSettings } from "@/lib/admin/server";
import { intents, type Intent } from "@/lib/design/tokens";

export const metadata: Metadata = { title: "Settings" };
export const dynamic = "force-dynamic";

const CARD = "border-line bg-bg rounded-panel border p-4";
const TITLE = "font-display tracking-display text-[17px] font-extrabold";
const SUB = "text-meta-lg text-ink-2 mb-2";

const MODES: Record<string, string> = {
  open: "On: anyone can sign up",
  invite_only: "Invite only",
  closed: "Off: nobody new can join",
};

/** Settings (reference-admin.html): turn things on and off. Owners and admins only. */
export default async function SettingsPage() {
  const me = await getAdminMe();
  if (!me.permissions.includes("manage_settings")) notFound();
  const settings = await getSettings();

  return (
    <>
      <AdminHeading
        lead="Settings."
        rest="Turn things on and off."
        description="Changes apply within a minute without a deploy. Each change is recorded."
      />

      <div className="grid gap-3 md:grid-cols-2">
        <section aria-labelledby="app-h" className={CARD}>
          <h2 id="app-h" className={TITLE}>
            App
          </h2>
          <p className={SUB}>Set on the server</p>
          <dl className="text-meta-lg grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <dt className="text-muted">App name</dt>
            <dd className="break-all">
              {settings.server.app_name}{" "}
              <span className="text-muted font-mono text-[11px]">APP_NAME</span>
            </dd>
            <dt className="text-muted">Terms version</dt>
            <dd className="break-all">
              {settings.server.terms_version}{" "}
              <span className="text-muted font-mono text-[11px]">TERMS_VERSION</span>
            </dd>
            <dt className="text-muted">Environment</dt>
            <dd className="capitalize">{settings.server.environment}</dd>
          </dl>
        </section>

        <section aria-labelledby="limits-h" className={CARD}>
          <h2 id="limits-h" className={TITLE}>
            Limits
          </h2>
          <p className={SUB}>Per user</p>
          <div className="flex flex-col gap-3">
            {settings.limits.map((limit) => (
              <LimitField key={`${limit.key}-${limit.value}`} limit={limit} />
            ))}
          </div>
        </section>
      </div>

      <section aria-labelledby="flags-h" className={cx(CARD, "mt-3")}>
        <h2 id="flags-h" className={TITLE}>
          Feature switches
        </h2>
        <p className={SUB}>Turn a feature off for everyone if something goes wrong.</p>
        <div className="divide-line flex flex-col divide-y">
          <div className="flex min-h-11 items-start justify-between gap-3 py-2.5">
            <span className="flex flex-col">
              <span className="text-ink font-semibold">Open signups</span>
              <span className="text-meta-lg text-muted">
                {MODES[settings.signup_mode]}. Change it on{" "}
                <Link href="/admin/access" className="text-green underline">
                  Signup and access
                </Link>
                .
              </span>
            </span>
          </div>
          {settings.features.map((feature) => (
            <FeatureSwitch key={feature.key} feature={feature.key} on={feature.on} />
          ))}
        </div>
      </section>

      <section aria-labelledby="intents-h" className={cx(CARD, "mt-3")}>
        <h2 id="intents-h" className={TITLE}>
          Intent types
        </h2>
        <p className={SUB}>Shown on the Home composer and on profiles. Read only for now.</p>
        <ul className="flex flex-wrap gap-1.5">
          {settings.intents.map((intent) => (
            <li
              key={intent}
              className="rounded-chip border-line text-ink border px-2 py-0.5 text-[12px]"
            >
              {intents[intent as Intent]?.label ?? intent}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
