import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AdminHeading } from "@/components/admin/admin-shell";
import { ProbeButton, ProviderSwitch, RerunForm } from "@/components/admin/content";
import { cx } from "@/components/ui/cx";
import { getAdminMe, getAiOverview } from "@/lib/admin/server";

export const metadata: Metadata = { title: "Matching and AI" };
export const dynamic = "force-dynamic";

const CARD = "border-line bg-bg rounded-panel border p-4";
const TITLE = "font-display tracking-display text-[17px] font-extrabold";
const SUB = "text-meta-lg text-ink-2 mb-2";

function percent(value: number | null): string {
  return value === null ? "–" : `${Math.round(value * 1000) / 10}%`;
}

function ms(value: number | null): string {
  return value === null ? "–" : `${value} ms`;
}

const STATUS: Record<string, string> = {
  ok: "OK",
  degraded: "Degraded",
  idle: "No calls today",
  off: "Off",
};

/** Matching and AI (reference-admin.html): providers, quality and tools. Owners and admins. */
export default async function AiPage() {
  const me = await getAdminMe();
  if (!me.permissions.includes("manage_ai")) notFound();
  const ai = await getAiOverview();
  const quality = ai.quality;

  return (
    <>
      <AdminHeading
        lead="Matching and AI."
        rest="How well it works."
        description="Providers, response times, cost and how people respond to matches. No prompt or response text is kept."
      />

      {ai.llm_enabled ? null : (
        <p className="border-line bg-panel rounded-panel text-meta-lg mb-3 border px-4 py-3">
          AI is switched off on the server (AI_LLM_ENABLED): matching uses the rule-based path.
        </p>
      )}

      <section aria-labelledby="prov-h" className={CARD}>
        <h2 id="prov-h" className={TITLE}>
          Providers
        </h2>
        <p className={SUB}>Last 24 hours; cost is today&apos;s.</p>
        {ai.providers.length ? (
          <ul className="divide-line flex flex-col divide-y">
            {ai.providers.map((provider) => (
              <li
                key={provider.name}
                className="grid gap-x-4 gap-y-1 py-2 md:grid-cols-[minmax(0,1.6fr)_repeat(5,auto)] md:items-center"
              >
                <ProviderSwitch name={provider.name} role={provider.role} on={provider.on} />
                <span className="text-meta-lg">
                  <span className="text-muted md:hidden">Status </span>
                  <span
                    className={cx(
                      provider.status === "ok" && "text-green font-medium",
                      provider.status === "degraded" && "text-danger font-medium",
                    )}
                  >
                    {STATUS[provider.status]}
                  </span>
                </span>
                <span className="text-meta-lg font-mono">
                  <span className="text-muted font-sans md:hidden">p50 / p95 </span>
                  {ms(provider.p50_ms)} / {ms(provider.p95_ms)}
                </span>
                <span className="text-meta-lg">
                  <span className="text-muted md:hidden">Errors </span>
                  {percent(provider.error_rate)} of {provider.calls_24h}
                </span>
                <span className="text-meta-lg font-mono">
                  <span className="text-muted font-sans md:hidden">Cost today </span>
                  {provider.cost_today.toLocaleString()} / {provider.daily_budget.toLocaleString()}{" "}
                  {provider.cost_unit}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-meta text-muted py-4 text-center">
            No AI provider is configured on the server.
          </p>
        )}
        {Object.keys(ai.fallbacks_today).length ? (
          <p className="text-meta text-muted mt-2">
            Rule-based answers today:{" "}
            {Object.entries(ai.fallbacks_today)
              .map(([reason, count]) => `${reason.replaceAll("_", " ")} ${count}`)
              .join(", ")}
          </p>
        ) : null}
        <div className="mt-3">
          <ProbeButton />
        </div>
      </section>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <section aria-labelledby="quality-h" className={CARD}>
          <h2 id="quality-h" className={TITLE}>
            Match quality
          </h2>
          <p className={SUB}>
            Intros sent in the last {quality.days} days: {quality.intros_sent}
          </p>
          <dl className="grid grid-cols-3 gap-3">
            {[
              ["Accepted", quality.accept_rate],
              ["Ignored", quality.ignore_rate],
              ["Reported", quality.report_rate],
            ].map(([label, value]) => (
              <div key={label as string}>
                <dt className="text-mono text-muted font-mono uppercase">{label as string}</dt>
                <dd className="font-display tracking-display text-[26px] font-extrabold">
                  {percent(value as number | null)}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section aria-labelledby="eval-h" className={CARD}>
          <h2 id="eval-h" className={TITLE}>
            Evaluation set
          </h2>
          {ai.evals.connected ? (
            <p className="text-meta-lg">
              {ai.evals.labelled} of {ai.evals.total} pairs labelled · latest score{" "}
              {percent(ai.evals.latest_score)}
            </p>
          ) : (
            <p className="text-meta-lg text-ink-2">
              Not connected. The labelled pairs live in the repository (backend/evals), not in the
              database, so the server can&apos;t read them yet.
            </p>
          )}
        </section>
      </div>

      <section aria-labelledby="rerun-h" className={cx(CARD, "mt-3 md:max-w-xl")}>
        <h2 id="rerun-h" className={TITLE}>
          Re-run matching for one person
        </h2>
        <p className={SUB}>Runs in the background. At most 10 an hour.</p>
        <RerunForm />
      </section>
    </>
  );
}
