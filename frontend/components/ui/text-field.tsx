import { useId, type ComponentProps } from "react";

import { cx } from "./cx";

type FieldProps = {
  label: string;
  /** Visually hide the label (it stays the accessible name). */
  hideLabel?: boolean;
  hint?: string;
  error?: string | null;
};

function describedBy(...ids: (string | false | undefined)[]): string | undefined {
  const joined = ids.filter(Boolean).join(" ");
  return joined || undefined;
}

const FIELD = cx(
  "w-full rounded-none border-0 border-b border-muted bg-transparent px-0 text-body text-ink",
  "placeholder:text-muted hover:border-ink focus:border-green-base aria-invalid:border-coral-ink",
);

/** Underline-only text input with a real label, an optional hint and an error message. */
export function TextField({
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
    <div className="flex flex-col gap-1">
      <label
        htmlFor={inputId}
        className={cx("text-small text-ink font-semibold", hideLabel && "sr-only")}
      >
        {label}
      </label>
      <input
        id={inputId}
        {...props}
        aria-invalid={error ? true : props["aria-invalid"]}
        aria-describedby={describedBy(
          hint && hintId,
          error ? errorId : undefined,
          props["aria-describedby"],
        )}
        className={cx(FIELD, "h-11", className)}
      />
      {hint ? (
        <p id={hintId} className="text-small text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-small text-coral-ink font-semibold">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Underline-only multi-line field; same rules as TextField. */
export function TextArea({
  label,
  hideLabel = false,
  hint,
  error,
  id,
  className,
  rows = 4,
  ...props
}: FieldProps & ComponentProps<"textarea">) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={inputId}
        className={cx("text-small text-ink font-semibold", hideLabel && "sr-only")}
      >
        {label}
      </label>
      <textarea
        id={inputId}
        rows={rows}
        {...props}
        aria-invalid={error ? true : props["aria-invalid"]}
        aria-describedby={describedBy(
          hint && hintId,
          error ? errorId : undefined,
          props["aria-describedby"],
        )}
        className={cx(FIELD, "resize-y py-2", className)}
      />
      {hint ? (
        <p id={hintId} className="text-small text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-small text-coral-ink font-semibold">
          {error}
        </p>
      ) : null}
    </div>
  );
}
