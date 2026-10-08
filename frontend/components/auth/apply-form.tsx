"use client";

import { useId, useState, type FormEvent } from "react";

import { Select } from "@/components/ds/fields";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/text-field";
import { browserApi } from "@/lib/api/browser";
import { applicationReceivedSchema } from "@/lib/api/schemas";
import { APPLICATION_SOURCES } from "@/lib/auth/application-sources";
import { describeError } from "@/lib/auth/messages";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/**
 * Apply to join while signups are invite only (A5). The answer is the same for every
 * address; nothing is emailed until an admin approves the application.
 */
export function ApplyForm() {
  const ids = useId();
  const [email, setEmail] = useState("");
  const [source, setSource] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!EMAIL_PATTERN.test(email.trim())) {
      setError("Enter a valid email address, like name@example.com.");
      return;
    }
    if (!source) {
      setError("Choose how you heard about us.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await browserApi("/auth/applications", applicationReceivedSchema, {
        method: "POST",
        body: { email: email.trim(), source },
      });
      setSent(true);
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-labelledby={`${ids}-heading`} className="flex flex-col gap-4">
      <h2 id={`${ids}-heading`} className="text-title-lg">
        No invite code? Apply to join
      </h2>
      {sent ? (
        <p role="status" className="text-muted">
          Thanks. If your application is approved, we&apos;ll email you an invite.
        </p>
      ) : (
        <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
          <TextField
            id={`${ids}-email`}
            label="Email address"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Select
            id={`${ids}-source`}
            label="How did you hear about us?"
            value={source}
            onChange={(event) => setSource(event.target.value)}
          >
            <option value="" disabled>
              Choose one
            </option>
            {APPLICATION_SOURCES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
          {error ? (
            <p
              role="alert"
              className="rounded-why bg-coral-tint text-small text-coral-ink px-4 py-3 font-semibold"
            >
              {error}
            </p>
          ) : null}
          <Button type="submit" disabled={submitting} className="self-start">
            {submitting ? "Sending…" : "Apply to join"}
          </Button>
        </form>
      )}
    </section>
  );
}
