"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { cx } from "@/components/ui/cx";
import { textLinkClasses } from "@/components/ui/text-link";
import { browserApi } from "@/lib/api/browser";
import { ApiError } from "@/lib/api/errors";
import { googleStartSchema, otpRequestResponseSchema, userSchema } from "@/lib/api/schemas";
import { RESEND_COOLDOWN_SECONDS } from "@/lib/auth/constants";
import { describeError } from "@/lib/auth/messages";

import { AppealForm } from "./appeal-form";
import { brand } from "@/lib/brand";

import { GoogleButton } from "./google-button";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const EMAIL_MAX_LENGTH = 254;
const CONSENT_MESSAGE = "To continue, confirm that you are 18 or older and accept the terms.";

const INPUT =
  "h-11 w-full rounded-lg border border-line-strong bg-bg/60 px-3 text-body text-ink placeholder:text-muted focus:border-green focus:outline-none aria-invalid:border-coral-ink";
const PRIMARY =
  "bg-mint text-mint-text hover:bg-green-hover inline-flex h-11 w-full items-center justify-center rounded-lg text-[15px] font-semibold disabled:cursor-not-allowed disabled:opacity-60";

type Step = "email" | "code";

type LoginFormProps = {
  nextPath: string;
  /** Set when the API offers Google sign-in (ADR 0011): the domains it accepts. */
  google?: { domains: string[] };
  /** A message to show at once, e.g. after Google sign-in sent the person back. */
  initialError?: string | null;
  /** Signups are invite only (A5): show the invite code field. */
  inviteOnly?: boolean;
};

/**
 * Two-step passwordless sign-in: (1) email plus age and terms confirmation, (2) the 6-digit
 * code from the email. With Google enabled, "Continue with Google" comes first and the email
 * code stays below it as the fallback. Uses native form controls, labelled fields, and
 * announces errors (role="alert") and progress (role="status") to assistive technology.
 * The code step draws six boxes over one real input, so paste and autofill still work.
 */
