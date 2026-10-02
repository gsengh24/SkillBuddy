/** Mirrors the API's limits (backend/app/schemas/profile.py); the API is the real check. */
export const ABOUT_MIN = 20;
export const ABOUT_MAX = 2000;
export const NAME_MAX = 60;
export const MAX_LINKS = 3;
export const PHRASE_MAX = 60;
export const MAX_PHRASES = 8;
export const TIMEZONE_PATTERN = /^(UTC|[A-Za-z]+(\/[A-Za-z0-9_+-]+){1,2})$/;
export const LINK_PATTERN = /^https:\/\/[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+(:\d{1,5})?(\/\S*)?$/;

/** Languages offered on the form, as BCP 47 tags. */
export const LANGUAGES: { code: string; label: string }[] = [
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "pa", label: "Punjabi" },
  { code: "ur", label: "Urdu" },
  { code: "bn", label: "Bengali" },
  { code: "mr", label: "Marathi" },
  { code: "gu", label: "Gujarati" },
  { code: "ta", label: "Tamil" },
  { code: "te", label: "Telugu" },
  { code: "kn", label: "Kannada" },
];

/** Share of the profile filled in, 0 to 100, for the sidebar card. */
export function profileCompleteness(
  profile: {
    about_text: string;
    parse_status: string;
    links: string[];
    languages: string[];
    timezone: string | null;
  } | null,
): number | null {
  if (!profile) return null;
  let value = profile.about_text.trim() ? 50 : 0;
  if (profile.parse_status === "parsed") value += 20;
  if (profile.links.length) value += 10;
  if (profile.languages.length) value += 10;
  if (profile.timezone) value += 10;
  return value;
}
