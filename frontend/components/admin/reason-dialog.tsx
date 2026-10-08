"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ds/button";
import { Dialog } from "@/components/ds/dialog";
import { InlineError, Textarea } from "@/components/ds/fields";
import { describeError } from "@/lib/auth/messages";

const REASON_MIN = 10;

/** Every admin change asks for a reason (at least 10 characters), kept in the audit log. */
export function ReasonDialog({
  open,
  title,
  onClose,
  onSubmit,
  children,
  confirm,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  onSubmit: (reason: string) => Promise<void>;
  children?: ReactNode;
  confirm: string;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(reason.trim());
      setReason("");
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        {children}
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
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            disabled={busy || reason.trim().length < REASON_MIN}
          >
            {busy ? "Saving…" : confirm}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
