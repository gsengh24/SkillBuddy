"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { Button } from "@/components/ds/button";
import { InlineError } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { blockedSchema, noContentSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

/**
 * Block someone, after saying plainly what it does. A block works both ways and ends the
 * connection for good; the other person isn't told.
 */
export function BlockButton({
  userId,
  name,
  redirectTo,
}: {
  userId: string;
  /** How to refer to them, e.g. their name or "this person". */
  name: string;
  /** Where to go afterwards; without it the current page refreshes. */
  redirectTo?: string;
}) {
  const router = useRouter();
  const ids = useId();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await browserApi("/blocks", blockedSchema, { method: "POST", body: { user_id: userId } });
      if (redirectTo) router.push(redirectTo);
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  if (!confirming) {
    return (
      <Button variant="danger" onClick={() => setConfirming(true)}>
        Block
      </Button>
    );
  }
  return (
    <div
      role="group"
      aria-labelledby={`${ids}-title`}
      className="border-line rounded-panel bg-bg flex flex-col gap-3 border p-4"
    >
      <p id={`${ids}-title`} className="text-title text-ink">
        Block {name}?
      </p>
      <ul className="text-meta-lg text-ink-2 flex list-disc flex-col gap-1 pl-5">
        <li>Neither of you can message the other, and your chat closes for both of you.</li>
        <li>No intros between you, and you won&apos;t be shown to each other as matches.</li>
        <li>They won&apos;t be told.</li>
        <li>
          You can unblock later in Settings, but your chat stays closed: to talk again, one of you
          would need to send a new intro.
        </li>
      </ul>
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex flex-wrap gap-3">
        <Button variant="danger" disabled={busy} onClick={confirm}>
          {busy ? "Blocking…" : "Block"}
        </Button>
        <Button variant="ghost" disabled={busy} onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

/** Remove your block. The old connection stays ended. */
export function UnblockButton({ userId }: { userId: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await browserApi(`/blocks/${userId}`, noContentSchema, { method: "DELETE" });
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  if (!confirming) {
    return (
      <Button variant="outline" onClick={() => setConfirming(true)}>
        Unblock
      </Button>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-meta-lg text-ink-2">
        They may be shown to you as a match again, and you to them. Your old chat stays closed.
      </p>
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" disabled={busy} onClick={confirm}>
          {busy ? "Unblocking…" : "Unblock"}
        </Button>
        <Button variant="ghost" disabled={busy} onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
