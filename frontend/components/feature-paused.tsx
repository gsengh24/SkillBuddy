import { ButtonLink } from "@/components/ds/button";

/** Shown in place of a feature an admin has switched off for everyone (A6). */
export function FeaturePaused({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h1 className="text-headline lg:text-headline-lg">{title}</h1>
      <p className="text-ink-2">{children}</p>
      <ButtonLink href="/home" variant="outline" className="self-start">
        Back to Home
      </ButtonLink>
    </div>
  );
}
