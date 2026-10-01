"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { browserApi } from "@/lib/api/browser";
import { ApiError } from "@/lib/api/errors";
import { otpRequestResponseSchema, userSchema } from "@/lib/api/schemas";
import { RESEND_COOLDOWN_SECONDS } from "@/lib/auth/constants";
import { describeError } from "@/lib/auth/messages";
import { brand } from "@/lib/brand";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const EMAIL_MAX_LENGTH = 254;

type Step = "email" | "code";

/**
 * Two-step passwordless sign-in: (1) email plus age and terms confirmation, (2) the 6-digit
 * code from the email. Uses native form controls, labelled fields, and announces errors
 * (role="alert") and progress (role="status") to assistive technology.
 */
export function LoginForm({ nextPath }: { nextPath: string }) {
  const router = useRouter();
  const ids = useId();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resendAt, setResendAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const codeInput = useRef<HTMLInputElement>(null);
  const emailInput = useRef<HTMLInputElement>(null);

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
      setError("To continue, confirm that you are 18 or older and accept the terms.");
      return;
    }
    if (await sendCode()) {
      setCode("");
      setStep("code");
      setStatus(`We sent a 6-digit code to ${trimmed}. It expires in 10 minutes.`);
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
        body: { email: email.trim(), code, age_confirmed: ageConfirmed, accept_terms: acceptTerms },
      });
      setStatus("You're signed in. Taking you there now…");
      router.replace(nextPath);
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
      if (caught instanceof ApiError && caught.code === "code_locked") setCode("");
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
    <p id={errorId} role="alert" className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-800">
      {error}
    </p>
  ) : null;

  return (
    <section className="flex w-full max-w-md flex-col gap-6" aria-labelledby={`${ids}-heading`}>
      <p role="status" aria-live="polite" className="sr-only">
        {status}
      </p>

      {step === "email" ? (
        <form noValidate onSubmit={onEmailSubmit} className="flex flex-col gap-5">
          <h1 id={`${ids}-heading`} className="text-2xl font-bold text-slate-900">
            Sign in to {brand.name}
          </h1>
          <p className="text-slate-600">
            We&apos;ll email you a 6-digit code. No password needed. New here? This creates your
            account.
          </p>

          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${ids}-email`} className="font-medium text-slate-800">
              Email address
            </label>
            <input
              ref={emailInput}
              id={`${ids}-email`}
              name="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              maxLength={EMAIL_MAX_LENGTH}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? errorId : undefined}
              className="rounded-md border border-slate-300 px-3 py-2 text-base focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 focus:outline-none"
            />
          </div>

          <fieldset className="flex flex-col gap-3">
            <legend className="sr-only">Confirmations</legend>
            <label className="flex items-start gap-3 text-slate-700">
              <input
                type="checkbox"
                checked={ageConfirmed}
                onChange={(event) => setAgeConfirmed(event.target.checked)}
                className="mt-1 size-4"
              />
              <span>I am 18 or older.</span>
            </label>
            <label className="flex items-start gap-3 text-slate-700">
              <input
                type="checkbox"
                checked={acceptTerms}
                onChange={(event) => setAcceptTerms(event.target.checked)}
                className="mt-1 size-4"
              />
              <span>
                I accept the{" "}
                <Link href="/terms" className="text-indigo-700 underline">
                  Terms
                </Link>{" "}
                and{" "}
                <Link href="/privacy" className="text-indigo-700 underline">
                  Privacy Policy
                </Link>
                .
              </span>
            </label>
          </fieldset>

          {errorMessage}

          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-indigo-600 px-4 py-2.5 font-semibold text-white hover:bg-indigo-700 focus-visible:ring-2 focus-visible:ring-indigo-300 focus-visible:outline-none disabled:opacity-60"
          >
            {submitting ? "Sending code…" : "Email me a code"}
          </button>
        </form>
      ) : (
        <form noValidate onSubmit={onCodeSubmit} className="flex flex-col gap-5">
          <h1 id={`${ids}-heading`} className="text-2xl font-bold text-slate-900">
            Check your email
          </h1>
          <p className="text-slate-600">
            Enter the 6-digit code we sent to <strong className="break-all">{email.trim()}</strong>.
            It expires in 10 minutes.
          </p>

          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${ids}-code`} className="font-medium text-slate-800">
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
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? errorId : undefined}
              className="rounded-md border border-slate-300 px-3 py-2 font-mono text-xl tracking-[0.4em] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 focus:outline-none"
            />
          </div>

          {errorMessage}

          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-indigo-600 px-4 py-2.5 font-semibold text-white hover:bg-indigo-700 focus-visible:ring-2 focus-visible:ring-indigo-300 focus-visible:outline-none disabled:opacity-60"
          >
            {submitting ? "Checking…" : "Sign in"}
          </button>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <button
              type="button"
              onClick={onResend}
              disabled={submitting || secondsUntilResend > 0}
              className="text-indigo-700 underline disabled:text-slate-500 disabled:no-underline"
            >
              {secondsUntilResend > 0 ? `Resend code in ${secondsUntilResend}s` : "Resend code"}
            </button>
            <button type="button" onClick={useDifferentEmail} className="text-slate-700 underline">
              Use a different email
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
