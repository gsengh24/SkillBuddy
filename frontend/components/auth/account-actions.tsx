"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { Dialog } from "@/components/ds/dialog";
import { InlineError, Input } from "@/components/ds/fields";
import { Panel } from "@/components/ds/surfaces";
import { Button } from "@/components/ds/button";
import { textLinkClasses } from "@/components/ui/text-link";
import { browserApi } from "@/lib/api/browser";
import { deletionScheduledSchema, noContentSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

const GRACE_DAYS = 30;
/** Typed to confirm deleting, as well as the "I understand" box (design spec section 13). */
const CONFIRM_WORD = "DELETE";

/** Sign out of this device, or of every device. */
export function SignOutActions() {
  const router = useRouter();
  const [busy, setBusy] = useState<"logout" | "logout-all" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function signOut(everywhere: boolean) {
    setBusy(everywhere ? "logout-all" : "logout");
    setError(null);
    try {
      await browserApi(everywhere ? "/auth/logout-all" : "/auth/logout", noContentSchema, {
        method: "POST",
      });
      router.replace("/login");
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => signOut(false)} disabled={busy !== null}>
          {busy === "logout" ? "Signing out…" : "Sign out"}
        </Button>
        <Button variant="outline" onClick={() => signOut(true)} disabled={busy !== null}>
          {busy === "logout-all" ? "Signing out…" : "Sign out of all devices"}
        </Button>
      </div>
    </div>
  );
}

/**
 * Delete the account: a dialog with the grace-period explanation, the "I understand" box
 * and DELETE typed. Afterwards it says when the account goes for good.
 */
export function DeleteAccount() {
  const ids = useId();
  const [open, setOpen] = useState(false);
  const [understood, setUnderstood] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletedUntil, setDeletedUntil] = useState<string | null>(null);

  function close() {
    setOpen(false);
    setUnderstood(false);
    setTyped("");
    setError(null);
  }

  async function deleteAccount() {
    setBusy(true);
    setError(null);
    try {
      const result = await browserApi("/me", deletionScheduledSchema, { method: "DELETE" });
      setDeletedUntil(
        new Date(result.deletion_scheduled_for).toLocaleDateString(undefined, {
          dateStyle: "long",
        }),
      );
      setOpen(false);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  if (deletedUntil) {
    return (
      <Panel role="status" className="flex flex-col gap-3">
        <h3 className="font-display tracking-display text-[20px] leading-tight font-extrabold">
          Your account is scheduled for deletion
        </h3>
        <p>
          You have been signed out everywhere. Your account and all its data will be permanently
          deleted on <strong>{deletedUntil}</strong>. Until then, signing in is disabled.
        </p>
        <Link href="/" className={textLinkClasses()}>
          Go to the home page
        </Link>
      </Panel>
    );
  }

  return (
    <>
      <Button variant="danger" size="compact" onClick={() => setOpen(true)}>
        Delete my account…
      </Button>
      <Dialog open={open} onClose={close} title="Delete account">
        <div role="group" aria-label="Confirm account deletion" className="flex flex-col gap-4">
          <p>
            Your account will be scheduled for permanent deletion in{" "}
            <strong>{GRACE_DAYS} days</strong>. You will be signed out on every device right away
            and won&apos;t be able to sign in during those {GRACE_DAYS} days. After that, your
            account and everything in it are deleted for good and cannot be recovered.
          </p>
          <label className="flex min-h-11 items-start gap-3">
            <input
              type="checkbox"
              checked={understood}
              onChange={(event) => setUnderstood(event.target.checked)}
              className="accent-green mt-1 size-4 shrink-0"
            />
            <span>I understand that my account will be permanently deleted.</span>
          </label>
          <Input
            id={`${ids}-confirm`}
            label={`Type ${CONFIRM_WORD} to confirm`}
            autoComplete="off"
            spellCheck={false}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
          />
          {error ? <InlineError announce>{error}</InlineError> : null}
          <div className="flex flex-wrap justify-end gap-3">
            <Button variant="outline" onClick={close}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={deleteAccount}
              disabled={!understood || typed !== CONFIRM_WORD || busy}
            >
              {busy ? "Deleting…" : "Delete my account"}
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  );
}
