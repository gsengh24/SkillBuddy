"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Logo } from "@/components/ds/logo";
import { cx } from "@/components/ui/cx";
import { ROLE_LABELS, type AdminRole } from "@/lib/admin/schemas";
import { hrefOf, type AdminPage } from "@/lib/admin/pages";
import { browserApi } from "@/lib/api/browser";
import { noContentSchema } from "@/lib/api/schemas";

function initials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

/**
 * The admin portal frame (reference-admin.html): a sidebar with the pages this role may
 * open (fixed from 1024px, a slide-in menu on phones), and a top bar with the
 * environment badge and the role.
 */
export function AdminShell({
  pages,
  counts = {},
  role,
  name,
  environment,
  children,
}: {
  pages: AdminPage[];
  /** Open items per page slug, shown beside the menu entry. */
  counts?: Record<string, number>;
  role: AdminRole;
  name: string;
  environment: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);

  // Ends only the admin session; the normal one stays, so they land back in the app.
  async function signOut() {
    setLeaving(true);
    try {
      await browserApi("/admin/sign-out", noContentSchema, { method: "POST" });
      router.push("/home");
      router.refresh();
    } catch {
      setLeaving(false);
    }
  }
  // Opening a page closes the phone menu.
  const [shownPath, setShownPath] = useState(pathname);
  if (pathname !== shownPath) {
    setShownPath(pathname);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const groups = pages.reduce<Map<string, AdminPage[]>>((all, page) => {
    all.set(page.group, [...(all.get(page.group) ?? []), page]);
    return all;
  }, new Map());

  return (
    <div className="bg-panel min-h-dvh">
      <a
        href="#admin-main"
        className="focus:border-ink focus:bg-bg rounded-control sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[90] focus:border focus:px-4 focus:py-2"
      >
        Skip to content
      </a>
      {open ? (
        <div
          aria-hidden
          onClick={() => setOpen(false)}
          className="bg-ink/40 fixed inset-0 z-50 lg:hidden"
        />
      ) : null}
      <aside
        id="admin-menu"
        className={cx(
          "border-line bg-bg fixed inset-y-0 left-0 z-[60] flex w-[264px] flex-col border-r",
          open ? "flex" : "hidden lg:flex",
        )}
      >
        <div className="border-line flex h-[60px] items-center gap-2 border-b px-4">
          <Logo />
          <span className="bg-ink text-bg rounded-chip px-1.5 py-0.5 font-mono text-[10px] uppercase">
            Admin
          </span>
        </div>
        <nav aria-label="Admin" className="flex-1 overflow-y-auto px-2.5 py-3">
          {[...groups.entries()].map(([group, items]) => (
            <div key={group || "top"} className="mb-2">
              {group ? (
                <p className="text-mono text-muted mx-2 mt-3 mb-1.5 font-mono uppercase">{group}</p>
              ) : null}
              <ul className="flex flex-col gap-0.5">
                {items.map((page) => {
                  const href = hrefOf(page);
                  const current = page.slug ? pathname.startsWith(href) : pathname === "/admin";
                  return (
                    <li key={page.slug}>
                      <Link
                        href={href}
                        aria-current={current ? "page" : undefined}
                        aria-label={
                          counts[page.slug]
                            ? `${page.label}, ${counts[page.slug]} waiting`
                            : undefined
                        }
                        className={cx(
                          "text-meta-lg flex min-h-11 items-center rounded-lg border-l-2 px-2.5 lg:min-h-10",
                          current
                            ? "bg-panel text-ink border-green font-medium"
                            : "text-ink-2 hover:bg-panel border-transparent",
                        )}
                      >
                        {page.label}
                        {counts[page.slug] ? (
                          <span className="bg-ink text-bg rounded-chip ml-auto px-1.5 py-0.5 font-mono text-[10px]">
                            {counts[page.slug]}
                          </span>
                        ) : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
        <p className="border-line text-meta text-muted border-t px-4 py-3">
          Every change needs a reason and is recorded.
        </p>
      </aside>

      <div className="min-w-0 lg:ml-[264px]">
        <header className="border-line bg-bg sticky top-0 z-40 flex h-[60px] items-center gap-2.5 border-b px-3 lg:h-16 lg:px-6">
          <button
            type="button"
            aria-controls="admin-menu"
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((value) => !value)}
            className="border-line bg-bg rounded-input flex size-11 items-center justify-center border lg:hidden"
          >
            <span aria-hidden className="text-[18px] leading-none">
              {open ? "×" : "≡"}
            </span>
          </button>
          <span className="border-amber-edge bg-amber-tint text-amber-ink rounded-[6px] border border-dashed px-2 py-0.5 font-mono text-[10px] uppercase">
            {environment}
          </span>
          <form action="/admin/users" method="get" role="search" className="min-w-0 flex-1">
            <input
              name="q"
              type="search"
              aria-label="Search users by name or email"
              placeholder="Search users by name or email"
              className="rounded-input border-muted-2 bg-bg text-ink sm:text-body h-11 w-full max-w-[420px] border px-3 text-[16px] lg:h-10"
            />
          </form>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-meta-lg text-ink-2 max-sm:sr-only">{ROLE_LABELS[role]}</span>
            <span
              aria-hidden
              className="bg-ink text-bg flex size-[34px] items-center justify-center rounded-full text-[12px] font-medium"
            >
              {initials(name)}
            </span>
            <button
              type="button"
              onClick={signOut}
              disabled={leaving}
              className="text-meta-lg text-ink rounded-control hover:bg-panel inline-flex min-h-11 items-center px-2 font-medium whitespace-nowrap lg:min-h-10"
            >
              {leaving ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </header>
        <main id="admin-main" className="mx-auto max-w-[1280px] px-3 pt-4 pb-20 lg:px-8 lg:pt-7">
          {children}
        </main>
      </div>
    </div>
  );
}

/** A page heading in the reference's style: two-tone, with a short description. */
export function AdminHeading({
  lead,
  rest,
  description,
  actions,
}: {
  lead: string;
  rest: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 className="font-display tracking-display text-[30px] leading-[1.05] font-extrabold md:text-[38px] lg:text-[44px]">
          {lead} <span className="text-muted-2">{rest}</span>
        </h1>
        {description ? (
          <p className="text-meta-lg text-ink-2 mt-1 max-w-[640px]">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

/** For people who aren't admins, or whose role doesn't include a page. */
export function AccessDenied({ reason }: { reason: string }) {
  return (
    <main className="bg-panel flex min-h-dvh items-center justify-center px-4">
      <div className="border-line bg-bg rounded-panel flex max-w-md flex-col gap-3 border p-6">
        <h1 className="font-display tracking-display text-[26px] leading-tight font-extrabold">
          No access
        </h1>
        <p className="text-ink-2">{reason}</p>
        <Link href="/home" className="text-green text-meta-lg font-medium underline">
          Back to the app
        </Link>
      </div>
    </main>
  );
}
