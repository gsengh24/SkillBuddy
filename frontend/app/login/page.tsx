import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { LoginForm } from "@/components/auth/login-form";
import { Card } from "@/components/ui/card";
import { Logo } from "@/components/ui/logo";
import { TextLink } from "@/components/ui/text-link";
import { messageForCode } from "@/lib/auth/messages";
import { getAuthMethods } from "@/lib/auth/methods";
import { safeNextPath } from "@/lib/auth/redirect";
import { getCurrentUser } from "@/lib/auth/session";
import { brand } from "@/lib/brand";

export const metadata: Metadata = { title: "Sign in" };
export const dynamic = "force-dynamic";

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

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-lg flex-col justify-center gap-6 px-4 py-10">
      <Link href="/" aria-label={`${brand.name} home`} className="self-start">
        <Logo />
      </Link>
      <Card className="p-6 sm:p-8">
        <LoginForm
          nextPath={nextPath}
          google={methods.google ? { domains: methods.google_domains } : undefined}
          initialError={initialError}
        />
      </Card>
      <TextLink href="/" tone="muted" className="text-small self-start">
        Back to {brand.name}
      </TextLink>
    </main>
  );
}
