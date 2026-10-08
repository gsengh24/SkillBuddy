import type { ReactNode } from "react";

import { Panel } from "@/components/ds/surfaces";
import { Overline } from "@/components/ui/overline";

/** A route that exists in the shell but whose screen is built in a later step. */
export function PlaceholderPage({
  title,
  intro,
  children,
}: {
  title: string;
  intro: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-headline lg:text-headline-lg">{title}</h1>
        <p className="text-muted">{intro}</p>
      </header>
      <Panel className="flex flex-col gap-2">
        <Overline>Coming soon</Overline>
        <p>This screen is part of a later step. Nothing here yet.</p>
      </Panel>
      {children}
    </div>
  );
}
