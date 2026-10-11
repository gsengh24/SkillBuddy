"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

const EVERY_MS = 20_000;

/**
 * Keeps Home current without a reload: re-fetches the page's data every 20 s while the tab
 * is visible, and straight away when the person comes back to it. Renders nothing.
 */
export function LiveRefresh() {
  const router = useRouter();
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "visible") router.refresh();
    };
    const timer = window.setInterval(refresh, EVERY_MS);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [router]);
  return null;
}
