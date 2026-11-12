"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { Accordion } from "@/components/ds/accordion";
import { Button } from "@/components/ds/button";
import { ChoiceChip } from "@/components/ds/choices";
import { InlineError, Textarea } from "@/components/ds/fields";
import { ArrowLeftIcon, CheckIcon, FileIcon } from "@/components/ds/icons";
import { TwoToneHeadline } from "@/components/ds/page-parts";
import { Panel } from "@/components/ds/surfaces";
import { cx } from "@/components/ui/cx";
import { includesTag, toggleTag } from "@/lib/onboarding/catalog";
import { PDF_MAX_BYTES, PdfReadError, readPdfText, type PdfText } from "@/lib/onboarding/pdf-text";
import { PASTE_MAX, redact } from "@/lib/onboarding/redact";
import { spotSkills, type Found } from "@/lib/onboarding/spot";
import { commonSkills } from "@/lib/profile/skills";

export type ShortcutMode = "resume" | "paste";

type Reading = { name: string; size: number; pages: number | null; done: number };
type Stage =
  | { kind: "pick" }
  | { kind: "reading"; file: Reading }
  | { kind: "paste" }
  | { kind: "found"; found: Found; from: ShortcutMode };

export const PRIVACY_NOTE = "Up to 2 MB. Read in your browser, never uploaded or stored.";
const READING_NOTE = "We remove phone numbers, emails and addresses before anything else happens.";

function foundNote(from: ShortcutMode): string {
  return `Found in your ${from === "resume" ? "resume" : "text"}. Phone numbers, emails and addresses were removed first. Only the chips you keep are saved; the text is thrown away.`;
}

