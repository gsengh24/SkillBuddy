"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ds/button";
import { Input } from "@/components/ds/fields";
import { SegmentedControl } from "@/components/ds/segmented-control";
import {
  accessSchema,
  domainSchema,
  inviteCodeSchema,
  invitedSchema,
  type Application,
  type InviteCode,
  type SignupMode,
} from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema } from "@/lib/api/schemas";

import { ReasonDialog } from "./reason-dialog";

const MODES: { value: SignupMode; label: string; hint: string }[] = [
  { value: "open", label: "Open", hint: "Anyone can sign up." },
  {
    value: "invite_only",
    label: "Invite only",
    hint: "New users need a valid invite code or an approved application.",
  },
  {
    value: "closed",
    label: "Closed",
    hint: "Nobody new can join. Existing users can still sign in.",
  },
];

export function modeHint(mode: SignupMode): string {
  return MODES.find((item) => item.value === mode)?.hint ?? "";
}

/** Open, invite only or closed. A change asks for a reason first. */
export function ModeSwitch({ mode }: { mode: SignupMode }) {
  const router = useRouter();
  const [next, setNext] = useState<SignupMode | null>(null);
  const label = MODES.find((item) => item.value === next)?.label ?? "";
  return (
    <>
      <SegmentedControl
        label="Signup mode"
        segments={MODES.map(({ value, label: text }) => ({ value, label: text }))}
        value={mode}
        onChange={(value) => (value === mode ? undefined : setNext(value))}
        className="max-w-md"
      />
      <p className="text-meta-lg text-ink-2 mt-2.5">{modeHint(mode)}</p>
      <ReasonDialog
        open={next !== null}
        title={`Change signup mode to ${label}?`}
        confirm="Change mode"
        onClose={() => setNext(null)}
        onSubmit={async (reason) => {
          await browserApi("/admin/access/mode", accessSchema, {
            method: "POST",
            body: { mode: next, reason },
          });
          setNext(null);
          router.refresh();
        }}
      >
        <p className="text-meta-lg text-ink-2">
          {next ? modeHint(next) : ""} Applies to the next sign-up. Existing users are not affected.
        </p>
      </ReasonDialog>
    </>
  );
}

/** Approve or reject one application. */
export function ApplicationActions({ application }: { application: Application }) {
  const router = useRouter();
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);
  return (
    <>
      <div className="flex shrink-0 gap-2">
        <Button variant="outline" size="compact" onClick={() => setDecision("approve")}>
          Approve
        </Button>
        <Button variant="ghost" size="compact" onClick={() => setDecision("reject")}>
          Reject
        </Button>
      </div>
      <ReasonDialog
        open={decision !== null}
        title={`${decision === "approve" ? "Approve" : "Reject"} ${application.email}?`}
        confirm={decision === "approve" ? "Approve" : "Reject"}
        onClose={() => setDecision(null)}
        onSubmit={async (reason) => {
          await browserApi(`/admin/access/applications/${application.id}/decide`, noContentSchema, {
            method: "POST",
            body: { decision, reason },
          });
          setDecision(null);
          router.refresh();
        }}
      >
        {decision === "approve" ? (
          <p className="text-meta-lg text-ink-2">
            They can create an account with this address, and we email them a one-use invite code
            that works for 14 days.
          </p>
        ) : null}
      </ReasonDialog>
    </>
  );
}

/** Approve the 10 oldest applications. */
export function InviteNext({ waitlist }: { waitlist: number }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  return (
    <>
      <Button variant="outline" disabled={waitlist === 0} onClick={() => setOpen(true)}>
        Invite next 10
      </Button>
      <p role="status" className="text-meta text-muted min-h-5">
        {done}
      </p>
      <ReasonDialog
        open={open}
        title="Invite the next 10?"
        confirm="Invite"
        onClose={() => setOpen(false)}
        onSubmit={async (reason) => {
          const { invited } = await browserApi(
            "/admin/access/applications/invite-next",
            invitedSchema,
            { method: "POST", body: { reason } },
          );
          setOpen(false);
          setDone(`${invited} ${invited === 1 ? "invite" : "invites"} queued.`);
          router.refresh();
        }}
      >
        <p className="text-meta-lg text-ink-2">
          Approves the oldest applications in the queue and emails each an invite.
        </p>
      </ReasonDialog>
    </>
  );
}

