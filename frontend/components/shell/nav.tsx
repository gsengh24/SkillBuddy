"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { TopBar } from "@/components/ds/page-parts";

import { APP_LINKS, currentPlace } from "./links";

/** The desktop top bar, with the current section marked (aria-current="page"). */
export function AppTopBar({ actions }: { actions: ReactNode }) {
  const current = currentPlace(usePathname());
  return (
    <TopBar
      homeHref="/home"
      links={APP_LINKS.map(({ href, label }) => ({ href, label }))}
      currentHref={current?.href}
      actions={actions}
    />
  );
}
