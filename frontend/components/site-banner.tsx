"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { cx } from "@/components/ui/cx";
import { BANNER_STYLES } from "@/lib/banner-styles";

const DISMISSED_KEY = "dismissed-banners";

type Banner = { id: string; message: string; kind: keyof typeof BANNER_STYLES };

/**
 * Checked by hand rather than with the zod schemas: this runs on every page, including ones
 * with no other client code, so it must not pull the schema library into them.
 */
function parse(body: unknown): Banner | null {
  if (typeof body !== "object" || body === null || !("banner" in body)) return null;
  const banner: unknown = body.banner;
  if (typeof banner !== "object" || banner === null) return null;
  const { id, message, kind } = banner as Record<string, unknown>;
  if (typeof id !== "string" || typeof message !== "string") return null;
  if (kind !== "info" && kind !== "warning" && kind !== "maintenance") return null;
  return { id, message, kind };
}

function dismissed(): string[] {
  try {
    const stored: unknown = JSON.parse(window.localStorage.getItem(DISMISSED_KEY) ?? "[]");
    return Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

/**
 * The admin's announcement at the top of the app (A8). Loaded after the page (the API caches
 * it for a minute), so it never slows the page down. Plain text. Dismissing hides that banner
 * in this browser; a new banner shows again.
 */
export function SiteBanner() {
  const pathname = usePathname();
  const [banner, setBanner] = useState<Banner | null>(null);

  useEffect(() => {
    if (pathname.startsWith("/admin")) return;
    let cancelled = false;
    fetch("/api/v1/banner", { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body: unknown) => {
        const found = parse(body);
        if (!cancelled && found && !dismissed().includes(found.id)) setBanner(found);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  if (!banner || pathname.startsWith("/admin")) return null;

  function dismiss() {
    if (!banner) return;
    try {
      window.localStorage.setItem(
        DISMISSED_KEY,
        JSON.stringify([...dismissed(), banner.id].slice(-20)),
      );
    } catch {
      // Private browsing: it simply shows again next time.
    }
    setBanner(null);
  }

  return (
    <div
      role="status"
      className={cx(
        "text-meta-lg flex items-center justify-between gap-3 border-b px-4 py-1.5",
        BANNER_STYLES[banner.kind],
      )}
    >
      <p className="mx-auto max-w-5xl min-w-0 flex-1 break-words">{banner.message}</p>
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss announcement"
        className="hover:bg-bg inline-flex size-11 shrink-0 items-center justify-center rounded-full pointer-fine:size-8"
      >
        ×
      </button>
    </div>
  );
}