export function LoginForm({
  nextPath,
  google,
  initialError = null,
  inviteOnly = false,
}: LoginFormProps) {
  const router = useRouter();
  const ids = useId();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [code, setCode] = useState("");
  const [codeFocused, setCodeFocused] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(initialError);
  const [appealToken, setAppealToken] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resendAt, setResendAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const codeInput = useRef<HTMLInputElement>(null);
  const emailInput = useRef<HTMLInputElement>(null);

  // Sent only when signups are invite only; ignored for existing accounts.
  const invite = () => (inviteOnly && inviteCode.trim() ? inviteCode.trim() : undefined);

  const secondsUntilResend = Math.max(0, Math.ceil((resendAt - now) / 1000));
  const errorId = `${ids}-error`;

  useEffect(() => {
    if (step !== "code") return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [step]);

  useEffect(() => {
    if (step === "code") codeInput.current?.focus();
    else emailInput.current?.focus();
  }, [step]);

  async function sendCode(): Promise<boolean> {
    setSubmitting(true);
    setError(null);
    try {
      await browserApi("/auth/otp/request", otpRequestResponseSchema, {
        method: "POST",
        body: { email: email.trim() },
      });
      const sentAt = Date.now();
      setNow(sentAt);
      setResendAt(sentAt + RESEND_COOLDOWN_SECONDS * 1000);
      return true;
    } catch (caught) {
      setError(describeError(caught));
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  async function onEmailSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = email.trim();
    if (!EMAIL_PATTERN.test(trimmed) || trimmed.length > EMAIL_MAX_LENGTH) {
      setError("Enter a valid email address, like name@example.com.");
      return;
    }
    if (!ageConfirmed || !acceptTerms) {
      setError(CONSENT_MESSAGE);
      return;
    }
    if (await sendCode()) {
      setCode("");
      setStep("code");
      setStatus(`We sent a 6-digit code to ${trimmed}. It expires in 10 minutes.`);
    }
  }

  async function onGoogle() {
    if (!ageConfirmed || !acceptTerms) {
      setError(CONSENT_MESSAGE);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const { authorization_url } = await browserApi("/auth/google/start", googleStartSchema, {
        method: "POST",
        body: {
          age_confirmed: ageConfirmed,
          accept_terms: acceptTerms,
          next: nextPath,
          invite_code: invite(),
        },
      });
      setStatus("Taking you to Google…");
      window.location.assign(authorization_url);
    } catch (caught) {
      setError(describeError(caught));
      setSubmitting(false);
    }
  }

  async function onResend() {
    if (await sendCode()) setStatus(`We sent a new code to ${email.trim()}.`);
  }

  async function onCodeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError("Enter the 6-digit code from the email.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await browserApi("/auth/otp/verify", userSchema, {
        method: "POST",
        body: {
          email: email.trim(),
          code,
          age_confirmed: ageConfirmed,
          accept_terms: acceptTerms,
          invite_code: invite(),
        },
      });
      setStatus("You're signed in. Taking you there now…");
      router.replace(nextPath);
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
      if (caught instanceof ApiError && caught.code === "code_locked") setCode("");
      // A suspended or banned account may appeal once (A3).
      const token =
        caught instanceof ApiError ? caught.body?.error.details?.[0]?.appeal_token : undefined;
      setAppealToken(typeof token === "string" ? token : null);
      setSubmitting(false);
      codeInput.current?.focus();
    }
  }

  function useDifferentEmail() {
    setStep("email");
    setCode("");
    setError(null);
    setStatus(null);
  }

  const errorMessage = error ? (
    <p
      id={errorId}
      role="alert"
      className="rounded-why bg-coral-tint text-small text-coral-ink px-4 py-3 font-semibold"
    >
      {error}
    </p>
  ) : null;
  const appealForm = appealToken ? <AppealForm token={appealToken} /> : null;
  const inviteField = inviteOnly ? (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={`${ids}-invite`} className="text-small text-ink font-medium">
        Invite code (optional)
      </label>
      <input
        id={`${ids}-invite`}
        name="invite_code"
        autoComplete="off"
        autoCapitalize="characters"
        spellCheck={false}
        maxLength={32}
        value={inviteCode}
        onChange={(event) => setInviteCode(event.target.value)}
        className={cx(INPUT, "font-mono uppercase")}
      />
      <p className="text-small text-muted">Not needed if your application was approved.</p>
    </div>
  ) : null;

  const consent = (
    <fieldset className="flex flex-col gap-1">
      <legend className="sr-only">Confirmations</legend>
      <label className="flex min-h-9 items-center gap-3 text-[14px]">
        <input
          type="checkbox"
          checked={ageConfirmed}
          onChange={(event) => setAgeConfirmed(event.target.checked)}
          className="accent-green size-4 shrink-0"
        />
        <span>I am 18 or older.</span>
      </label>
      <label className="flex min-h-9 items-center gap-3 text-[14px]">
        <input
          type="checkbox"
          checked={acceptTerms}
          onChange={(event) => setAcceptTerms(event.target.checked)}
          className="accent-green size-4 shrink-0"
        />
        <span>
          I accept the{" "}
          <Link href="/terms" className={textLinkClasses()}>
            Terms
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className={textLinkClasses()}>
            Privacy Policy
          </Link>
          .
        </span>
      </label>
    </fieldset>
  );

  const emailPlaceholder = `name@${google?.domains[0] ?? "example.com"}`;

  return (
    <section className="flex w-full flex-col gap-6" aria-labelledby={`${ids}-heading`}>
      <p role="status" aria-live="polite" className="sr-only">
        {status}
      </p>

      {step === "email" ? (
        <form noValidate onSubmit={onEmailSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <h1 id={`${ids}-heading`} className="text-h1">
              Sign in to {brand.name}
            </h1>
            <p className="text-muted">
              {google
                ? "Use your college Google account, or get a 6-digit code by email. New here? This creates your account."
                : "We'll email you a 6-digit code. No password needed. New here? This creates your account."}
            </p>
          </div>

          {google ? (
            <>
              <div className="flex flex-col gap-3">
                <GoogleButton onClick={onGoogle} disabled={submitting} className="w-full" />
                <p className="text-small text-muted text-center">
                  Only {google.domains.map((domain) => `@${domain}`).join(" or ")} Google accounts.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span aria-hidden="true" className="bg-line h-px flex-1" />
                <span className="text-small text-muted">or</span>
                <span aria-hidden="true" className="bg-line h-px flex-1" />
              </div>
            </>
          ) : null}

          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${ids}-email`} className="text-small text-ink font-medium">
              Email address
            </label>
            <input
              ref={emailInput}
              id={`${ids}-email`}
              name="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder={emailPlaceholder}
              maxLength={EMAIL_MAX_LENGTH}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? errorId : undefined}
              className={INPUT}
            />
          </div>

          {inviteField}
          {consent}
          {errorMessage}

          <button type="submit" disabled={submitting} className={PRIMARY}>
            {submitting ? "Sending code…" : "Email me a code"}
          </button>
        </form>
      ) : (
        <form noValidate onSubmit={onCodeSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <h1 id={`${ids}-heading`} className="text-h1">
              Check your email
            </h1>
            <p className="text-muted">
              Enter the 6-digit code we sent to{" "}
              <strong className="text-ink break-all">{email.trim()}</strong>. It expires in 10
              minutes.
            </p>
          </div>

          <div className="relative">
            <div aria-hidden="true" className="grid grid-cols-6 gap-2">
              {Array.from({ length: 6 }, (_, index) => (
                <div
                  key={index}
                  className={cx(
                    "bg-bg/60 flex h-14 items-center justify-center rounded-lg border font-mono text-[22px]",
                    codeFocused && index === Math.min(code.length, 5)
                      ? "border-green"
                      : "border-line-strong",
                  )}
                >
                  {code[index] ?? ""}
                </div>
              ))}
            </div>
            <label htmlFor={`${ids}-code`} className="sr-only">
              Sign-in code
            </label>
            <input
              ref={codeInput}
              id={`${ids}-code`}
              name="code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              onFocus={() => setCodeFocused(true)}
              onBlur={() => setCodeFocused(false)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? errorId : undefined}
              className="absolute inset-0 size-full cursor-text opacity-0"
            />
          </div>

          {inviteField}
          {errorMessage}

          <button type="submit" disabled={submitting} className={PRIMARY}>
            {submitting ? "Checking…" : "Sign in"}
          </button>

          <div className="text-small flex flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              onClick={onResend}
              disabled={submitting || secondsUntilResend > 0}
              className={`min-h-11 ${textLinkClasses()} disabled:text-muted disabled:cursor-not-allowed disabled:no-underline`}
            >
              {secondsUntilResend > 0 ? `Resend code in ${secondsUntilResend}s` : "Resend code"}
            </button>
            <button
              type="button"
              onClick={useDifferentEmail}
              className={`min-h-11 ${textLinkClasses("muted")}`}
            >
              Use a different email
            </button>
          </div>
        </form>
      )}
      {step === "code" ? appealForm : null}
    </section>
  );
}
