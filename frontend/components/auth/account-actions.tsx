"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { textLinkClasses } from "@/components/ui/text-link";
import { browserApi } from "@/lib/api/browser";
import { deletionScheduledSchema, noContentSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

type Busy = "logout" | "logout-all" | "delete" | null;

const GRACE_DAYS = 30;

/** Sign out, sign out everywhere, and delete the account (after explicit confirmation). */
export function AccountActions() {
  const router = useRouter();
  const ids = useId();
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [understood, setUnderstood] = useState(false);
  const [deletedUntil, setDeletedUntil] = useState<string | null>(null);

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

  async function deleteAccount() {
    setBusy("delete");
    setError(null);
    try {
      const result = await browserApi("/me", deletionScheduledSchema, { method: "DELETE" });
      setDeletedUntil(
        new Date(result.deletion_scheduled_for).toLocaleDateString(undefined, {
          dateStyle: "long",
        }),
      );
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(null);
    }
  }

  if (deletedUntil) {
    return (
      <Card role="status" className="flex flex-col gap-3">
        <h2 className="text-section">Your account is scheduled for deletion</h2>
        <p>
          You have been signed out everywhere. Your account and all its data will be permanently
          deleted on <strong>{deletedUntil}</strong>. Until then, signing in is disabled.
        </p>
        <Link href="/" className={textLinkClasses()}>
          Go to the home page
        </Link>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {error ? (
        <p
          role="alert"
          className="rounded-why bg-coral-tint text-coral-ink px-4 py-3 font-semibold"
        >
          {error}
        </p>
      ) : null}

      <section aria-labelledby={`${ids}-sessions`} className="flex flex-col gap-3">
        <h2 id={`${ids}-sessions`} className="text-section">
          Sign out
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => signOut(false)} disabled={busy !== null}>
            {busy === "logout" ? "Signing out…" : "Sign out"}
          </Button>
          <Button onClick={() => signOut(true)} disabled={busy !== null}>
            {busy === "logout-all" ? "Signing out…" : "Sign out of all devices"}
          </Button>
        </div>
      </section>

      <section aria-labelledby={`${ids}-delete`} className="flex flex-col gap-3">
        <h2 id={`${ids}-delete`} className="text-section">
          Delete account
        </h2>
        {!confirmingDelete ? (
          <div>
            <Button tone="danger" onClick={() => setConfirmingDelete(true)}>
              Delete my account…
            </Button>
          </div>
        ) : (
          <div
            role="group"
            aria-label="Confirm account deletion"
            className="rounded-card border-coral-edge bg-coral-tint flex flex-col gap-4 border p-5"
          >
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
                className="accent-green-base mt-1 size-4 shrink-0"
              />
              <span>I understand that my account will be permanently deleted.</span>
            </label>
            <div className="flex flex-wrap gap-3">
              <Button tone="danger" onClick={deleteAccount} disabled={!understood || busy !== null}>
                {busy === "delete" ? "Deleting…" : "Delete my account"}
              </Button>
              <Button
                onClick={() => {
                  setConfirmingDelete(false);
                  setUnderstood(false);
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
