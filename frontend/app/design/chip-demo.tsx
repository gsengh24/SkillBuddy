"use client";

import { useState } from "react";

import { IntentChip } from "@/components/ui/intent-chip";
import { INTENTS, type Intent } from "@/lib/design/tokens";

/** Interactive intent chips: toggle buttons with aria-pressed. */
export function IntentChipDemo() {
  const [selected, setSelected] = useState<Intent>("build_together");
  return (
    <div role="group" aria-label="What are you looking for" className="flex flex-wrap gap-2">
      {INTENTS.map((intent) => (
        <IntentChip
          key={intent}
          intent={intent}
          selected={selected === intent}
          onToggle={() => setSelected(intent)}
        />
      ))}
    </div>
  );
}
