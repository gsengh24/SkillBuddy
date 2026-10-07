/** The four places in the app, the same on desktop (top bar) and phones (bottom nav). */
export const APP_LINKS = [
  { href: "/home", label: "Home" },
  { href: "/spaces", label: "Spaces" },
  { href: "/saved", label: "Saved" },
  { href: "/profile", label: "You" },
] as const;

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Round 44px icon link (bell, messages). */
export const ICON_LINK =
  "border-line bg-bg text-ink hover:bg-panel relative inline-flex size-11 shrink-0 items-center justify-center rounded-full border";

/** The green "something new" dot on an icon link. */
export const DOT = "bg-green absolute top-2 right-2.5 size-2 rounded-full";
