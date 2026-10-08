"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ds/button";
import { Input, Textarea } from "@/components/ds/fields";
import { SegmentedControl } from "@/components/ds/segmented-control";
import { cx } from "@/components/ui/cx";
import { adminBannerSchema, type AdminBanner, type EmailSend } from "@/lib/admin/schemas";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { BANNER_STYLES } from "@/lib/banner-styles";

import { ReasonDialog } from "./reason-dialog";

type Kind = AdminBanner["kind"];

const KINDS: { value: Kind; label: string }[] = [
  { value: "info", label: "Info" },
  { value: "warning", label: "Warning" },
  { value: "maintenance", label: "Maintenance" },
];

const MAX = 160;

/** Write a banner, see it as users will, and publish it with a reason. */
export function NewBanner() {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [kind, setKind] = useState<Kind>("info");
  const [endsAt, setEndsAt] = useState("");
  const [asking, setAsking] = useState(false);
  const text = message.trim();
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (text) setAsking(true);
      }}
    >
      <Textarea
        label="Message"
        hint={`${message.length} / ${MAX} characters. Plain text.`}
        rows={2}
        maxLength={MAX}
        value={message}
        onChange={(event) => setMessage(event.target.value)}
      />
      <div className="flex flex-col gap-1.5">
        <span className="text-small text-ink font-semibold">Type</span>
        <SegmentedControl label="Banner type" segments={KINDS} value={kind} onChange={setKind} />
      </div>
      <Input
        label="Ends (optional)"
        hint="Empty: until you end it."
        type="datetime-local"
        value={endsAt}
        onChange={(event) => setEndsAt(event.target.value)}
      />
      <div className="flex flex-col gap-1.5">
        <span className="text-small text-ink font-semibold">Preview</span>
        <p
          className={cx(
            "rounded-card text-meta-lg border px-3 py-2 break-words",
            BANNER_STYLES[kind],
          )}
        >
          {text || "Your message"}
        </p>
      </div>
      <Button type="submit" variant="primary" disabled={!text} className="self-start">
        Publish banner
      </Button>
      <ReasonDialog
        open={asking}
        title="Publish this banner?"
        confirm="Publish"
        onClose={() => setAsking(false)}
        onSubmit={async (reason) => {
          await browserApi("/admin/comms/banners", adminBannerSchema, {
            method: "POST",
            body: {
              message: text,
              kind,
              ends_at: endsAt ? new Date(endsAt).toISOString() : null,
              reason,
            },
          });
          setAsking(false);
          setMessage("");
          setEndsAt("");
          router.refresh();
        }}
      >
        <p className="text-meta-lg text-ink-2">Everyone sees it within a minute.</p>
      </ReasonDialog>
    </form>
  );
}

/** End a live banner now. */
export function EndBanner({ banner }: { banner: AdminBanner }) {
  const router = useRouter();
  const [asking, setAsking] = useState(false);
  return (
    <>
      <Button variant="ghost" size="compact" onClick={() => setAsking(true)}>
        End
      </Button>
      <ReasonDialog
        open={asking}
        title="End this banner?"
        confirm="End banner"
        onClose={() => setAsking(false)}
        onSubmit={async (reason) => {
          await browserApi(`/admin/comms/banners/${banner.id}/end`, noContentSchema, {
            method: "POST",
            body: { reason },
          });
          setAsking(false);
          router.refresh();
        }}
      />
    </>
  );
}

/** "Send test to me": a [Test] copy with made-up values, to your own address. */
export function SendTest({ templateKey }: { templateKey: string }) {
  const [state, setState] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <span className="flex flex-col items-end gap-0.5">
      <Button
        variant="ghost"
        size="compact"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await browserApi(`/admin/comms/templates/${templateKey}/test`, noContentSchema, {
              method: "POST",
            });
            setState("Sent to you");
          } catch (caught) {
            setState(describeError(caught));
          } finally {
            setBusy(false);
          }
        }}
      >
        Send test to me
      </Button>
      <span role="status" className="text-meta text-muted">
        {state}
      </span>
    </span>
  );
}

/** Retry a failed email (once). */
export function RetryEmail({ send }: { send: EmailSend }) {
  const router = useRouter();
  const [asking, setAsking] = useState(false);
  return (
    <>
      <Button variant="outline" size="compact" onClick={() => setAsking(true)}>
        Retry
      </Button>
      <ReasonDialog
        open={asking}
        title={`Retry the email to ${send.to}?`}
        confirm="Retry"
        onClose={() => setAsking(false)}
        onSubmit={async (reason) => {
          await browserApi(`/admin/comms/emails/${send.id}/retry`, noContentSchema, {
            method: "POST",
            body: { reason },
          });
          setAsking(false);
          router.refresh();
        }}
      />
    </>
  );
}
