import Link from "next/link";
import type { ReactNode } from "react";

import { legal } from "@/lib/legal";

import { DraftNotice } from "./draft-notice";

export type TocEntry = { id: string; title: string };

/**
 * The frame of a legal page (privacy, terms): the title, the version line, the draft
 * notice, then the sections, with a sticky table of contents on desktop. Only the frame
 * lives here; every word of the policy stays in the page.
 */
export function LegalPage({
  title,
  toc,
  children,
}: {
  title: string;
  toc: TocEntry[];
  children: ReactNode;
}) {
  return (
    <main className="max-w-content mx-auto w-full px-4 py-10 lg:px-8 lg:py-14">
      <div className="lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-12">
        <nav aria-label="On this page" className="hidden lg:block">
          <div className="sticky top-8 flex flex-col gap-2">
            <p className="text-mono-lg text-muted font-mono uppercase">On this page</p>
            <ol className="border-line flex flex-col border-l">
              {toc.map((entry) => (
                <li key={entry.id}>
                  <Link
                    href={`#${entry.id}`}
                    className="text-meta-lg text-muted hover:text-ink hover:border-green -ml-px block border-l border-transparent py-1 pl-3"
                  >
                    {entry.title}
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        </nav>
        <article className="flex max-w-[72ch] flex-col gap-6">
          <header className="flex flex-col gap-2">
            <h1 className="text-headline lg:text-headline-lg">{title}</h1>
            <p className="text-meta-lg text-muted">
              Last updated {legal.updated} (version {legal.version}).
            </p>
          </header>
          <DraftNotice />
          {children}
        </article>
      </div>
    </main>
  );
}

/** One section, with a hairline above it and room to land on from the contents. */
export function LegalSection({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-h`}
      className="border-line flex scroll-mt-8 flex-col gap-2 border-t pt-6"
    >
      <h2
        id={`${id}-h`}
        className="font-display tracking-display text-[20px] leading-tight font-extrabold"
      >
        {title}
      </h2>
      <div className="text-ink-2 flex flex-col gap-2">{children}</div>
    </section>
  );
}
