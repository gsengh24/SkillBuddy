/**
 * Removes personal details from resume or pasted text, in the browser, before anything else
 * reads it (ADR 0023): email addresses, links, phone numbers, address lines and the name at
 * the top. Nothing here is sent anywhere; the cleaned text is only searched for skill names
 * on the device and then thrown away. Stripping first also stops a surname such as "Rust"
 * from becoming a suggested skill.
 */

export const PASTE_MAX = 2000;

const EMAIL = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g;
const LINK =
  /\b(?:https?:\/\/|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|in|io|dev|me|org|net|ai|app)\b(?:\/\S*)?/gi;
// A run of digits with +, spaces, dots, dashes or brackets between them; it counts as a phone
// number from 10 digits, so years and date ranges ("2023 - 2025") stay.
const DIGIT_RUN = /\+?\d[\d\s().-]{6,}\d/g;
const PHONE_DIGITS = 10;
const ADDRESS_LINE = /^\s*(?:address|addr\.?|location|dob|date of birth)\b.*$/gim;
// An Indian PIN code (6 digits) or a US ZIP, on a line that reads like an address.
const POSTCODE_LINE = /^.*\b\d{6}\b.*$|^.*,\s*[A-Z]{2}\s+\d{5}\b.*$/gm;
const NAME_LABEL = /^\s*name\s*[:-].*$/gim;
// A header name: one to four words, letters only (initials and hyphens allowed).
const LOOKS_LIKE_NAME = /^\p{Lu}[\p{L}'.-]*(?:\s+\p{Lu}[\p{L}'.-]*){0,3}$/u;

export type Redacted = { text: string; removed: number };

function count(text: string, pattern: RegExp): number {
  return text.match(pattern)?.length ?? 0;
}

export function redact(raw: string): Redacted {
  let removed = 0;
  let text = raw.replace(/\r\n?/g, "\n");

  // The name at the top: the first line with words on it, when it looks like a name and
  // more lines follow (a one-line paste is a sentence, not a header).
  const lines = text.split("\n");
  const first = lines.findIndex((line) => line.trim().length > 0);
  const head = lines[first];
  const more = lines.slice(first + 1).some((line) => line.trim().length > 0);
  if (head !== undefined && more && LOOKS_LIKE_NAME.test(head.trim())) {
    lines[first] = "";
    removed += 1;
    text = lines.join("\n");
  }

  for (const pattern of [EMAIL, LINK, NAME_LABEL, ADDRESS_LINE, POSTCODE_LINE]) {
    removed += count(text, pattern);
    text = text.replace(pattern, " ");
  }
  text = text.replace(DIGIT_RUN, (run) => {
    if (run.replace(/\D/g, "").length < PHONE_DIGITS) return run;
    removed += 1;
    return " ";
  });
  return { text: text.replace(/[ \t]+/g, " ").trim(), removed };
}
