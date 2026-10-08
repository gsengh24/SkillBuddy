"use client";

import { useId, useState, type ComponentProps, type ReactNode } from "react";

import { cx } from "../ui/cx";

type FieldProps = {
  label: string;
  /** Visually hide the label (it stays the accessible name). */
  hideLabel?: boolean;
  hint?: string;
  error?: string | null;
};

function describedBy(...ids: (string | false | null | undefined)[]): string | undefined {
  const joined = ids.filter(Boolean).join(" ");
  return joined || undefined;
}

/**
 * White field, radius 10, 16px text on phones (no iOS zoom). The border is muted-2, not the
 * reference's line colour: it is the field's only edge, so it needs 3:1 (ADR 0014).
 */
const FIELD = cx(
  "rounded-input border-muted-2 bg-bg text-ink w-full border px-3 text-[16px] sm:text-body",
  "placeholder:text-muted focus:border-green aria-invalid:border-danger",
);

function Label({
  htmlFor,
  hidden,
  children,
}: {
  htmlFor: string;
  hidden: boolean;
  children: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className={cx("text-meta-lg text-ink font-medium", hidden && "sr-only")}
    >
      {children}
    </label>
  );
}

function Footnotes({
  hintId,
  hint,
  errorId,
  error,
  counter,
}: {
  hintId: string;
  hint?: string;
  errorId: string;
  error?: string | null;
  counter?: ReactNode;
}) {
  if (!hint && !error && !counter) return null;
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        {hint ? (
          <p id={hintId} className="text-meta text-muted">
            {hint}
          </p>
        ) : null}
        {error ? <InlineError id={errorId}>{error}</InlineError> : null}
      </div>
      {counter}
    </div>
  );
}

/** A labelled text input with an optional hint and error. */
export function Input({
  label,
  hideLabel = false,
  hint,
  error,
  id,
  className,
  ...props
}: FieldProps & ComponentProps<"input">) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={inputId} hidden={hideLabel}>
        {label}
      </Label>
      <input
        id={inputId}
        {...props}
        aria-invalid={error ? true : props["aria-invalid"]}
        aria-describedby={describedBy(hint && hintId, error && errorId, props["aria-describedby"])}
        className={cx(FIELD, "h-11", className)}
      />
      <Footnotes hintId={hintId} hint={hint} errorId={errorId} error={error} />
    </div>
  );
}

/** A labelled native select, styled like Input. */
export function Select({
  label,
  hideLabel = false,
  hint,
  error,
  id,
  className,
  children,
  ...props
}: FieldProps & ComponentProps<"select">) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={inputId} hidden={hideLabel}>
        {label}
      </Label>
      <select
        id={inputId}
        {...props}
        aria-invalid={error ? true : props["aria-invalid"]}
        aria-describedby={describedBy(hint && hintId, error && errorId, props["aria-describedby"])}
        className={cx(FIELD, "h-11", className)}
      >
        {children}
      </select>
      <Footnotes hintId={hintId} hint={hint} errorId={errorId} error={error} />
    </div>
  );
}

/**
 * A labelled textarea. With `maxLength`, a mono counter ("12/500") sits under it. The
 * counter is visual only (not read on every key); `maxLength` itself stops extra input.
 */
export function Textarea({
  label,
  hideLabel = false,
  hint,
  error,
  id,
  className,
  rows = 3,
  maxLength,
  showCounter = true,
  defaultValue,
  onChange,
  ...props
}: FieldProps &
  ComponentProps<"textarea"> & {
    /** Show the mono "n/max" counter when there is a maxLength (default). */
    showCounter?: boolean;
  }) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const [typed, setTyped] = useState(String(defaultValue ?? "").length);
  // A controlled field (value set by its owner, e.g. from a suggestion) counts its value.
  const length = props.value === undefined ? typed : String(props.value).length;
  const counter =
    maxLength === undefined || !showCounter ? null : (
      <span aria-hidden className="text-mono text-muted shrink-0 font-mono">
        {length}/{maxLength}
      </span>
    );
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={inputId} hidden={hideLabel}>
        {label}
      </Label>
      <textarea
        id={inputId}
        rows={rows}
        maxLength={maxLength}
        defaultValue={defaultValue}
        onChange={(event) => {
          setTyped(event.target.value.length);
          onChange?.(event);
        }}
        {...props}
        aria-invalid={error ? true : props["aria-invalid"]}
        aria-describedby={describedBy(hint && hintId, error && errorId, props["aria-describedby"])}
        className={cx(FIELD, "min-h-[72px] resize-y py-2.5", className)}
      />
      <Footnotes hintId={hintId} hint={hint} errorId={errorId} error={error} counter={counter} />
    </div>
  );
}

/**
 * An inline error: says what happened and what to do, in sentence case, with no "Error:"
 * prefix. `announce` makes screen readers read it when it appears.
 */
export function InlineError({
  id,
  announce = false,
  children,
  className,
}: {
  id?: string;
  announce?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      id={id}
      role={announce ? "alert" : undefined}
      className={cx("text-meta-lg text-danger font-medium", className)}
    >
      {children}
    </p>
  );
}

/**
 * A toast: a short status message in a panel. Read politely by screen readers (an error
 * is read at once). With `onDismiss`, it gets a close button.
 */
export function Toast({
  tone = "info",
  onDismiss,
  children,
  className,
}: {
  tone?: "info" | "error";
  onDismiss?: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx(
        "rounded-card bg-bg flex items-center justify-between gap-3 border px-4 py-3",
        tone === "error" ? "border-danger text-danger" : "border-line text-ink",
        className,
      )}
    >
      <p className="text-body font-medium">{children}</p>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          className="text-meta-lg text-ink hover:bg-panel rounded-control min-h-11 shrink-0 px-3 font-medium pointer-fine:min-h-9"
        >
          Dismiss
        </button>
      ) : null}
    </div>
  );
}
