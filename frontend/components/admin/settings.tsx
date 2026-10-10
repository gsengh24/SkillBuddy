"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ds/button";
import { Input } from "@/components/ds/fields";
import type { LimitState } from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema } from "@/lib/api/schemas";

import { ReasonDialog } from "./reason-dialog";

const FEATURES: Record<string, { label: string; hint: string }> = {
  intro_requests: { label: "Intro requests", hint: "Users can send intros" },
  chats: { label: "Chats", hint: "Users can message after an intro is accepted" },
  ai_matching: {
    label: "AI matching",
    hint: "Use AI to suggest matches. Off: the rule-based matcher is used instead",
  },
  pair_spaces: { label: "Pair spaces", hint: "Shared goal spaces for two people" },
  teams: { label: "Teams", hint: "Groups of up to six. Off until reporting for teams is ready" },
  email_notifications: {
    label: "Email notifications",
    hint: "Intro emails. Sign-in codes are always sent",
  },
};

const LIMITS: Record<string, string> = {
  match_requests_per_day: "Requests per day",
  intros_per_day: "Intros per day",
  max_pending_intros: "Pending intros at once",
  message_max_length: "Max message length",
};

/** One feature switch. Turning it on or off asks for a reason first. */
export function FeatureSwitch({ feature, on }: { feature: string; on: boolean }) {
  const router = useRouter();
  const [asking, setAsking] = useState(false);
  const { label, hint } = FEATURES[feature] ?? { label: feature, hint: "" };
  return (
    <>
      <label className="flex min-h-11 items-start justify-between gap-3 py-2.5">
        <span className="flex flex-col">
          <span className="text-ink font-semibold">{label}</span>
          <span className="text-meta-lg text-muted">{hint}</span>
        </span>
        <input
          type="checkbox"
          role="switch"
          checked={on}
          onChange={() => setAsking(true)}
          className="accent-green mt-1 size-5 shrink-0"
        />
      </label>
      <ReasonDialog
        open={asking}
        title={`${on ? "Turn off" : "Turn on"} ${label}?`}
        confirm={on ? "Turn off" : "Turn on"}
        onClose={() => setAsking(false)}
        onSubmit={async (reason) => {
          await browserApi(`/admin/settings/features/${feature}`, noContentSchema, {
            method: "POST",
            body: { on: !on, reason },
          });
          setAsking(false);
          router.refresh();
        }}
      >
        <p className="text-meta-lg text-ink-2">
          {on ? "Users lose this feature within a minute." : "Takes effect within a minute."}
        </p>
      </ReasonDialog>
    </>
  );
}

/** One limit: a number field, saved with a reason. */
export function LimitField({ limit }: { limit: LimitState }) {
  const router = useRouter();
  const [value, setValue] = useState(String(limit.value));
  const [asking, setAsking] = useState(false);
  const label = LIMITS[limit.key] ?? limit.key;
  const parsed = Number(value);
  const valid =
    value.trim() !== "" &&
    Number.isInteger(parsed) &&
    parsed >= limit.minimum &&
    parsed <= limit.maximum;
  return (
    <>
      <form
        className="flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (valid && parsed !== limit.value) setAsking(true);
        }}
      >
        <div className="min-w-0 flex-1">
          <Input
            label={label}
            hint={`${limit.minimum} to ${limit.maximum}. Default ${limit.default}.`}
            type="number"
            inputMode="numeric"
            min={limit.minimum}
            max={limit.maximum}
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </div>
        <Button
          type="submit"
          variant="ghost"
          size="compact"
          disabled={!valid || parsed === limit.value}
        >
          Save
        </Button>
      </form>
      <ReasonDialog
        open={asking}
        title={`Set ${label.toLowerCase()} to ${parsed}?`}
        confirm="Save limit"
        onClose={() => setAsking(false)}
        onSubmit={async (reason) => {
          await browserApi(`/admin/settings/limits/${limit.key}`, noContentSchema, {
            method: "POST",
            body: { value: parsed, reason },
          });
          setAsking(false);
          router.refresh();
        }}
      >
        <p className="text-meta-lg text-ink-2">Applies to everyone within a minute.</p>
      </ReasonDialog>
    </>
  );
}