/** A shareable code with a use limit and an optional expiry. */
export function CreateCode() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [limit, setLimit] = useState("25");
  const [days, setDays] = useState("30");
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        Create code
      </Button>
      <ReasonDialog
        open={open}
        title="Create an invite code"
        confirm="Create code"
        onClose={() => setOpen(false)}
        onSubmit={async (reason) => {
          await browserApi("/admin/access/codes", inviteCodeSchema, {
            method: "POST",
            body: {
              code: code.trim() || null,
              max_uses: Number(limit),
              expires_in_days: days.trim() ? Number(days) : null,
              reason,
            },
          });
          setOpen(false);
          setCode("");
          router.refresh();
        }}
      >
        <Input
          label="Code (optional)"
          hint="Letters, digits and hyphens, like CYN-FRIENDS. Leave empty to generate one."
          maxLength={32}
          autoCapitalize="characters"
          spellCheck={false}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          className="font-mono uppercase"
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Use limit"
            type="number"
            inputMode="numeric"
            min={1}
            max={10000}
            required
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
          />
          <Input
            label="Expires in (days)"
            hint="Empty: never."
            type="number"
            inputMode="numeric"
            min={1}
            max={365}
            value={days}
            onChange={(event) => setDays(event.target.value)}
          />
        </div>
      </ReasonDialog>
    </>
  );
}

/** Stop a code working; people who already joined with it are not affected. */
export function RevokeCode({ code }: { code: InviteCode }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="danger" size="compact" onClick={() => setOpen(true)}>
        Revoke
      </Button>
      <ReasonDialog
        open={open}
        title={`Revoke ${code.code}?`}
        confirm="Revoke"
        onClose={() => setOpen(false)}
        onSubmit={async (reason) => {
          await browserApi(`/admin/access/codes/${code.id}/revoke`, noContentSchema, {
            method: "POST",
            body: { reason },
          });
          setOpen(false);
          router.refresh();
        }}
      >
        <p className="text-meta-lg text-ink-2">
          The code stops working. People already in are not affected.
        </p>
      </ReasonDialog>
    </>
  );
}

/** Allowed or blocked email domains, as removable chips with an add field. */
export function DomainList({
  kind,
  domains,
  placeholder,
}: {
  kind: "allowed" | "blocked";
  domains: string[];
  placeholder: string;
}) {
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [change, setChange] = useState<{ action: "add" | "remove"; domain: string } | null>(null);
  const listName = kind === "allowed" ? "allowed" : "blocked";
  return (
    <>
      {domains.length ? (
        <ul className="flex flex-wrap gap-1.5" aria-label={`${listName} domains`}>
          {domains.map((domain) => (
            <li
              key={domain}
              className={
                kind === "blocked"
                  ? "rounded-chip border-danger text-danger inline-flex items-center gap-1 border py-0.5 pr-0.5 pl-2 font-mono text-[12px]"
                  : "rounded-chip border-line text-ink inline-flex items-center gap-1 border py-0.5 pr-0.5 pl-2 font-mono text-[12px]"
              }
            >
              {domain}
              <button
                type="button"
                aria-label={`Remove ${domain}`}
                onClick={() => setChange({ action: "remove", domain })}
                className="hover:bg-panel inline-flex size-11 items-center justify-center rounded-full pointer-fine:size-7"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-meta text-muted">None</p>
      )}
      <form
        className="mt-2.5 flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.trim()) setChange({ action: "add", domain: draft.trim() });
        }}
      >
        <div className="min-w-0 flex-1">
          <Input
            label={`Add ${listName} domain`}
            hideLabel
            placeholder={placeholder}
            maxLength={254}
            spellCheck={false}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </div>
        <Button type="submit" variant="ghost" size="compact" disabled={!draft.trim()}>
          Add
        </Button>
      </form>
      <ReasonDialog
        open={change !== null}
        title={
          change?.action === "add"
            ? `Add ${change.domain} to the ${listName} list?`
            : `Remove ${change?.domain ?? ""} from the ${listName} list?`
        }
        confirm={change?.action === "add" ? "Add" : "Remove"}
        onClose={() => setChange(null)}
        onSubmit={async (reason) => {
          if (!change) return;
          if (change.action === "add") {
            await browserApi(`/admin/access/domains/${kind}`, domainSchema, {
              method: "POST",
              body: { domain: change.domain, reason },
            });
            setDraft("");
          } else {
            await browserApi(`/admin/access/domains/${kind}/remove`, noContentSchema, {
              method: "POST",
              body: { domain: change.domain, reason },
            });
          }
          setChange(null);
          router.refresh();
        }}
      >
        <p className="text-meta-lg text-ink-2">Applies to new accounts only.</p>
      </ReasonDialog>
    </>
  );
}
