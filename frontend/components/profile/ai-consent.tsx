import Link from "next/link";

import { textLinkClasses } from "@/components/ui/text-link";

/**
 * The AI-processing consent line, word for word from ADR 0007 section 5. Changing it needs
 * the owner's sign-off and a new AI_CONSENT_VERSION on the API, so everyone agrees again.
 */
export function AiConsentText() {
  return (
    <>
      Your description is read by AI to find and explain your matches. We send only this text (never
      your name, email or contact details) to our AI providers, Groq and Cloudflare, and their terms
      don&apos;t allow them to train on it.{" "}
      <Link href="/privacy#ai" className={textLinkClasses()}>
        How we use AI
      </Link>
    </>
  );
}
