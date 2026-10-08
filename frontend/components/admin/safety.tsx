"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ds/button";
import { Select } from "@/components/ds/fields";
import { appealSchema, queueItemSchema, type Case } from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";

import { ReasonDialog } from "./reason-dialog";

const DECISIONS = [
  { value: "dismiss", label: "Dismiss" },
  { value: "warn", label: "Warn" },
  { value: "suspend", label: "Suspend for 7 days" },
  { value: "ban", label: "Ban" },
] as const;

function when(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "";
}

/**
 * A case (reference-admin.html, Reports and safety): who, why, the messages the reporter
 * attached, and both people's history counts. No other message text, no chat view.
 */
export function CaseDrawer({
  found,
  permissions,
  closeHref,
}: {
  found: Case;
  permissions: string[];
  closeHref: string;
}) {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const [deciding, setDeciding] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [decision, setDecision] = useState<(typeof DECISIONS)[number]["value"]>("dismiss");
  const report = found.report;
  const canHandle = permissions.includes("handle_reports") && report.status !== "resolved";

  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
  }, []);

  async function post(path: string, body: object) {
    await browserApi(`/admin/safety/reports/${report.id}/${path}`, queueItemSchema, {
      method: "POST",
      body,
    });
    setDeciding(false);
    setReviewing(false);
    router.refresh();
  }

  const history = (title: string, counts: Record<string, number>) => (
    <div className="bg-panel border-line rounded-card border px-3 py-2">
      <p className="text-mono text-muted mb-1 font-mono uppercase">{title}</p>
      <dl className="text-meta-lg grid grid-cols-[1fr_auto] gap-x-3">
        {Object.entries(counts).map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="text-ink-2">{key.replaceAll("_", " ")}</dt>
            <dd className="font-mono">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );

  return (
    <dialog
      ref={dialog}
      aria-labelledby="case-h"
      onCancel={(event) => {
        event.preventDefault();
        router.push(closeHref, { scroll: false });
      }}
      className="border-line bg-bg backdrop:bg-ink/40 fixed inset-y-0 right-0 left-auto m-0 flex h-full max-h-none w-full max-w-[560px] flex-col border-l p-0"
    >
      <div className="border-line flex items-center gap-3 border-b px-4 py-3.5">
        <h2
          id="case-h"
          className="font-display tracking-display min-w-0 flex-1 truncate text-[18px] font-extrabold"
        >
          Report: {report.reason}
        </h2>
        <Link
          href={closeHref}
          scroll={false}
          className="text-meta-lg text-ink rounded-control hover:bg-panel inline-flex min-h-11 items-center px-3 font-medium"
        >
          Close
        </Link>
      </div>
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        <dl className="text-meta-lg grid grid-cols-[120px_1fr] gap-x-3 gap-y-2">
          <dt className="text-muted">Reported</dt>
          <dd className="break-all">
            {report.reported ? `${report.reported.email} (${report.reported.status})` : "Deleted"}
          </dd>
          <dt className="text-muted">Reporter</dt>
          <dd className="break-all">{report.reporter?.email ?? "Deleted"}</dd>
          <dt className="text-muted">What</dt>
          <dd>{report.target}</dd>
          <dt className="text-muted">Filed</dt>
          <dd suppressHydrationWarning>{when(report.created_at)}</dd>
          <dt className="text-muted">Status</dt>
          <dd>
            {report.status.replace("_", " ")}
            {report.decision ? ` · ${report.decision}` : ""}
          </dd>
        </dl>

        {found.details ? (
          <section aria-labelledby="details-h">
            <h3 id="details-h" className="text-mono text-muted mb-1 font-mono uppercase">
              What the reporter wrote
            </h3>
            <p className="text-meta-lg whitespace-pre-wrap">{found.details}</p>
          </section>
        ) : null}

        <section aria-labelledby="attached-h" className="flex flex-col gap-1.5">
          <h3 id="attached-h" className="text-mono text-muted font-mono uppercase">
            Attached by the reporter
          </h3>
          {found.attached.length ? (
            <ul className="flex flex-col gap-1.5">
              {found.attached.map((item, index) => (
                <li
                  key={`${item.sent_at}-${index}`}
                  className="bg-panel border-line rounded-card border px-3 py-2"
                >
                  <span className="text-muted block font-mono text-[10px]" suppressHydrationWarning>
                    {item.label ?? item.sender} {item.sent_at ? `· ${when(item.sent_at)}` : ""}
                  </span>
                  <span className="text-meta-lg whitespace-pre-wrap">{item.body}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-meta text-muted">Nothing attached.</p>
          )}
        </section>

        <div className="grid gap-2 sm:grid-cols-2">
          {history("Reported person", found.reported_history)}
          {history("Reporter", found.reporter_history)}
        </div>

        {found.resolution_note ? (
          <p className="text-meta-lg text-ink-2">Decision note: {found.resolution_note}</p>
        ) : null}

        {canHandle ? (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Actions">
            {report.status === "open" ? (
              <Button variant="outline" size="compact" onClick={() => setReviewing(true)}>
                Start review
              </Button>
            ) : null}
            <Button variant="primary" size="compact" onClick={() => setDeciding(true)}>
              Decide
            </Button>
          </div>
        ) : null}
      </div>

      <ReasonDialog
        open={reviewing}
        title="Start review"
        confirm="Start review"
        onClose={() => setReviewing(false)}
        onSubmit={(reason) => post("start-review", { reason })}
      />
      <ReasonDialog
        open={deciding}
        title="Decide this report"
        confirm="Record decision"
        onClose={() => setDeciding(false)}
        onSubmit={(reason) => post("decide", { decision, reason })}
      >
        <Select
          label="Decision"
          value={decision}
          onChange={(event) =>
            setDecision(event.target.value as (typeof DECISIONS)[number]["value"])
          }
        >
          {DECISIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        <p className="text-meta text-muted">
          The reporter is told the report was reviewed. A warning, suspension or ban is emailed to
          the reported person.
        </p>
      </ReasonDialog>
    </dialog>
  );
}

/** Uphold or overturn one appeal. */
export function AppealActions({ appealId }: { appealId: string }) {
  const router = useRouter();
  const [outcome, setOutcome] = useState<"uphold" | "overturn" | null>(null);
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="compact" onClick={() => setOutcome("uphold")}>
          Uphold
        </Button>
        <Button variant="outline" size="compact" onClick={() => setOutcome("overturn")}>
          Overturn
        </Button>
      </div>
      <ReasonDialog
        open={outcome !== null}
        title={outcome === "overturn" ? "Overturn and lift it" : "Uphold the decision"}
        confirm={outcome === "overturn" ? "Overturn" : "Uphold"}
        onClose={() => setOutcome(null)}
        onSubmit={async (reason) => {
          await browserApi(`/admin/safety/appeals/${appealId}/decide`, appealSchema, {
            method: "POST",
            body: { outcome, reason },
          });
          setOutcome(null);
          router.refresh();
        }}
      />
    </>
  );
}
