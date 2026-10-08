"use client";

import { useEffect, useRef, useState } from "react";

import { cx } from "@/components/ui/cx";
import { SECTIONS, type SectionId } from "@/lib/profile/you";

/**
 * The section list: numbered on the left from 1024px, a sticky row of chips on phones.
 * The section in view is marked (scroll spy); on phones its chip scrolls into view.
 */
export function SectionNav() {
  const [current, setCurrent] = useState<SectionId>(SECTIONS[0].id);
  const links = useRef(new Map<SectionId, HTMLAnchorElement>());

  useEffect(() => {
    if (!("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const id = entry.target.id as SectionId;
          setCurrent(id);
          if (window.innerWidth < 1024) {
            links.current.get(id)?.scrollIntoView({ inline: "center", block: "nearest" });
          }
        }
      },
      { rootMargin: "-130px 0px -65% 0px" },
    );
    for (const { id } of SECTIONS) {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    }
    return () => observer.disconnect();
  }, []);

  return (
    <nav
      aria-label="Sections"
      className={cx(
        "border-line bg-bg sticky top-0 z-20 -mx-4 [scrollbar-width:none] overflow-x-auto border-b px-4 py-2 whitespace-nowrap",
        "lg:top-6 lg:mx-0 lg:flex lg:flex-col lg:gap-0.5 lg:self-start lg:overflow-visible lg:border-0 lg:p-0 lg:whitespace-normal",
      )}
    >
      {SECTIONS.map(({ id, label }, index) => {
        const on = id === current;
        return (
          <a
            key={id}
            ref={(node) => {
              if (node) links.current.set(id, node);
            }}
            href={`#${id}`}
            aria-current={on ? "location" : undefined}
            onClick={() => setCurrent(id)}
            className={cx(
              "text-meta mr-1 inline-flex min-h-11 items-center gap-1.5 rounded-full border px-3",
              "lg:text-meta-lg lg:m-0 lg:min-h-[38px] lg:rounded-lg lg:border-0 lg:border-l-2 lg:px-2.5",
              on
                ? "bg-ink text-bg border-ink lg:bg-panel lg:text-ink lg:border-green font-medium"
                : "border-line text-ink-2 lg:border-transparent",
            )}
          >
            <span aria-hidden className="text-muted hidden font-mono text-[10px] lg:inline">
              {String(index + 1).padStart(2, "0")}
            </span>
            {label}
          </a>
        );
      })}
    </nav>
  );
}
