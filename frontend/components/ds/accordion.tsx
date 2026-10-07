"use client";

import { useId, useState, type ReactNode } from "react";

import { cx } from "../ui/cx";
import { ChevronDownIcon } from "./icons";

export type AccordionItem = { id: string; question: string; answer: ReactNode };

/**
 * FAQ accordion: hairline rows, each question a button with aria-expanded that controls
 * its answer region. The answer opens smoothly (grid rows; the one exception to "transform
 * and opacity only", allowed by the spec) and is inert while closed, so it is neither read
 * nor focusable. With `single`, opening one closes the others.
 */
export function Accordion({
  items,
  single = false,
  headingLevel = 3,
  className,
}: {
  items: AccordionItem[];
  single?: boolean;
  headingLevel?: 2 | 3 | 4;
  className?: string;
}) {
  const baseId = useId();
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const Heading = `h${headingLevel}` as const;

  function toggle(id: string) {
    setOpen((current) => {
      const next = new Set(single ? [] : current);
      if (current.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className={cx("border-line max-w-[760px] border-t", className)}>
      {items.map((item) => {
        const expanded = open.has(item.id);
        const buttonId = `${baseId}-${item.id}-button`;
        const panelId = `${baseId}-${item.id}-panel`;
        return (
          <div key={item.id} className="border-line border-b">
            <Heading className="m-0">
              <button
                id={buttonId}
                type="button"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => toggle(item.id)}
                className="text-body-lg flex min-h-11 w-full items-center justify-between gap-3 py-4 text-left font-medium"
              >
                {item.question}
                <ChevronDownIcon
                  className={cx(
                    "text-muted size-5 shrink-0 transition-transform duration-200",
                    expanded && "rotate-180",
                  )}
                />
              </button>
            </Heading>
            <div
              id={panelId}
              role="region"
              aria-labelledby={buttonId}
              inert={!expanded}
              className={cx(
                "grid transition-[grid-template-rows] duration-300 ease-out",
                expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
              )}
            >
              <div className="overflow-hidden">
                <div className="text-ink-2 max-w-[62ch] pb-4">{item.answer}</div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
