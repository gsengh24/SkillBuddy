"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** True for fields where Escape belongs to the field (typing a message, a report note). */
function inField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * While an item is open on Home, Escape goes back to the composer view (design spec 6.2,
 * v2), like "New request". It leaves Escape alone inside text fields, so a half-written
 * message or report is never thrown away.
 */
export function EscapeToComposer({ href }: { href: string }) {
  const router = useRouter();
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape" || event.defaultPrevented || inField(event.target)) return;
      router.push(href);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [href, router]);
  return null;
}
