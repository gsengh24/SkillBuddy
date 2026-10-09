"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { Dialog } from "@/components/ds/dialog";
import { InlineError, Textarea } from "@/components/ds/fields";
import { STATUS_LABELS, noteSchema, type UserDetail } from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

const REASON_MIN = 10;

type Action = {
  path: string;
  label: string;
  permission: string;
  danger?: boolean;
  shows: (user: UserDetail) => boolean;
};

const ACTIONS: Action[] = [
  {
    path: "suspend",
    label: "Suspend for 7 days",
    permission: "suspend_users",
    danger: true,
    shows: (u) => u.status === "active" || u.status === "paused",
  },
  {
    path: "unsuspend",
    label: "Lift suspension",
    permission: "suspend_users",
    shows: (u) => u.status === "suspended",
  },
  {
    path: "ban",
    label: "Ban",
    permission: "suspend_users",
    danger: true,
    shows: (u) => u.status !== "banned" && u.status !== "pending_deletion",
  },
  {
    path: "unban",
    label: "Reverse ban",
    permission: "suspend_users",
    shows: (u) => u.status === "banned",
  },
  {
    path: "sign-out",
    label: "Sign out everywhere",
    permission: "suspend_users",
    shows: () => true,
  },
  {
    path: "clear-bio",
    label: "Clear about text",
    permission: "suspend_users",
    danger: true,
    shows: (u) => Boolean(u.profile?.about_text),
  },
  {
    path: "schedule-deletion",
    label: "Schedule deletion",
    permission: "delete_data",
    danger: true,
    shows: (u) => u.status !== "pending_deletion",
  },
];

function when(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "Never";
}

/** One action, behind a dialog that asks for the reason the audit log records. */
function ActionButton({ userId, action }: { userId: string; action: Action }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await browserApi(`/admin/users/${userId}/${action.path}`, noContentSchema, {
        method: "POST",
        body: { reason: reason.trim() },
      });
      setOpen(false);
      setReason("");
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button
        variant={action.danger ? "danger" : "outline"}
        size="compact"
        onClick={() => setOpen(true)}
      >
        {action.label}
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} title={action.label}>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <Textarea
            label="Reason (recorded in the audit log)"
            hint={`At least ${REASON_MIN} characters.`}
            rows={3}
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          {error ? <InlineError announce>{error}</InlineError> : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              variant={action.danger ? "danger" : "primary"}
              type="submit"
              disabled={busy || reason.trim().length < REASON_MIN}
            >
              {busy ? "Saving…" : "Confirm"}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}

function AddNote({ userId }: { userId: string }) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await browserApi(`/admin/users/${userId}/notes`, noteSchema, {
        method: "POST",
        body: { body: body.trim() },
      });
      setBody("");
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <Textarea
        label="Add a private note"
        hint="Only admins see notes."
        rows={2}
        maxLength={1000}
        value={body}
        onChange={(event) => setBody(event.target.value)}
      />
      {error ? <InlineError announce>{error}</InlineError> : null}
      <Button
        variant="outline"
        size="compact"
        type="submit"
        disabled={busy || !body.trim()}
        className="self-start"
      >
        {busy ? "Saving…" : "Add note"}
      </Button>
    </form>
  );
}

/**
 * A user's detail as a drawer over the list (reference-admin.html). Actions show only for
 * roles that have their permission; the API checks the same on every call.
 */