function sizeLabel(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * "Skip the typing" on step 2 (ADR 0022 screens 6 and 7, ADR 0023): a resume PDF or pasted
 * text is read on the device, personal details are removed, and known skill names are
 * suggested. Nothing is sent or saved here: the kept chips go back to step 2, which saves
 * them only when the person continues.
 */
export function ImportShortcut({
  mode,
  onUse,
  onCancel,
  loadNames = commonSkills,
  readPdf = readPdfText,
  embedded = false,
}: {
  mode: ShortcutMode;
  /** Inside another page (the screens preview): no <main>, no sticky footer. */
  embedded?: boolean;
  onUse: (found: Found) => void;
  onCancel: () => void;
  loadNames?: () => Promise<string[]>;
  readPdf?: (file: File, onPage: (done: number, total: number) => void) => Promise<PdfText>;
}) {
  const [stage, setStage] = useState<Stage>({ kind: mode === "resume" ? "pick" : "paste" });
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [kept, setKept] = useState<Found>({ skills: [], interests: [] });
  const names = useRef<Promise<string[]> | null>(null);
  const run = useRef(0);
  const headingRef = useRef<HTMLDivElement>(null);

  // Start fetching the name list at once; it is small and only names, no text goes out.
  useEffect(() => {
    names.current ??= loadNames();
  }, [loadNames]);

  // Each new state is announced by moving focus to its heading.
  const firstRender = useRef(true);
  useEffect(() => {
    if (embedded && firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [stage.kind, embedded]);

  async function suggest(raw: string, from: ShortcutMode) {
    const clean = redact(raw).text;
    const found = spotSkills(clean, await (names.current ?? loadNames()));
    setKept(found);
    setStage({ kind: "found", found, from });
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    const id = ++run.current;
    const reading: Reading = { name: file.name, size: file.size, pages: null, done: 0 };
    setStage({ kind: "reading", file: reading });
    try {
      const pdf = await readPdf(file, (done, total) => {
        if (run.current === id) {
          setStage({ kind: "reading", file: { ...reading, pages: total, done } });
        }
      });
      if (run.current !== id) return;
      await suggest(pdf.text, "resume");
    } catch (caught) {
      if (run.current !== id) return;
      setStage({ kind: "pick" });
      setError(
        caught instanceof PdfReadError
          ? caught.message
          : "We couldn't read that PDF. Try pasting the text.",
      );
    }
  }

  function cancelReading() {
    run.current += 1;
    setStage({ kind: "pick" });
  }

  function startOver() {
    setError(null);
    setStage({ kind: mode === "resume" ? "pick" : "paste" });
  }

  const count = kept.skills.length + kept.interests.length;

  let heading: { lead: string; rest: string };
  let body: ReactNode;
  let footer: ReactNode;

  if (stage.kind === "pick") {
    heading = { lead: "Import your resume.", rest: "We'll suggest skills from it." };
    body = <PickFile onFile={onFile} error={error} />;
    footer = null;
  } else if (stage.kind === "reading") {
    heading = { lead: "Reading your resume…", rest: "This takes a moment." };
    body = <ReadingSteps file={stage.file} />;
    footer = (
      <Button variant="ghost" onClick={cancelReading}>
        Cancel
      </Button>
    );
  } else if (stage.kind === "paste") {
    heading = {
      lead: "Paste anything about you.",
      rest: "LinkedIn About, resume, a portfolio blurb.",
    };
    body = (
      <Textarea
        label="Text about you"
        rows={9}
        maxLength={PASTE_MAX}
        hint="We pick out skills and interests. You'll confirm everything."
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
    );
    footer = (
      <>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <span className="flex-1" />
        <Button
          variant="primary"
          disabled={!text.trim()}
          onClick={() => suggest(text.slice(0, PASTE_MAX), "paste")}
        >
          Find my skills
        </Button>
      </>
    );
  } else {
    heading = { lead: "We found these.", rest: "Keep what's right." };
    body = <Suggestions found={stage.found} from={stage.from} kept={kept} onChange={setKept} />;
    footer = (
      <>
        <Button variant="ghost" onClick={startOver}>
          Start over
        </Button>
        <span className="flex-1" />
        <span role="status" className="text-mono-lg text-muted font-mono uppercase">
          {count} kept
        </span>
        <Button variant="primary" disabled={count === 0} onClick={() => onUse(kept)}>
          Use these
          <CheckIcon className="size-4" />
        </Button>
      </>
    );
  }

  const Main = embedded ? "div" : "main";
  const Footer = embedded ? "div" : "footer";
  return (
    <>
      <Main
        className={cx(
          "mx-auto grid w-full max-w-[640px] content-start gap-6",
          embedded ? "" : "px-4 pt-6 pb-6 lg:gap-8 lg:px-0 lg:pt-12 lg:pb-8",
        )}
      >
        {stage.kind === "reading" ? null : (
          <button
            type="button"
            onClick={onCancel}
            className="text-meta-lg text-ink-2 hover:text-ink -my-2 inline-flex min-h-11 items-center gap-1.5 self-start"
          >
            <ArrowLeftIcon className="size-4" />
            Back to skills
          </button>
        )}
        <div ref={headingRef} tabIndex={-1} className="outline-none">
          <TwoToneHeadline
            as={embedded ? "h3" : "h1"}
            size="greeting"
            lead={heading.lead}
            rest={heading.rest}
          />
        </div>
        {body}
      </Main>
      {footer ? (
        <Footer
          className={cx(
            "mx-auto flex w-full max-w-[640px] items-center gap-2",
            embedded
              ? "border-line mt-4 border-t pt-3"
              : "border-line bg-bg sticky bottom-0 mt-auto border-t px-4 py-3 pb-[max(12px,env(safe-area-inset-bottom))] lg:static lg:mb-12 lg:border-0 lg:bg-transparent lg:px-0 lg:pt-5",
          )}
        >
          {footer}
        </Footer>
      ) : null}
    </>
  );
}

function PickFile({
  onFile,
  error,
}: {
  onFile: (file: File | undefined) => void;
  error: string | null;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div className="grid gap-4">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setOver(false);
          onFile(event.dataTransfer.files[0]);
        }}
        className={cx(
          "bg-card rounded-card grid justify-items-center gap-3 border-2 border-dashed px-4 py-8 text-center",
          over ? "border-green" : "border-muted-2",
        )}
      >
        <span className="bg-green-tint text-green grid size-11 place-items-center rounded-full">
          <FileIcon className="size-5" />
        </span>
        <p className="text-body text-ink">Drop your resume PDF here or choose a file</p>
        <input
          ref={input}
          id={id}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          tabIndex={-1}
          aria-label="Choose a resume PDF"
          aria-describedby={`${id}-note`}
          onChange={(event) => {
            onFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <Button variant="outline" onClick={() => input.current?.click()}>
          Choose a file
        </Button>
        <p id={`${id}-note`} className="text-meta text-muted">
          {PRIVACY_NOTE}
        </p>
      </div>
      {error ? <InlineError announce>{error}</InlineError> : null}
      <Accordion
        items={[
          {
            id: "linkedin",
            question: "Using LinkedIn?",
            answer: (
              <p>
                Open your LinkedIn profile, choose More → Save to PDF, then drop that file here.
              </p>
            ),
          },
        ]}
      />
      <p className="sr-only">PDF files up to {sizeLabel(PDF_MAX_BYTES)}.</p>
    </div>
  );
}

function ReadingSteps({ file }: { file: Reading }) {
  const percent = file.pages ? Math.round((file.done / file.pages) * 90) + 5 : 5;
  const steps = [
    { label: "Text read in your browser", done: file.pages !== null && file.done >= file.pages },
    { label: "Removing phone numbers, emails and addresses", done: false },
    { label: "Finding skills, interests and projects", done: false },
  ];
  return (
    <div className="grid gap-4">
      <Panel className="grid gap-3">
        <div className="flex items-center gap-3">
          <span className="bg-green-tint text-green grid size-10 shrink-0 place-items-center rounded-full">
            <FileIcon className="size-5" />
          </span>
          <div className="min-w-0">
            <p className="text-body text-ink truncate">{file.name}</p>
            <p className="text-meta text-muted">
              {file.pages === null
                ? sizeLabel(file.size)
                : `${file.pages} ${file.pages === 1 ? "page" : "pages"} · ${sizeLabel(file.size)}`}
            </p>
          </div>
        </div>
        <div
          role="progressbar"
          aria-label="Reading your resume"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="bg-line h-1.5 overflow-hidden rounded-full"
        >
          <div className="bg-green h-full rounded-full" style={{ width: `${percent}%` }} />
        </div>
        <ol className="grid gap-2" aria-label="Steps">
          {steps.map((step) => (
            <li key={step.label} className="text-meta-lg text-ink flex items-center gap-2">
              <span
                aria-hidden
                className={cx(
                  "grid size-5 place-items-center rounded-full border",
                  step.done ? "border-green bg-green text-bg" : "border-muted-2",
                )}
              >
                {step.done ? <CheckIcon className="size-3" /> : null}
              </span>
              {step.label}
              {step.done ? <span className="sr-only">, done</span> : null}
            </li>
          ))}
        </ol>
      </Panel>
      <p className="text-meta-lg text-ink-2">{READING_NOTE}</p>
    </div>
  );
}

function Suggestions({
  found,
  from,
  kept,
  onChange,
}: {
  found: Found;
  from: ShortcutMode;
  kept: Found;
  onChange: (kept: Found) => void;
}) {
  if (found.skills.length + found.interests.length === 0) {
    return (
      <Panel className="text-meta-lg text-ink-2">
        We didn&apos;t spot any skills we know. Go back and pick them from the list, or try
        different text.
      </Panel>
    );
  }
  const groups: { key: keyof Found; label: string }[] = [
    { key: "skills", label: "Skills you offer" },
    { key: "interests", label: "Interests" },
  ];
  return (
    <div className="grid gap-5">
      <p className="text-meta-lg text-ink-2">
        Tap a chip to drop it. Dashed chips won&apos;t be saved.
      </p>
      <Panel tone="green" className="text-meta-lg text-ink">
        {foundNote(from)}
      </Panel>
      {groups.map(({ key, label }) =>
        found[key].length ? (
          <div key={key} className="grid gap-2.5">
            <p className="text-mono text-muted font-mono uppercase" id={`found-${key}`}>
              {label}
            </p>
            <div role="group" aria-labelledby={`found-${key}`} className="flex flex-wrap gap-2">
              {found[key].map((name) => {
                const keep = includesTag(kept[key], name);
                return (
                  <ChoiceChip
                    key={name}
                    pressed={keep}
                    onToggle={() => onChange({ ...kept, [key]: toggleTag(kept[key], name) })}
                    className={keep ? undefined : "border-dashed"}
                  >
                    {name}
                  </ChoiceChip>
                );
              })}
            </div>
          </div>
        ) : null,
      )}
    </div>
  );
}
