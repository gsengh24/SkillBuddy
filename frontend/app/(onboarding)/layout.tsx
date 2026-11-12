/**
 * Onboarding has no app navigation (mockups 01–04): the logo, the step and the page only.
 * Each page checks the session itself and redirects signed-out visitors to /login.
 */
export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
