## What and why

<!-- One or two sentences. Link the issue or ARCHITECTURE.md section if relevant. -->

## How it was tested

<!-- Commands run, new tests added, manual checks. -->

## Checklist

- [ ] Title follows Conventional Commits.
- [ ] Backend and frontend lint/typecheck and the backend tests pass (the `docker compose run`
      commands in README.md, or the equivalent `make lint` / `make test`).
- [ ] New or changed endpoints have tests (success and failure paths).
- [ ] Database changes have an Alembic migration that downgrades cleanly.
- [ ] New settings are documented in `.env.example` and validated.
- [ ] No secrets or personal data in code, tests, fixtures or logs.
- [ ] Model calls go only through the AI gateway; model output is schema-validated.
- [ ] Significant decisions have an ADR in `docs/adr/`.
