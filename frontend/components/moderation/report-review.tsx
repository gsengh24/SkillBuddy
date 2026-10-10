"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError, Textarea } from "@/components/ds/fields";
import { Panel, TopicChip } from "@/components/ds/surfaces";
import { Button } from "@/components/ds/button";
import { cx } from "@/components/ui/cx";

import { browserApi } from "@/lib/api/browser";
import {
  moderationAccountSchema,
  moderationReportSchema,
  type ModerationReport,
} from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { REPORT_DETAILS_MAX_LENGTH, REPORT_REASONS } from "@/lib/safety/reasons";

const WHAT: Record<ModerationReport["target"], string> = {
  message: "Chat message",
  intro: "Intro",
  profile: "Profile",
  goal: "Goal",
  progress_log: "Progress note",
  team: "Team",
  team_message: "Team chat message",
};

const PART: Record<string, string> = {
  request: "What they asked for",
  note: "Their note",
  name: "Name",
  links: "Links",
  summary: "Summary",
  offers: "Offers",
  seeks: "Looking for",
  interests: "Interests",
  availability: "Availability",
  goal: "Goal",
  due: "Due",
};

function when(iso: string | null) {
  return iso
    ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : null;
}

/** One report: the copy the reporter's report kept, and the moderator's two actions. */
export function ReportReview({ report }: { report: ModerationReport }) {
  const router = useRouter();
  const [action, setAction] = useState<"resolve" | "suspend" | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reason = REPORT_REASONS.find((option) => option.value === report.reason)?.label;
  const open = report.status === "open";
  const canSuspend = report.reported_id !== null && report.reported_status === "active";

  async function run() {
    setBusy(true);
    setError(null);
    try {
      if (action === "resolve") {
        await browserApi(`/moderation/reports/${report.id}/resolve`, moderationReportSchema, {
          method: "POST",
          body: { note: note.trim() },
        });
      } else if (action === "suspend" && report.reported_id) {
        await browserApi(
          `/moderation/accounts/${report.reported_id}/suspend`,
          moderationAccountSchema,
          { method: "POST", body: { note: note.trim(), report_id: report.id } },
        );
      }
      setAction(null);
      setNote("");
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <TopicChip>{reason ?? report.reason}</TopicChip>
        <TopicChip tone="soft">{WHAT[report.target]}</TopicChip>
        {report.reported_status === "suspended" ? (
          <TopicChip tone="soft">Account suspended</TopicChip>
        ) : null}
        {report.reported_id === null ? <TopicChip tone="soft">Account deleted</TopicChip> : null}
        <time
          dateTime={report.created_at}
          suppressHydrationWarning
          className="text-meta-lg text-muted"
        >
          Reported {when(report.created_at)}
        </time>
      </div>
      {report.details ? (
        <p>
          <span className="text-ink font-semibold">Reporter&apos;s note: </span>
          {report.details}
        </p>
      ) : null}

      <ol aria-label="Copy of what was reported" className="flex flex-col gap-2">
        {report.messages.map((part, index) => {
          const reported = part.sender === "reported";
          const last = report.target === "message" && index === report.messages.length - 1;
          return (
            <li
              key={`${part.id ?? part.label ?? "part"}-${index}`}
              className={cx(
                "rounded-card border px-4 py-2",
                reported ? "border-danger bg-bg" : "border-line bg-panel",
                last && "ring-danger ring-1",
              )}
            >
              <p className="text-meta-lg text-muted">
                {part.label
                  ? (PART[part.label] ?? part.label)
                  : reported
                    ? "Reported person"
                    : "Reporter"}
                {part.sent_at ? (
                  <time dateTime={part.sent_at} suppressHydrationWarning>
                    {" · "}
                    {when(part.sent_at)}
                  </time>
                ) : null}
                {last ? " · the reported message" : null}
              </p>
              <p className="text-ink break-words whitespace-pre-wrap">{part.body}</p>
            </li>
          );
        })}
      </ol>

      {!open ? (
        <p className="text-meta-lg text-muted">
          Resolved {when(report.resolved_at)}
          {report.resolution_note ? `: ${report.resolution_note}` : ""}
        </p>
      ) : null}

      {open && action === null ? (
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={() => setAction("resolve")}>
            Resolve
          </Button>
          {canSuspend ? (
            <Button variant="danger" onClick={() => setAction("suspend")}>
              Suspend this account
            </Button>
          ) : null}
        </div>
      ) : null}

      {action ? (
        <div className="border-line rounded-card flex flex-col gap-3 border p-4">
          {action === "suspend" ? (
            <p className="text-meta-lg">
              <strong className="text-ink">Suspend this account?</strong> They are signed out at
              once and can&apos;t sign in. People can&apos;t message them and they won&apos;t be
              shown in matches. You can unsuspend later under Suspended accounts. The report stays
              open until you resolve it.
            </p>
          ) : (
            <p className="text-meta-lg">
              Resolving closes this report. It and its copy are deleted 180 days later.
            </p>
          )}
          <Textarea
            showCounter={false}
            label="Note for your records (optional)"
            rows={2}
            maxLength={REPORT_DETAILS_MAX_LENGTH}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            error={error}
          />
          <div className="flex flex-wrap gap-3">
            <Button
              variant={action === "suspend" ? "danger" : "primary"}
              disabled={busy}
              onClick={run}
            >
              {busy ? "Saving…" : action === "suspend" ? "Suspend" : "Resolve"}
            </Button>
            <Button variant="outline" disabled={busy} onClick={() => setAction(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

/** Make a suspended account active again. */
export function UnsuspendButton({ userId }: { userId: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await browserApi(`/moderation/accounts/${userId}/unsuspend`, moderationAccountSchema, {
        method: "POST",
        body: {},
      });
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  if (!confirming)
    return (
      <Button variant="outline" onClick={() => setConfirming(true)}>
        Unsuspend
      </Button>
    );
  return (
    <div className="flex flex-col gap-3">
      <p className="text-meta-lg">They can sign in again and be matched and messaged.</p>
      {error ? <InlineError announce>{error}</InlineError> : null}
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" disabled={busy} onClick={confirm}>
          {busy ? "Saving…" : "Unsuspend"}
        </Button>
        <Button variant="outline" disabled={busy} onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
