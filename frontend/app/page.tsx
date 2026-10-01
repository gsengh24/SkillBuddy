import { Suspense } from "react";

import { ApiStatusFallback, ApiStatusIndicator } from "@/components/api-status";
import { ButtonLink } from "@/components/ui/button";
import { HeroPanel } from "@/components/ui/hero-panel";
import { Logo } from "@/components/ui/logo";
import { brand } from "@/lib/brand";

// The status indicator reflects the API right now, so never serve a cached render.
export const dynamic = "force-dynamic";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-3xl flex-col justify-center gap-8 px-4 py-12">
      <Logo />
      <HeroPanel className="p-8">
        <h1 className="text-h1 max-w-lg text-balance">{brand.tagline}</h1>
        <p className="max-w-lg text-pretty">{brand.description}</p>
        <div className="pt-2">
          <ButtonLink href="/login">Sign in or create an account</ButtonLink>
        </div>
      </HeroPanel>

      <section aria-label="System status">
        <Suspense fallback={<ApiStatusFallback />}>
          <ApiStatusIndicator />
        </Suspense>
      </section>
    </main>
  );
}
