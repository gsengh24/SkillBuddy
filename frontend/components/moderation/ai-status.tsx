"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError } from "@/components/ds/fields";
import { Button } from "@/components/ds/button";
import { browserApi } from "@/lib/api/browser";
import { probeQueuedSchema, type AIStatus } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

const OUTCOMES: Record<string, string> = {
  ok: "answered",
  timeout: "timed out",
  rate_limited: "rate-limited",
  unavailable: "unavailable",
  error: "error",
  invalid: "invalid answer",
  over_budget: "over its daily budget",
  global_cap: "daily AI cap reached",
};

const REASONS: Record<string, string> = {
  no_provider: "no provider could answer",
  disabled: "AI switched off (AI_LLM_ENABLED)",
  user_cap: "a person's daily limit",
  global_cap: "the daily AI cap",
  privacy: "blocked for privacy (contact details found)",
};

function counts(record: Record<string, number>, words: Record<string, string>) {
  const entries = Object.entries(record);
  if (!entries.length) return "none today";
  return entries.map(([key, value]) => `${value} ${words[key] ?? key}`).join(", ");
}

/** Today's AI usage by provider, and a button to test every provider on its own. */
export function AIStatusView({ status }: { status: AIStatus }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function probe() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await browserApi("/moderation/ai/probe", probeQueuedSchema, { method: "POST" });
      setMessage("Test queued. Reload this page in a minute to see the results.");
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <p className={status.enabled ? "text-ink" : "text-danger font-medium"}>
        {status.enabled
          ? "AI is switched on."
          : "AI is switched off (AI_LLM_ENABLED=false): every answer uses the template."}{" "}
        {status.global_calls_today} of {status.global_cap} AI calls used today (UTC).
      </p>

      <section aria-labelledby="providers-h" className="flex flex-col gap-3">
        <h2
          id="providers-h"
          className="font-display tracking-display text-[20px] leading-tight font-extrabold"
        >
          Providers, in fallback order
        </h2>
        {status.providers.length ? (
          <ul className="border-line border-t">
            {status.providers.map((provider) => (
              <li key={provider.name}>
                <div className="border-line flex flex-col gap-1 border-b py-3">
                  <p className="text-ink font-mono font-bold break-all">{provider.name}</p>
                  <p>Real calls today: {counts(provider.calls, OUTCOMES)}.</p>
                  <p>Tests today: {counts(provider.probes, OUTCOMES)}.</p>
                  {provider.daily_budget ? (
                    <p className="text-meta-lg text-muted">
                      {provider.used_today.toLocaleString()} of{" "}
                      {provider.daily_budget.toLocaleString()} {provider.unit} used today.
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted">
            No AI provider is configured: every answer uses the template.
          </p>
        )}
      </section>

      <section aria-labelledby="fallback-h" className="flex flex-col gap-2">
        <h2
          id="fallback-h"
          className="font-display tracking-display text-[20px] leading-tight font-extrabold"
        >
          Template answers today
        </h2>
        <p>{counts(status.fallbacks, REASONS)}.</p>
      </section>

      <section aria-labelledby="test-h" className="flex flex-col gap-3">
        <h2
          id="test-h"
          className="font-display tracking-display text-[20px] leading-tight font-extrabold"
        >
          Test the providers
        </h2>
        <p className="text-meta-lg">
          Sends one short, fixed test message (no user data) to each provider on its own, so the
          backup is tested too. It uses a little of each provider&apos;s daily budget.
        </p>
        <Button variant="outline" onClick={probe} disabled={busy} className="self-start">
          {busy ? "Queuing…" : "Test the AI providers"}
        </Button>
        {message ? (
          <p role="status" className="text-meta-lg text-ink">
            {message}
          </p>
        ) : null}
        {error ? <InlineError announce>{error}</InlineError> : null}
      </section>
    </div>
  );
}
