"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

const FAST_MS = 20_000;
const SLOW_MS = 60_000;
// Coming back to the tab refreshes at once, unless it refreshed a moment ago.
const MIN_GAP_MS = 30_000;

/**
 * Keeps Home current without a reload while the tab is visible: every 20 s while a request is
 * still being matched (`fast`), otherwise every 60 s, and when the person comes back to the
 * tab. Each refresh re-runs the whole page and the shell on the server, so it is kept sparing.
 * Renders nothing.
 */
export function LiveRefresh({ fast = false }: { fast?: boolean }) {
  const router = useRouter();
  const last = useRef(0);
  useEffect(() => {
    last.current = Date.now();
    const refresh = () => {
      last.current = Date.now();
      router.refresh();
    };
    const tick = () => {
      if (document.visibilityState === "visible") refresh();
    };
    const comeBack = () => {
      if (document.visibilityState === "visible" && Date.now() - last.current >= MIN_GAP_MS) {
        refresh();
      }
    };
    const timer = window.setInterval(tick, fast ? FAST_MS : SLOW_MS);
    document.addEventListener("visibilitychange", comeBack);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", comeBack);
    };
  }, [router, fast]);
  return null;
}
