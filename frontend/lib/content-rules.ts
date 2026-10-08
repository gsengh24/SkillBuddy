/** The automatic content rules (A7), in plain words. Shared by the admin page and the
 * "we removed some text" notice. */
export const CONTENT_RULES: Record<string, { label: string; hint: string; reason: string }> = {
  profanity: {
    label: "Profanity list",
    hint: "Flag words from the list",
    reason: "offensive language",
  },
  links_in_bios: {
    label: "Links in bios",
    hint: "Links and short links in the about text",
    reason: "a link in your about text",
  },
  contact_details: {
    label: "Contact details in text",
    hint: "Phone numbers and emails in requests, bios and intros",
    reason: "contact details",
  },
  repeated_intros: {
    label: "Repeated intros",
    hint: "The same note sent to many people in a day",
    reason: "the same intro sent to many people",
  },
  prompt_injection: {
    label: "Prompt injection",
    hint: "Text that tries to instruct the AI",
    reason: "text that tries to instruct the AI",
  },
};
