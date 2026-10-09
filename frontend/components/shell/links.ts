/**
 * The three places in the app, the same on desktop (top bar) and phones (bottom nav).
 * Chats (/messages/...) belong to Home, which lists requests and messages together.
 */
export const APP_LINKS = [
  { href: "/home", label: "Home", match: ["/messages"] },
  { href: "/spaces", label: "Spaces", match: [] },
  { href: "/you", label: "You", match: ["/settings"] },
] as const;

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** The place the current page belongs to, if any. */
export function currentPlace(pathname: string) {
  return APP_LINKS.find((link) =>
    [link.href, ...link.match].some((path) => isActive(pathname, path)),
  );
}

/** Round 44px icon link (the bell). */
export const ICON_LINK =
  "border-line bg-bg text-ink hover:bg-panel relative inline-flex size-11 shrink-0 items-center justify-center rounded-full border";

/** The green "something new" dot on an icon link. */
export const DOT = "bg-green absolute top-2 right-2.5 size-2 rounded-full";
