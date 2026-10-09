"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ds/button";
import { adminExportSchema } from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

import { ReasonDialog } from "./reason-dialog";

/** Run the waiting export, or delete the account now, with a reason. */
export function ProcessRequest({
  kind,
  id,
  email,
}: {
  kind: "export" | "deletion";
  id: string;
  email: string;
}) {
  const router = useRouter();
  const [asking, setAsking] = useState(false);
  const deletion = kind === "deletion";
  return (
    <>
      <Button
        variant={deletion ? "danger" : "outline"}
        size="compact"
        onClick={() => setAsking(true)}
      >
        Process
      </Button>
      <ReasonDialog
        open={asking}
        title={deletion ? `Delete ${email} now?` : `Send ${email} their data now?`}
        confirm={deletion ? "Delete permanently" : "Build and email"}
        onClose={() => setAsking(false)}
        onSubmit={async (reason) => {
          await browserApi(
            deletion ? `/admin/data/deletions/${id}/process` : `/admin/data/exports/${id}/process`,
            noContentSchema,
            { method: "POST", body: { reason } },
          );
          setAsking(false);
          router.refresh();
        }}
      >
        <p className="text-meta-lg text-ink-2">
          {deletion
            ? "The account and everything in it are deleted now instead of at the end of the grace period. This can't be undone."
            : "The file is built in the background and the link is emailed to them."}
        </p>
      </ReasonDialog>
    </>
  );
}

/**
 * Start a CSV export; it is built in the background. Away from the Data page,
 * ``doneHref`` links to where the file appears.
 */
export function StartCsv({
  kind,
  label,
  doneHref,
}: {
  kind: "users" | "audit";
  label: string;
  doneHref?: string;
}) {
  const router = useRouter();
  const [state, setState] = useState<string | null>(null);
  const [queued, setQueued] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <span className="flex flex-col gap-0.5">
      <Button
        variant="outline"
        size="compact"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await browserApi(`/admin/data/csv/${kind}`, adminExportSchema, { method: "POST" });
            setQueued(true);
            setState(
              doneHref
                ? "Queued. Ready in a minute or two."
                : "Queued. Reload in a minute to download.",
            );
            router.refresh();
          } catch (caught) {
            setState(describeError(caught));
          } finally {
            setBusy(false);
          }
        }}
      >
        {label}
      </Button>
      <span role="status" className="text-meta text-muted min-h-5">
        {state}
        {queued && doneHref ? (
          <>
            {" "}
            <Link href={doneHref} className="text-green font-medium underline">
              Download it from Data and compliance
            </Link>
          </>
        ) : null}
      </span>
    </span>
  );
}
