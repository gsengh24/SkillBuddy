"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { InlineError, Input } from "@/components/ds/fields";
import { adminSessionSchema, twoStepSetupSchema } from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";
import { describeError } from "@/lib/auth/messages";

type Stage = "start" | "scan" | "codes";

/**
 * The admin portal's second step (ADR 0015). The first time: get a key for an
 * authenticator app, confirm a first code, and keep the recovery codes shown once. After
 * that: a code from the app, or one recovery code.
 */
export function TwoStepForm({ enabled }: { enabled: boolean }) {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("start");
  const [secret, setSecret] = useState<string | null>(null);
  const [uri, setUri] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function startSetup() {
    setBusy(true);
    setError(null);
    try {
      const setup = await browserApi("/admin/two-step/setup", twoStepSetupSchema, {
        method: "POST",
      });
      setSecret(setup.secret);
      setUri(setup.otpauth_uri);
      setStage("scan");
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await browserApi(
        enabled ? "/admin/two-step/verify" : "/admin/two-step/confirm",
        adminSessionSchema,
        { method: "POST", body: { code: code.trim() } },
      );
      if (result.recovery_codes?.length) {
        setCodes(result.recovery_codes);
        setStage("codes");
      } else {
        router.replace("/admin");
        router.refresh();
      }
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  if (stage === "codes") {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-ink-2">
          Two-step login is on. These recovery codes each work once if you lose your phone. They are
          shown only now: save them somewhere safe.
        </p>
        <ul
          aria-label="Recovery codes"
          className="bg-panel border-line rounded-card grid grid-cols-2 gap-2 border p-4 font-mono"
        >
          {codes.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <Button
          variant="primary"
          className="self-start"
          onClick={() => {
            router.replace("/admin");
            router.refresh();
          }}
        >
          I&apos;ve saved them
        </Button>
      </div>
    );
  }

  const codeForm = (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Input
        label={enabled ? "Code from your authenticator app" : "First code from the app"}
        hint={enabled ? "Or one of your recovery codes." : undefined}
        inputMode={enabled ? "text" : "numeric"}
        autoComplete="one-time-code"
        maxLength={20}
        value={code}
        onChange={(event) => setCode(event.target.value)}
      />
      {error ? <InlineError announce>{error}</InlineError> : null}
      <Button
        variant="primary"
        type="submit"
        disabled={busy || !code.trim()}
        className="self-start"
      >
        {busy ? "Checking…" : enabled ? "Continue" : "Turn on two-step login"}
      </Button>
    </form>
  );

  if (enabled) return codeForm;

  if (stage === "start") {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-ink-2">
          Every admin needs two-step login. You&apos;ll need an authenticator app such as Google
          Authenticator, Microsoft Authenticator or 1Password.
        </p>
        {error ? <InlineError announce>{error}</InlineError> : null}
        <Button variant="primary" onClick={startSetup} disabled={busy} className="self-start">
          {busy ? "Starting…" : "Set up two-step login"}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-ink-2">
        Add this key to your authenticator app (choose &ldquo;enter a setup key&rdquo;), or open the
        link on the phone that has the app. Then type the 6-digit code it shows.
      </p>
      <p className="bg-panel border-line rounded-card border p-4 font-mono break-all">
        {secret?.match(/.{1,4}/g)?.join(" ")}
      </p>
      {uri ? (
        <a href={uri} className="text-green text-meta-lg self-start font-medium underline">
          Open in authenticator app
        </a>
      ) : null}
      {codeForm}
    </div>
  );
}
