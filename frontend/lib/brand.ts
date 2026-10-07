import { legal } from "./legal";

/**
 * Product identity. The product name lives here and only here on the frontend.
 *
 * The product is being renamed to Cynergi (ADR 0014, docs/design/design-spec.md section
 * 10). `name` is what pages, titles and the legal pages say today; it changes to
 * `displayName` in the rename PRs (the legal pages in one PR, everything else in another),
 * each reviewed by the owner. The new logo already uses `wordmark`.
 */
export const brand = {
  /** The name shown in titles, sign-in text and the legal pages until the rename PRs. */
  name: "Skill Buddy",
  /** The new product name, in running text. */
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
