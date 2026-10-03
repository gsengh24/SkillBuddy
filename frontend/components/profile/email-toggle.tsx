"use client";

import { useState } from "react";

import { browserApi } from "@/lib/api/browser";
import { profileSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

/** "Emails about intros": on by default; in-app notifications always stay. */
export function EmailToggle({ initial }: { initial: boolean }) {
  const [enabled, setEnabled] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onChange(checked: boolean) {
    if (saving) return;
    const previous = enabled;
    // Show the change at once; put it back if the save fails.
    setEnabled(checked);
    setSaving(true);
    setError(null);
    try {
      const saved = await browserApi("/me/profile", profileSchema, {
        method: "PATCH",
        body: { email_notifications: checked },
      });
      setEnabled(saved.email_notifications);
    } catch (caught) {
      setEnabled(previous);
      setError(describeError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="flex min-h-11 items-start gap-3">
        <input
          type="checkbox"
          role="switch"
          checked={enabled}
          aria-busy={saving}
          onChange={(event) => onChange(event.target.checked)}
          className="accent-green-base mt-1 size-4 shrink-0"
        />
        <span className="flex flex-col">
          <span className="text-ink font-semibold">Emails about intros</span>
          <span className="text-small text-muted">
            {enabled
              ? "We email you when someone sends you an intro or accepts yours."
              : "Off: we won't email you about intros. You'll still see them in Notifications."}
          </span>
        </span>
      </label>
      {error ? (
        <p role="alert" className="text-small text-coral-ink font-semibold">
          {error}
        </p>
      ) : null}
    </div>
  );
}
