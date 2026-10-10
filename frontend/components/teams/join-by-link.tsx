"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ds/button";
import { InlineError } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { teamSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

/** The one button on the join page: joining is the person's own choice (ADR 0016). */
export function JoinByLink({ code, teamName }: { code: string; teamName: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function join() {
    setBusy(true);
    setError(null);
    try {
      const team = await browserApi(`/teams/join/${encodeURIComponent(code)}`, teamSchema, {
        method: "POST",
      });
      router.push(`/teams/${team.id}`);
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-3">
      <Button variant="primary" disabled={busy} onClick={join}>
        {busy ? "Joining…" : `Join ${teamName}`}
      </Button>
      {error ? <InlineError announce>{error}</InlineError> : null}
    </div>
  );
}
