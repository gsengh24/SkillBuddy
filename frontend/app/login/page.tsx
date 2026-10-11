import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ApplyForm } from "@/components/auth/apply-form";
import { LoginForm } from "@/components/auth/login-form";
import { Logo } from "@/components/ds/logo";
import { messageForCode } from "@/lib/auth/messages";
import { getAuthMethods } from "@/lib/auth/methods";
import { safeNextPath } from "@/lib/auth/redirect";
import { getCurrentUser } from "@/lib/auth/session";
import { brand } from "@/lib/brand";

export const metadata: Metadata = { title: "Sign in" };
export const dynamic = "force-dynamic";

const CARD = "border-line bg-panel/70 w-full max-w-sm rounded-2xl border p-6 sm:p-8";
// Soft green glow from the top right and bottom left, on the dark ground.
const GLOW = {
  backgroundImage:
    "radial-gradient(60% 50% at 85% 0%, color-mix(in srgb, var(--green) 16%, transparent), transparent), radial-gradient(50% 40% at 0% 100%, color-mix(in srgb, var(--green) 10%, transparent), transparent)",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[]; error?: string | string[] }>;
}) {
  const { next, error } = await searchParams;
  const nextPath = safeNextPath(typeof next === "string" ? next : undefined);
  // Already signed in: skip the form. If the API is unreachable, show the form anyway.
  const user = await getCurrentUser().catch(() => null);
  if (user) redirect(nextPath);
  const methods = await getAuthMethods();
  // Google sign-in sends people back here with a stable error code (ADR 0011).
  const initialError = messageForCode(typeof error === "string" ? error : undefined);
  const inviteOnly = methods.signup_mode === "invite_only";

  return (
    <div className="bg-bg flex min-h-dvh flex-col" style={GLOW}>
      <header className="flex items-center justify-between px-6 py-6">
        <Link href="/" aria-label={`${brand.name} home`}>
          <Logo />
        </Link>
        <Link href="/" className="text-small text-muted hover:text-ink">
          <span aria-hidden="true">←</span> Back to {brand.name}
        </Link>
      </header>
      <main className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-8">
        <div className={CARD}>
          <LoginForm
            nextPath={nextPath}
            google={methods.google ? { domains: methods.google_domains } : undefined}
            initialError={initialError}
            inviteOnly={inviteOnly}
          />
        </div>
        {inviteOnly ? (
          <div className={CARD}>
            <ApplyForm />
          </div>
        ) : null}
      </main>
      <footer className="text-muted flex items-center justify-center gap-5 px-6 py-6 font-mono text-[11px] tracking-wider uppercase">
        <span>© 2026 {brand.name}</span>
        <Link href="/terms" className="hover:text-ink">
          Terms
        </Link>
        <Link href="/privacy" className="hover:text-ink">
          Privacy
        </Link>
      </footer>
    </div>
  );
}
