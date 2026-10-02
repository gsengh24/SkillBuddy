"use client";

import { useEffect, useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Overline } from "@/components/ui/overline";
import { Tag } from "@/components/ui/tag";
import { TextField } from "@/components/ui/text-field";
import { browserApi } from "@/lib/api/browser";
import { profileSchema, type Profile, type Understanding } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import { MAX_PHRASES, PHRASE_MAX } from "@/lib/profile/limits";

const POLL_MS = 2000;
const MAX_POLLS = 45;

const SOURCE_NOTE: Record<NonNullable<Profile["parse_source"]>, string> = {
  llm: "Read by AI from your description.",
  template: "Read by our simple reader, because the AI was busy. You can correct it below.",
  user: "Edited by you.",
};

function toList(text: string): string[] {
  return text
    .split(",")
    .map((part) => part.trim().slice(0, PHRASE_MAX))
    .filter(Boolean)
    .slice(0, MAX_PHRASES);
}

function PhraseRow({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="flex flex-col gap-1.5">
      <dt className="text-small text-muted font-semibold">{label}</dt>
      <dd className="flex flex-wrap gap-2">
        {items.length ? (
          items.map((item) => <Tag key={item}>{item}</Tag>)
        ) : (
          <span className="text-small text-muted">Nothing yet</span>
        )}
      </dd>
    </div>
  );
}

/**
 * "Here's what we understood": waits for the background read of the description (polling
 * the profile), then shows the result and lets the person correct it.
 */
export function UnderstandingReview({ initial }: { initial: Profile }) {
  const ids = useId();
  const [profile, setProfile] = useState(initial);
  const [polls, setPolls] = useState(0);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<keyof Understanding, string>>({
    summary: "",
    offers: "",
    seeks: "",
    interests: "",
    availability: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const pending = profile.parse_status === "pending";
  const gaveUp = pending && polls >= MAX_POLLS;

  useEffect(() => {
    if (!pending || gaveUp) return;
    const timer = window.setTimeout(async () => {
      try {
        const latest = await browserApi("/me/profile", profileSchema);
        setProfile(latest);
        if (latest.parse_status === "parsed") setStatus("Your profile is ready to review.");
      } catch {
        // A failed poll is retried on the next tick.
      }
      setPolls((count) => count + 1);
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [pending, gaveUp, polls]);

  function startEditing(understanding: Understanding) {
    setDraft({
      summary: understanding.summary,
      offers: understanding.offers.join(", "),
      seeks: understanding.seeks.join(", "),
      interests: understanding.interests.join(", "),
      availability: understanding.availability,
    });
    setError(null);
    setEditing(true);
  }

  async function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const saved = await browserApi("/me/profile/understanding", profileSchema, {
        method: "PUT",
        body: {
          summary: draft.summary.trim().slice(0, 200),
          offers: toList(draft.offers),
          seeks: toList(draft.seeks),
          interests: toList(draft.interests),
          availability: draft.availability.trim().slice(0, 80),
        },
      });
      setProfile(saved);
      setEditing(false);
      setStatus("Saved your corrections.");
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setSaving(false);
    }
  }

  const understanding = profile.understanding;

  return (
    <Card className="flex flex-col gap-4" aria-labelledby={`${ids}-heading`} role="region">
      <p role="status" aria-live="polite" className="sr-only">
        {status}
      </p>
      <Overline tone="green">What we understood</Overline>
      <h2 id={`${ids}-heading`} className="text-section">
        {pending ? "Reading your description…" : "Here's how we'll describe you to the matcher"}
      </h2>

      {pending && !gaveUp ? (
        <p className="text-muted">This usually takes a few seconds. You can leave this page.</p>
      ) : null}
      {gaveUp ? (
        <p className="text-muted">
          This is taking longer than usual. Your profile is saved; come back in a few minutes.
        </p>
      ) : null}

      {understanding && !editing ? (
        <>
          {profile.parse_source ? (
            <p className="text-small text-muted">{SOURCE_NOTE[profile.parse_source]}</p>
          ) : null}
          {understanding.summary ? <p>{understanding.summary}</p> : null}
          <dl className="flex flex-col gap-4">
            <PhraseRow label="You offer" items={understanding.offers} />
            <PhraseRow label="You're looking for" items={understanding.seeks} />
            <PhraseRow label="Interests" items={understanding.interests} />
            <div className="flex flex-col gap-1.5">
              <dt className="text-small text-muted font-semibold">Availability</dt>
              <dd>{understanding.availability || "Not mentioned"}</dd>
            </div>
          </dl>
          <Button type="button" className="self-start" onClick={() => startEditing(understanding)}>
            Correct this
          </Button>
        </>
      ) : null}

      {understanding && editing ? (
        <form noValidate onSubmit={onSave} className="flex flex-col gap-5">
          <TextField
            label="Summary"
            maxLength={200}
            value={draft.summary}
            onChange={(e) => setDraft({ ...draft, summary: e.target.value })}
          />
          <TextField
            label="You offer"
            hint="Separate with commas."
            value={draft.offers}
            onChange={(e) => setDraft({ ...draft, offers: e.target.value })}
          />
          <TextField
            label="You're looking for"
            hint="Separate with commas."
            value={draft.seeks}
            onChange={(e) => setDraft({ ...draft, seeks: e.target.value })}
          />
          <TextField
            label="Interests"
            hint="Separate with commas."
            value={draft.interests}
            onChange={(e) => setDraft({ ...draft, interests: e.target.value })}
          />
          <TextField
            label="Availability"
            maxLength={80}
            value={draft.availability}
            onChange={(e) => setDraft({ ...draft, availability: e.target.value })}
          />
          {error ? (
            <p
              role="alert"
              className="rounded-why bg-coral-tint text-small text-coral-ink px-4 py-3 font-semibold"
            >
              {error}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save corrections"}
            </Button>
            <Button type="button" onClick={() => setEditing(false)} disabled={saving}>
              Cancel
            </Button>
          </div>
        </form>
      ) : null}
    </Card>
  );
}
