"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ds/button";
import { InlineError } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import {
  dataExportSchema,
  noContentSchema,
  userSchema,
  type DataExport,
  type DeviceSession,
  type User,
} from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

function when(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** Signed-in devices: sign out one, or every device but this one. */
export function DeviceList({ initial }: { initial: DeviceSession[] }) {
  const [devices, setDevices] = useState(initial);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const others = devices.filter((device) => !device.current);

  async function signOut(id: string | "others") {
    setBusy(id);
    setError(null);
    try {
      if (id === "others") {
        await browserApi("/auth/logout-others", noContentSchema, { method: "POST" });
        setDevices((current) => current.filter((device) => device.current));
      } else {
        await browserApi(`/auth/sessions/${id}`, noContentSchema, { method: "DELETE" });
        setDevices((current) => current.filter((device) => device.id !== id));
      }
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <p className="text-mono text-muted font-mono uppercase">Signed-in devices</p>
      <ul aria-label="Signed-in devices" className="divide-line flex flex-col divide-y">
        {devices.map((device) => (
          <li key={device.id} className="flex items-center justify-between gap-3 py-3">
            <div>
              <p className="font-semibold">{device.device}</p>
              <p className="text-meta text-muted" suppressHydrationWarning>
                {device.current ? "Active now" : `Last active ${when(device.last_seen_at)}`}
              </p>
            </div>
            {device.current ? (
              <span className="text-mono text-green font-mono uppercase">This device</span>
            ) : (
              <Button
                variant="ghost"
                size="compact"
                aria-label={`Sign out ${device.device}, last active ${when(device.last_seen_at)}`}
                disabled={busy !== null}
                onClick={() => signOut(device.id)}
              >
                {busy === device.id ? "Signing out…" : "Sign out"}
              </Button>
            )}
          </li>
        ))}
      </ul>
      {others.length ? (
        <div>
          <Button
            variant="outline"
            size="compact"
            disabled={busy !== null}
            onClick={() => signOut("others")}
          >
            {busy === "others" ? "Signing out…" : "Sign out of all other devices"}
          </Button>
        </div>
      ) : null}
      {error ? <InlineError announce>{error}</InlineError> : null}
    </div>
  );
}

function exportStatus(item: DataExport | undefined): string | null {
  if (!item) return null;
  switch (item.status) {
    case "requested":
      return "We're putting your file together. We'll email you a link soon.";
    case "ready":
      return item.expires_at
        ? `We emailed you a link. It works until ${new Date(item.expires_at).toLocaleString(
            undefined,
            { dateStyle: "medium", timeStyle: "short" },
          )}.`
        : "We emailed you a link.";
    case "expired":
      return "Your last link has expired. You can ask for a new one.";
    case "failed":
      return "We couldn't send your last file. Please ask again.";
  }
}

/** "Download my data": ask for the file; a link arrives by email. */
export function DataDownload({ initial }: { initial: DataExport[] }) {
  const [latest, setLatest] = useState<DataExport | undefined>(initial[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const waiting = latest?.status === "requested";

  async function request() {
    setBusy(true);
    setError(null);
    try {
      setLatest(await browserApi("/me/data-exports", dataExportSchema, { method: "POST" }));
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  const status = exportStatus(latest);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold">Download my data</p>
          <p className="text-meta text-muted">
            A file with your profile, requests, intros, connections and messages. We email you a
            link.
          </p>
        </div>
        <Button
          variant="outline"
          size="compact"
          disabled={busy || waiting}
          onClick={request}
          className="shrink-0"
        >
          {busy ? "Asking…" : waiting ? "Requested" : "Request"}
        </Button>
      </div>
      {status ? (
        <p role="status" className="text-meta-lg text-ink-2" suppressHydrationWarning>
          {status}
        </p>
      ) : null}
      {error ? <InlineError announce>{error}</InlineError> : null}
    </div>
  );
}

/** Pause or resume the account. */
export function PauseAccount({ initial }: { initial: User["status"] }) {
  const router = useRouter();
  const [status, setStatus] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const paused = status === "paused";

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      const user = await browserApi(paused ? "/me/resume" : "/me/pause", userSchema, {
        method: "POST",
      });
      setStatus(user.status);
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold">{paused ? "Your account is paused" : "Pause my account"}</p>
          <p className="text-meta text-muted">
            {paused
              ? "You're hidden from matching and new intros. Your chats carry on."
              : "Hides you from matching and new intros. Your chats stay. Come back any time."}
          </p>
        </div>
        <Button
          variant={paused ? "outline" : "danger"}
          size="compact"
          disabled={busy}
          onClick={toggle}
          className="shrink-0"
        >
          {busy ? "Saving…" : paused ? "Resume" : "Pause"}
        </Button>
      </div>
      {error ? <InlineError announce>{error}</InlineError> : null}
    </div>
  );
}
