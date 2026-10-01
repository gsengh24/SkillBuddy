# Contributing

## Setup

1. Open the repository in GitHub Codespaces and start the stack with
   `docker compose up --build --detach --wait` (see "Develop in Codespaces" in
   [README.md](README.md)).
2. Install the git hooks (requires [uv](https://docs.astral.sh/uv/)):
   ```bash
   cd backend && uv sync && uv run pre-commit install   # done automatically in Codespaces
   ```
3. Read [CLAUDE.md](CLAUDE.md) for the coding standards and [docs/adr](docs/adr) for past
   decisions.

## Branching

- `main` is always releasable. It is protected: no direct pushes, CI must pass, and at
  least one approving review is required once the team has more than one member.
- Work happens on short-lived branches off `main`, named `<type>/<short-description>`,
  for example `feat/profile-parsing`, `fix/readiness-timeout`, `chore/bump-fastapi`.
- Keep branches small and merge them within a few days. Rebase on `main` rather than merging
  `main` into your branch.
- Pull requests are squash-merged; the PR title becomes the commit message, so it must
  follow the commit style below.

## Commit style: Conventional Commits

```
<type>(<optional scope>): <imperative summary, max ~72 chars>

<optional body: what and why, not how>

<optional footer: BREAKING CHANGE: ..., Refs: #123>
```

Types: `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `build`, `ci`, `chore`, `revert`.
Scopes are optional and name the area: `api`, `worker`, `db`, `web`, `infra`, `ci`, `docs`.

Examples:

```
feat(api): add PUT /me/profile
fix(worker): make embedding job idempotent on retry
build(db): add requests table migration
```

Mark breaking changes to the API, database or configuration with `!` (`feat(api)!: ...`)
and a `BREAKING CHANGE:` footer.

## Pull request checklist

Copy this into the PR description and tick every item that applies.

- [ ] Title follows Conventional Commits.
- [ ] The change is scoped to one concern; unrelated refactors are in separate PRs.
- [ ] CI is green (Backend, Frontend, Docker images, Smoke, Secret scan); no check was
      disabled or weakened.
- [ ] The description says what changed, how it was verified and what was not verified.
- [ ] Every new or changed endpoint has tests (success and failure paths).
- [ ] Every database change has an Alembic migration, and it downgrades cleanly.
- [ ] New settings are added to `backend/.env.example` (or `frontend/.env.example`) with a
      comment, and validated in `config.py` / `lib/env.ts`.
- [ ] No secrets, tokens, personal data or real user content in code, tests, fixtures or logs.
- [ ] LLM or embedding calls go only through the AI gateway module; model output is
      schema-validated before use.
- [ ] Architecturally significant decisions have an ADR in `docs/adr/`.
- [ ] User-facing behaviour changes are reflected in docs.

## Code review

Reviewers check correctness first, then security and privacy, then clarity. Prefer
suggesting a concrete change over asking an open question. Approve when the code is
better than before and safe to deploy, even if it is not how you would have written it.