export function UserDrawer({
  user,
  permissions,
  closeHref,
}: {
  user: UserDetail;
  permissions: string[];
  closeHref: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const router = useRouter();
  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
  }, []);
  const actions = ACTIONS.filter((a) => permissions.includes(a.permission) && a.shows(user));
  const canNote = permissions.includes("suspend_users");
  const name = user.profile?.display_name || user.email;

  return (
    <dialog
      ref={dialog}
      aria-labelledby="user-drawer-h"
      onCancel={(event) => {
        // Escape: go back to the list (the URL decides whether the drawer is open).
        event.preventDefault();
        router.push(closeHref, { scroll: false });
      }}
      className="border-line bg-bg backdrop:bg-ink/40 fixed inset-y-0 right-0 left-auto m-0 flex h-full max-h-none w-full max-w-[560px] flex-col border-l p-0"
    >
      <div className="border-line flex items-center gap-3 border-b px-4 py-3.5">
        <h2
          id="user-drawer-h"
          className="font-display tracking-display min-w-0 flex-1 truncate text-[18px] font-extrabold"
        >
          {name}
        </h2>
        <Link
          href={closeHref}
          scroll={false}
          className="text-meta-lg text-ink rounded-control hover:bg-panel inline-flex min-h-11 items-center px-3 font-medium"
        >
          Close
        </Link>
      </div>
      <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-4">
        <dl className="text-meta-lg grid grid-cols-[130px_1fr] gap-x-3 gap-y-2">
          <dt className="text-muted">Email</dt>
          <dd className="break-all">{user.email}</dd>
          <dt className="text-muted">Status</dt>
          <dd>
            {STATUS_LABELS[user.status]}
            {user.suspended_until ? ` until ${when(user.suspended_until)}` : ""}
            {user.deletion_scheduled_for ? ` on ${when(user.deletion_scheduled_for)}` : ""}
          </dd>
          <dt className="text-muted">Email verified</dt>
          <dd suppressHydrationWarning>
            {user.email_verified_at ? when(user.email_verified_at) : "Not yet"}
          </dd>
          {user.profile?.city ? (
            <>
              <dt className="text-muted">City</dt>
              <dd>{user.profile.city}</dd>
            </>
          ) : null}
          <dt className="text-muted">Signs in with</dt>
          <dd>{user.sign_in_methods.join(", ") || "Not yet"}</dd>
          <dt className="text-muted">Joined</dt>
          <dd suppressHydrationWarning>{when(user.created_at)}</dd>
          <dt className="text-muted">Last sign-in</dt>
          <dd suppressHydrationWarning>{when(user.last_login_at)}</dd>
          {Object.entries(user.counts).map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-muted">{key.replaceAll("_", " ")}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>

        {actions.length ? (
          <div className="flex flex-wrap gap-2" aria-label="Actions" role="group">
            {actions.map((action) => (
              <ActionButton key={action.path} userId={user.id} action={action} />
            ))}
          </div>
        ) : null}

        {user.profile ? (
          <section aria-labelledby="profile-h" className="flex flex-col gap-1.5">
            <h3 id="profile-h" className="text-mono text-muted font-mono uppercase">
              Profile
            </h3>
            {user.profile.headline ? (
              <p className="font-semibold">{user.profile.headline}</p>
            ) : null}
            <p className="text-meta-lg text-ink-2 whitespace-pre-wrap">
              {user.profile.about_text || "No about text."}
            </p>
          </section>
        ) : null}

        <section aria-labelledby="timeline-h" className="flex flex-col gap-1.5">
          <h3 id="timeline-h" className="text-mono text-muted font-mono uppercase">
            Timeline
          </h3>
          <ol className="border-line flex flex-col gap-2 border-l pl-3">
            {user.timeline.map((item, index) => (
              <li key={`${item.at}-${index}`} className="text-meta-lg">
                <span className="font-mono text-[12px]">{item.event}</span>
                <span className="text-muted block font-mono text-[11px]" suppressHydrationWarning>
                  {when(item.at)}
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="notes-h" className="flex flex-col gap-2">
          <h3 id="notes-h" className="text-mono text-muted font-mono uppercase">
            Notes
          </h3>
          {user.notes.length ? (
            <ul className="flex flex-col gap-1.5">
              {user.notes.map((note) => (
                <li key={note.id} className="bg-panel border-line rounded-card border px-3 py-2">
                  <span className="text-muted block font-mono text-[10px]" suppressHydrationWarning>
                    {when(note.created_at)}
                  </span>
                  <span className="text-meta-lg whitespace-pre-wrap">{note.body}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-meta text-muted">No notes yet.</p>
          )}
          {canNote ? <AddNote userId={user.id} /> : null}
        </section>
      </div>
    </dialog>
  );
}
