import Link from "next/link";
import type { ReactNode } from "react";

import { brand } from "@/lib/brand";

import { cx } from "../ui/cx";
import { ButtonLink } from "./button";
import { Logo } from "./logo";
import { PixelPattern } from "./pixel-pattern";

/** "© 2026 Cynergi": the legal row the owner approved (no "All rights reserved"). */
const COPYRIGHT = `© 2026 ${brand.displayName}`;

/**
 * The green CTA band: a white 800 headline whose second half is mint, a white button, and
 * a static pixel pattern in the corner.
 */
export function CtaBand({
  lead,
  rest,
  action,
  headingLevel = 2,
  className,
}: {
  lead: string;
  rest: string;
  action: { href: string; label: string };
  headingLevel?: 2 | 3;
  className?: string;
}) {
  const Heading = `h${headingLevel}` as const;
  return (
    <div
      className={cx(
        "bg-green rounded-panel relative flex flex-col gap-5 overflow-hidden px-5 py-6 lg:flex-row lg:items-center lg:justify-between lg:p-12",
        className,
      )}
    >
      <Heading className="font-display text-bg max-w-[420px] text-[28px] leading-none font-extrabold tracking-[-0.05em] lg:max-w-[560px] lg:text-[44px]">
        {lead} <span className="text-mint-text">{rest}</span>
      </Heading>
      <ButtonLink href={action.href} variant="white" className="self-start lg:self-center">
        {action.label}
      </ButtonLink>
      <PixelPattern onGreen className="absolute right-4 bottom-3" />
    </div>
  );
}

export type NavLink = { href: string; label: string };

const FOOTER_LINK =
  "text-meta-lg text-muted hover:text-ink inline-flex min-h-11 items-center pointer-fine:min-h-7";

/** Site footer: brand and one line on the left, link columns, then the legal row. */
export function Footer({
  productLinks,
  className,
}: {
  productLinks: NavLink[];
  className?: string;
}) {
  const columns: { title: string; links: NavLink[] }[] = [
    { title: "Product", links: productLinks },
    {
      title: "Legal",
      links: [
        { href: "/privacy", label: "Privacy" },
        { href: "/terms", label: "Terms" },
      ],
    },
    { title: "Contact", links: [{ href: `mailto:${brand.contactEmail}`, label: "Contact us" }] },
  ];
  return (
    <footer className={cx("border-line mt-6 border-t pt-7 pb-6 lg:pt-14 lg:pb-8", className)}>
      <div className="grid grid-cols-2 gap-6 sm:grid-cols-4 lg:grid-cols-[2fr_1fr_1fr_1fr]">
        <div className="text-muted col-span-2 max-w-[30ch] sm:col-span-1">
          <Logo className="mb-2.5" />
          <p>{brand.summary}</p>
        </div>
        {columns.map((column) => (
          <nav key={column.title} aria-label={column.title}>
            <h2 className="text-meta mb-2.5 font-medium">{column.title}</h2>
            <ul>
              {column.links.map((link) => (
                <li key={link.href}>
                  {link.href.startsWith("mailto:") ? (
                    <a href={link.href} className={FOOTER_LINK}>
                      {link.label}
                    </a>
                  ) : (
                    <Link href={link.href} className={FOOTER_LINK}>
                      {link.label}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <p className="border-line text-meta text-muted mt-6 border-t pt-4">{COPYRIGHT}</p>
    </footer>
  );
}

/**
 * The desktop top bar: logo on the left, links, and actions on the right (for example
 * Sign in as ghost and Get started as primary). Links hide below 1024px; phones use the
 * bottom nav in the app.
 */
export function TopBar({
  homeHref = "/",
  links,
  currentHref,
  actions,
  className,
}: {
  homeHref?: string;
  links: NavLink[];
  currentHref?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cx(
        "border-line flex h-[60px] items-center justify-between gap-4 border-b lg:h-[68px]",
        className,
      )}
    >
      <Link href={homeHref} aria-label={`${brand.wordmark} home`} className="rounded-control">
        <Logo />
      </Link>
      {links.length ? (
        <nav aria-label="Main" className="text-meta-lg text-muted hidden gap-7 lg:flex">
          {links.map((link) => {
            const current = link.href === currentHref;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={current ? "page" : undefined}
                className={cx(
                  "border-b-2 py-1.5",
                  current
                    ? "border-green text-ink font-medium"
                    : "hover:text-ink border-transparent",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      ) : null}
      {actions ? <div className="flex items-center gap-2.5">{actions}</div> : null}
    </header>
  );
}

/** A two-tone display headline: the first part in ink, the rest in muted-2 (large text). */
export function TwoToneHeadline({
  lead,
  rest,
  as: Heading = "h2",
  size = "headline",
  onTint = false,
  className,
}: {
  lead: string;
  rest: string;
  as?: "h1" | "h2" | "h3";
  size?: "hero" | "headline";
  /** On green tint the rest uses muted: muted-2 is under 3:1 there. */
  onTint?: boolean;
  className?: string;
}) {
  return (
    <Heading
      className={cx(
        "font-display",
        size === "hero" ? "text-hero lg:text-hero-lg" : "text-headline lg:text-headline-lg",
        className,
      )}
    >
      {lead}
      <br />
      <span className={onTint ? "text-muted" : "text-muted-2"}>{rest}</span>
    </Heading>
  );
}
