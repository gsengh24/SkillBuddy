"use client";

import { useState } from "react";

import { ALL_LISTED_SKILLS, INTERESTS } from "@/lib/onboarding/catalog";

import { ImportShortcut, type ShortcutMode } from "./import-shortcut";

const NAMES = [...ALL_LISTED_SKILLS, ...INTERESTS, "Firebase"];
const loadNames = () => Promise.resolve(NAMES);

/**
 * Screens 6 and 7 on the screens preview (no session): the real component, with the
 * onboarding chips as the name list and the real in-browser PDF reader. "Use these" and
 * "Back to skills" only say what would happen.
 */
export function ImportShortcutPreview({ mode }: { mode: ShortcutMode }) {
  const [said, setSaid] = useState<string | null>(null);
  return (
    <div className="bg-bg border-line rounded-card border p-4 lg:p-6">
      <ImportShortcut
        embedded
        mode={mode}
        loadNames={loadNames}
        onUse={(found) =>
          setSaid(`Would add ${found.skills.length + found.interests.length} to step 2.`)
        }
        onCancel={() => setSaid("Would go back to step 2.")}
      />
      {said ? (
        <p role="status" className="text-meta-lg text-ink-2 mt-3">
          {said}
        </p>
      ) : null}
    </div>
  );
}
