import { legal } from "./legal";

/**
 * Product identity. The product name lives here and only here on the frontend.
 *
 * The product is Cynergi (formerly Skill Buddy; docs/rename.md). `name` and `displayName`
 * are the same name, kept as two fields so older and newer code read naturally; the logo
 * uses the lowercase `wordmark`.
 */
export const brand = {
  /** The product name, in titles, metadata and running text. */
  name: "Cynergi",
  /** The same name (newer code uses this field). */
  displayName: "Cynergi",
  /** The new logo's wordmark: always lowercase. */
  wordmark: "cynergi",
  tagline: "Find the people worth building with.",
  description:
    "Describe who you are and what you want to do. We introduce you to the few people worth talking to, and tell you why.",
  /** One line about the product, for the footer. */
  summary: "Find people to build, learn and explore with.",
  /** The contact address. Its only definition stays in lib/legal.ts. */
  contactEmail: legal.contactEmail,
} as const;
