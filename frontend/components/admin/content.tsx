"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { Input } from "@/components/ds/fields";
import { probeQueuedSchema, rerunQueuedSchema, type Flag } from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { CONTENT_RULES } from "@/lib/content-rules";

import { ReasonDialog } from "./reason-dialog";

/** A switch that asks for a reason before changing (rules and AI providers). */
function ReasonSwitch({
  label,
  hint,
  on,
  disabled = false,
  send,
}: {
  label: string;
  hint: string;
  on: boolean;
  disabled?: boolean;
  send: (on: boolean, reason: string) => Promise<void>;
}) {
  const router = useRouter();
  const [asking, setAsking] = useState(false);
  return (
    <>
      <label className="flex min-h-11 items-start justify-between gap-3 py-2.5">
        <span className="flex min-w-0 flex-col">
          <span className="text-ink font-semibold break-all">{label}</span>
          <span className="text-meta-lg text-muted">{hint}</span>
        </span>
        <input
          type="checkbox"
          role="switch"
          checked={on}
          disabled={disabled}
          onChange={() => setAsking(true)}
          className="accent-green mt-1 size-5 shrink-0"
        />
      </label>
      <ReasonDialog
        open={asking}
        title={`${on ? "Turn off" : "Turn on"} ${label}?`}
        confirm={on ? "Turn off" : "Turn on"}
        onClose={() => setAsking(false)}
        onSubmit={async (reason) => {
          await send(!on, reason);
          setAsking(false);
          router.refresh();
        }}
      />
    </>
  );
}

/** An automatic content rule. Rules only flag; they never block or change what users see. */
export function RuleSwitch({
  rule,
  on,
  canChange,
}: {
  rule: string;
  on: boolean;
  canChange: boolean;
}) {
  const words = CONTENT_RULES[rule] ?? { label: rule, hint: "", reason: "" };
  return (
    <ReasonSwitch
      label={words.label}
      hint={words.hint}
      on={on}
      disabled={!canChange}
      send={async (next, reason) => {
        await browserApi(`/admin/content/rules/${rule}`, noContentSchema, {
          method: "POST",
          body: { on: next, reason },
        });
      }}
    />
  );
}

/** Keep the flagged text, or remove it (the person gets a notice naming the rule). */
export function FlagActions({ flag }: { flag: Flag }) {
  const router = useRouter();
  const [decision, setDecision] = useState<"keep" | "remove" | null>(null);
  return (
    <>
      <div className="flex shrink-0 gap-2">
        <Button variant="outline" size="compact" onClick={() => setDecision("keep")}>
          Keep
        </Button>
        <Button variant="danger" size="compact" onClick={() => setDecision("remove")}>
          Remove
        </Button>
      </div>
      <ReasonDialog
        open={decision !== null}
        title={decision === "remove" ? "Remove this text?" : "Keep this text?"}
        confirm={decision === "remove" ? "Remove" : "Keep"}
        onClose={() => setDecision(null)}
        onSubmit={async (reason) => {
          await browserApi(`/admin/content/flags/${flag.id}/decide`, noContentSchema, {
            method: "POST",
            body: { decision, reason },
          });
          setDecision(null);
          router.refresh();
        }}
      >
        {decision === "remove" ? (
          <p className="text-meta-lg text-ink-2">
            The text is cleared and they get a short notice naming the rule.
          </p>
        ) : null}
      </ReasonDialog>
    </>
  );
}

/** Switch one AI provider on or off. */
export function ProviderSwitch({ name, role, on }: { name: string; role: string; on: boolean }) {
  return (
    <ReasonSwitch
      label={name}
      hint={role === "primary" ? "Primary" : "Fallback"}
      on={on}
      send={async (next, reason) => {
        await browserApi("/admin/ai/providers", noContentSchema, {
          method: "POST",
          body: { provider: name, on: next, reason },
        });
      }}
    />
  );
}

/** "Test the AI providers": queues the fixed-prompt test (no user data). */
export function ProbeButton() {
  const [state, setState] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="flex flex-col gap-1.5">
      <Button
        variant="outline"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await browserApi("/admin/ai/probe", probeQueuedSchema, { method: "POST" });
            setState("Test queued. Results show here within a minute; reload to see them.");
          } catch (caught) {
            setState(describeError(caught));
          } finally {
            setBusy(false);
          }
        }}
      >
        Test the AI providers
      </Button>
      <p role="status" className="text-meta text-muted min-h-5">
        {state}
      </p>
    </div>
  );
}

/** Re-run matching for one person, by email, in the background. */
export function RerunForm() {
  const [email, setEmail] = useState("");
  const [asking, setAsking] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  return (
    <>
      <form
        className="flex items-end gap-2"
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          event.preventDefault();
          if (email.trim()) setAsking(true);
        }}
      >
        <div className="min-w-0 flex-1">
          <Input
            label="Email"
            type="email"
            autoComplete="off"
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <Button type="submit" variant="ghost" size="compact" disabled={!email.trim()}>
          Re-run
        </Button>
      </form>
      <p role="status" className="text-meta text-muted min-h-5">
        {done}
      </p>
      <ReasonDialog
        open={asking}
        title={`Re-run matching for ${email.trim()}?`}
        confirm="Re-run"
        onClose={() => setAsking(false)}
        onSubmit={async (reason) => {
          await browserApi("/admin/ai/rerun", rerunQueuedSchema, {
            method: "POST",
            body: { email: email.trim(), reason },
          });
          setAsking(false);
          setDone("Queued. New matches appear for them in a minute or two.");
          setEmail("");
        }}
      >
        <p className="text-meta-lg text-ink-2">
          Their newest open request is matched again. At most 10 an hour.
        </p>
      </ReasonDialog>
    </>
  );
}
