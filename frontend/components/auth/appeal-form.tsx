"use client";

import { useState, type FormEvent } from "react";
import { z } from "zod";

import { Button } from "@/components/ds/button";
import { InlineError, Textarea } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { describeError } from "@/lib/auth/messages";

const APPEAL_MAX = 1000;
const receiptSchema = z.object({ created_at: z.string() });

/**
 * One appeal against a suspension or ban (A3). The token comes from a refused sign-in or
 * the notice email; no session is needed.
 */
export function AppealForm({ token }: { token: string }) {
  const [appeal, setAppeal] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await browserApi("/appeals", receiptSchema, {
        method: "POST",
        body: { token, appeal: appeal.trim() },
      });
      setSent(true);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <p role="status" className="text-meta-lg text-ink font-medium">
        Thanks. We&apos;ve received your appeal and will email you when it&apos;s decided.
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Textarea
        label="Appeal this decision"
        hint="Tell us why you think it's wrong. You can send one appeal."
        rows={4}
        maxLength={APPEAL_MAX}
        value={appeal}
        onChange={(event) => setAppeal(event.target.value)}
      />
      {error ? <InlineError announce>{error}</InlineError> : null}
      <Button
        variant="outline"
        type="submit"
        disabled={busy || !appeal.trim()}
        className="self-start"
      >
        {busy ? "Sending…" : "Send appeal"}
      </Button>
    </form>
  );
}
