## What changed

<!-- What and why, in a few bullets. Link the issue or ARCHITECTURE.md section if relevant. -->

## How it was verified

<!-- CI jobs that passed (Backend, Frontend, Docker images) and any local checks run
     (ruff, mypy, unit tests, frontend lint/typecheck). New tests added. -->

## Not verified

<!-- Anything not covered by CI or local checks, e.g. behaviour only visible on staging.
     Write "Nothing" if everything was verified. -->

## Checklist

- [ ] Title follows Conventional Commits; branch is a short-lived feature branch.
- [ ] CI is green (Backend, Frontend, Docker images, Smoke, Secret scan); no check was
      disabled or weakened.
- [ ] New or changed endpoints have tests (success and failure paths).
- [ ] Database changes have an Alembic migration that downgrades cleanly.
- [ ] New growing tables: retention policy and estimated growth stated above, row added to
      `docs/storage-budget.md`.
- [ ] New settings are documented in `.env.example` and validated; secrets live only in the
      hosting dashboard.
- [ ] No secrets or personal data in code, tests, fixtures or logs.
- [ ] Model calls go only through the AI gateway; model output is schema-validated.
- [ ] Significant decisions have an ADR in `docs/adr/`.
