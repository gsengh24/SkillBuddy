"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { InlineError, Input, Textarea } from "@/components/ds/fields";
import { Button } from "@/components/ds/button";

import { browserApi } from "@/lib/api/browser";
import { profileSchema, type Profile } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";
import {
  ABOUT_MAX,
  ABOUT_MIN,
  LANGUAGES,
  LINK_PATTERN,
  MAX_LINKS,
  NAME_MAX,
  TIMEZONE_PATTERN,
} from "@/lib/profile/limits";

import { AiConsentText } from "./ai-consent";

type Mode = "onboarding" | "edit";

function browserTimezone(): string | null {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    // Same rule as the API; an unusual zone name is left out rather than failing the save.
    return zone && TIMEZONE_PATTERN.test(zone) ? zone : null;
  } catch {
    return null;
  }
}

/**
 * The "About you" form: name, free-text description, links and languages, plus the AI
 * consent line (required on the first save and whenever its version changes). Saving
 * returns at once; the description is read in the background.
 */
export function ProfileForm({ profile, mode }: { profile: Profile | null; mode: Mode }) {
  const router = useRouter();
  const ids = useId();
  const [name, setName] = useState(profile?.display_name ?? "");
  const [about, setAbout] = useState(profile?.about_text ?? "");
  const [links, setLinks] = useState<string[]>(() => {
    const existing = profile?.links ?? [];
    return [...existing, ...Array(MAX_LINKS).fill("")].slice(0, MAX_LINKS);
  });
  const [languages, setLanguages] = useState<string[]>(profile?.languages ?? []);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const needsConsent = !profile?.ai_consent_current;
  const errorId = `${ids}-error`;
  const aboutLength = about.trim().length;

  function toggleLanguage(code: string) {
    setLanguages((current) =>
      current.includes(code) ? current.filter((c) => c !== code) : [...current, code],
    );
  }

  function validate(): string | null {
    if (!name.trim()) return "Add the name you'd like matches to see.";
    if (aboutLength < ABOUT_MIN)
      return `Write at least ${ABOUT_MIN} characters about yourself, so we can find good matches.`;
    if (aboutLength > ABOUT_MAX) return `Keep your description under ${ABOUT_MAX} characters.`;
    const bad = links.map((l) => l.trim()).find((l) => l && !LINK_PATTERN.test(l));
    if (bad) return "Links must be full https:// addresses, like https://github.com/you.";
    if (needsConsent && !consent) return "To save, agree to how AI is used to find your matches.";
    return null;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await browserApi("/me/profile", profileSchema, {
        method: "PUT",
        body: {
          display_name: name.trim(),
          about_text: about.trim(),
          links: links.map((l) => l.trim()).filter(Boolean),
          languages,
          // Kept as saved, or taken from this device the first time.
          timezone: profile?.timezone ?? browserTimezone(),
          visibility: profile?.visibility ?? "matchable",
          ai_consent: needsConsent ? consent : false,
        },
      });
      if (mode === "onboarding") {
        setStatus("Saved. Reading your description…");
        router.push("/you?welcome=1");
      } else {
        setStatus("Saved.");
        setConsent(false);
        router.refresh();
      }
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
      <p role="status" aria-live="polite" className="sr-only">
        {status}
      </p>

      <Input
        id={`${ids}-name`}
        label="Your name"
        hint="Shown only to people you are introduced to. It is never sent to an AI."
        name="display_name"
        autoComplete="given-name"
        maxLength={NAME_MAX}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />

      <Textarea
        showCounter={false}
        id={`${ids}-about`}
        label="About you"
        hint={`What you're good at, what you'd like to learn or build, and when you're free. ${aboutLength}/${ABOUT_MAX} characters.`}
        name="about_text"
        rows={8}
        maxLength={ABOUT_MAX}
        value={about}
        onChange={(event) => setAbout(event.target.value)}
        placeholder="e.g. Second-year CSE. I build React apps and want a designer to make a small app with, a few hours on weekends. Also into chess."
      />

      <fieldset className="flex flex-col gap-3">
        <legend className="text-meta-lg text-ink mb-1 font-semibold">Links (optional)</legend>
        {links.map((link, index) => (
          <Input
            key={index}
            id={`${ids}-link-${index}`}
            label={`Link ${index + 1}`}
            hideLabel
            type="url"
            inputMode="url"
            placeholder="https://github.com/you"
            value={link}
            onChange={(event) =>
              setLinks((current) =>
                current.map((value, i) => (i === index ? event.target.value : value)),
              )
            }
          />
        ))}
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-meta-lg text-ink mb-1 font-semibold">Languages you speak</legend>
        <div className="flex flex-wrap gap-x-5">
          {LANGUAGES.map((language) => (
            <label key={language.code} className="flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                checked={languages.includes(language.code)}
                onChange={() => toggleLanguage(language.code)}
                className="accent-green size-4 shrink-0"
              />
              <span>{language.label}</span>
            </label>
          ))}
        </div>
        {profile?.timezone ? (
          <p className="text-meta-lg text-muted">Time zone: {profile.timezone}</p>
        ) : null}
      </fieldset>

      {needsConsent ? (
        <label className="bg-green-tint border-green-line rounded-card flex items-start gap-3 border p-4">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            className="accent-green mt-1 size-4 shrink-0"
          />
          <span className="text-meta-lg text-ink">
            <AiConsentText />
          </span>
        </label>
      ) : null}

      {error ? (
        <InlineError id={errorId} announce>
          {error}
        </InlineError>
      ) : null}

      <Button variant="outline" type="submit" disabled={submitting} className="self-start">
        {submitting ? "Saving…" : mode === "onboarding" ? "Save and continue" : "Save changes"}
      </Button>
    </form>
  );
}
