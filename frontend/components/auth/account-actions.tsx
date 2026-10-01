"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

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
      <div
        role="status"
        className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5"
      >
        <h2 className="text-lg font-semibold text-slate-900">
          Your account is scheduled for deletion
        </h2>
        <p className="text-slate-700">
          You have been signed out everywhere. Your account and all its data will be permanently
          deleted on <strong>{deletedUntil}</strong>. Until then, signing in is disabled.
        </p>
        <Link href="/" className="text-indigo-700 underline">
          Go to the home page
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {error ? (
        <p role="alert" className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {error}
        </p>
      ) : null}

      <section aria-labelledby={`${ids}-sessions`} className="flex flex-col gap-3">
        <h2 id={`${ids}-sessions`} className="text-lg font-semibold text-slate-900">
          Sign out
        </h2>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => signOut(false)}
            disabled={busy !== null}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
          >
            {busy === "logout" ? "Signing out…" : "Sign out"}
          </button>
          <button
            type="button"
            onClick={() => signOut(true)}
            disabled={busy !== null}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
          >
            {busy === "logout-all" ? "Signing out…" : "Sign out of all devices"}
          </button>
        </div>
      </section>

      <section aria-labelledby={`${ids}-delete`} className="flex flex-col gap-3">
        <h2 id={`${ids}-delete`} className="text-lg font-semibold text-slate-900">
          Delete account
        </h2>
        {!confirmingDelete ? (
          <div>
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              className="rounded-md border border-rose-300 bg-white px-4 py-2 font-medium text-rose-700 hover:bg-rose-50"
            >
              Delete my account…
            </button>
          </div>
        ) : (
          <div
            role="group"
            aria-label="Confirm account deletion"
            className="flex flex-col gap-4 rounded-lg border border-rose-200 bg-rose-50 p-5"
          >
            <p className="text-slate-800">
              Your account will be scheduled for permanent deletion in{" "}
              <strong>{GRACE_DAYS} days</strong>. You will be signed out on every device right away
              and won&apos;t be able to sign in during those {GRACE_DAYS} days. After that, your
              account and everything in it are deleted for good and cannot be recovered.
            </p>
            <label className="flex items-start gap-3 text-slate-800">
              <input
                type="checkbox"
                checked={understood}
                onChange={(event) => setUnderstood(event.target.checked)}
                className="mt-1 size-4"
              />
              <span>I understand that my account will be permanently deleted.</span>
            </label>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={deleteAccount}
                disabled={!understood || busy !== null}
                className="rounded-md bg-rose-600 px-4 py-2 font-semibold text-white hover:bg-rose-700 disabled:opacity-60"
              >
                {busy === "delete" ? "Deleting…" : "Delete my account"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmingDelete(false);
                  setUnderstood(false);
                }}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 font-medium text-slate-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
