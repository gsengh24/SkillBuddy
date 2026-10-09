"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { Dialog } from "@/components/ds/dialog";
import { InlineError, Input, Select, Textarea } from "@/components/ds/fields";
import { auditPageSchema, type AuditEntry, teamMemberSchema } from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

const REASON_MIN = 10;

function ReasonField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Textarea
      label="Reason (recorded in the audit log)"
      hint={`At least ${REASON_MIN} characters.`}
      rows={3}
      maxLength={500}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

/** Owners only: give someone with an account an admin role. */
export function InviteAdmin() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("moderator");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await browserApi("/admin/team", teamMemberSchema, {
        method: "POST",
        body: { email: email.trim(), role, reason: reason.trim() },
      });
      setOpen(false);
      setEmail("");
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
      <Button variant="primary" onClick={() => setOpen(true)}>
        Invite admin
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Invite an admin"
        description="They need an account already. They set up two-step login the first time they open the admin portal."
      >
        <form onSubmit={submit} className="flex flex-col gap-3">
          <Input
            label="Email"
            type="email"
            autoComplete="off"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Select label="Role" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="admin">Admin</option>
            <option value="moderator">Moderator</option>
            <option value="readonly">Read-only</option>
          </Select>
          <ReasonField value={reason} onChange={setReason} />
          {error ? <InlineError announce>{error}</InlineError> : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              disabled={busy || !email.trim() || reason.trim().length < REASON_MIN}
            >
              {busy ? "Saving…" : "Give the role"}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}

/** Owners only: take an admin role away (not from owners, who are set on the server). */
export function RemoveAdmin({ userId, email }: { userId: string; email: string }) {
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
      await browserApi(`/admin/team/${userId}/remove`, noContentSchema, {
        method: "POST",
        body: { reason: reason.trim() },
      });
      setOpen(false);
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
        variant="danger"
        size="compact"
        aria-label={`Remove ${email} from the admins`}
        onClick={() => setOpen(true)}
      >
        Remove
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Remove admin"
        description={`${email} loses their admin role, their two-step set-up and any admin session.`}
      >
        <form onSubmit={submit} className="flex flex-col gap-3">
          <ReasonField value={reason} onChange={setReason} />
          {error ? <InlineError announce>{error}</InlineError> : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              type="submit"
              disabled={busy || reason.trim().length < REASON_MIN}
            >
              {busy ? "Removing…" : "Remove admin"}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

// The API matches each of these exactly (they are the indexed columns).
const AUDIT_FILTERS = {
  action: "Action",
  target_id: "Target ID",
  actor_id: "Admin ID",
} as const;
type AuditFilter = keyof typeof AUDIT_FILTERS;

function auditPath(filter: AuditFilter, value: string, cursor: string | null): `/${string}` {
  const params = new URLSearchParams({ limit: "50" });
  if (value) params.set(filter, value);
  if (cursor) params.set("cursor", cursor);
  return `/admin/audit?${params.toString()}`;
}

/** The audit log, newest first, 50 at a time, with an exact-match filter. Plain text only. */
export function AuditLog({
  initial,
  initialCursor,
}: {
  initial: AuditEntry[];
  initialCursor: string | null;
}) {
  const [items, setItems] = useState(initial);
  const [cursor, setCursor] = useState(initialCursor);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<AuditFilter>("action");
  const [draft, setDraft] = useState("");
  // The value the list on screen was fetched with; "Show older entries" keeps using it.
  const [applied, setApplied] = useState("");

  async function load(value: string, from: string | null) {
    setBusy(true);
    setError(null);
    try {
      const page = await browserApi(auditPath(filter, value, from), auditPageSchema);
      setItems((current) => (from ? [...current, ...page.items] : page.items));
      setCursor(page.next_cursor);
      setApplied(value);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void load(draft.trim(), null);
  }

  return (
    <div className="flex flex-col">
      <form onSubmit={apply} role="search" className="mb-2 flex flex-wrap items-end gap-2">
        <Select
          label="Filter by"
          value={filter}
          onChange={(event) => setFilter(event.target.value as AuditFilter)}
        >
          {Object.entries(AUDIT_FILTERS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        <div className="min-w-[180px] flex-1">
          <Input
            label="Exactly"
            autoComplete="off"
            maxLength={64}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </div>
        <Button variant="outline" type="submit" disabled={busy || (!draft.trim() && !applied)}>
          {draft.trim() || !applied ? "Filter" : "Clear filter"}
        </Button>
      </form>
      {items.length ? null : (
        <p className="text-muted p-7 text-center">
          {applied ? "No entries match." : "Nothing recorded yet."}
        </p>
      )}
      <ul aria-label="Audit log" className="divide-line flex flex-col divide-y">
        {items.map((entry) => (
          <li key={entry.id} className="flex flex-col gap-0.5 py-3">
            <p className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="font-mono text-[13px]">{entry.action}</span>
              <time
                dateTime={entry.created_at}
                className="text-mono text-muted font-mono"
                suppressHydrationWarning
              >
                {when(entry.created_at)}
              </time>
            </p>
            <p className="text-meta text-muted">
              {entry.actor_role ?? "system"}
              {entry.target_type ? ` · ${entry.target_type} ${entry.target_id ?? ""}` : ""}
              {entry.ip ? ` · ${entry.ip}` : ""}
            </p>
            {entry.reason ? <p className="text-meta-lg text-ink-2">{entry.reason}</p> : null}
          </li>
        ))}
      </ul>
      {error ? <InlineError announce>{error}</InlineError> : null}
      {cursor ? (
        <Button
          variant="outline"
          size="compact"
          onClick={() => load(applied, cursor)}
          disabled={busy}
          className="mt-3 self-start"
        >
          {busy ? "Loading…" : "Show older entries"}
        </Button>
      ) : null}
    </div>
  );
}
