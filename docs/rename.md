# Rename: Skill Buddy becomes Cynergi

October 2026 (design spec section 10, prompts 8 and 10). This page lists what changed, what was kept and why, and the steps only the owner can do.

## What changed

- **Web app:**
  - `frontend/lib/brand.ts`: `name` and `displayName` are "Cynergi" and `wordmark` is "cynergi". Everything the app shows reads from there:
    - page titles (`%s · Cynergi`) and metadata;
    - "Sign in to Cynergi" and "Back to Cynergi" on the sign-in page;
    - the landing page and its Open Graph image;
    - the logo;
    - the web app manifest.
  - Icons: `app/icon.svg` and `app/apple-icon.tsx` draw the placeholder four-dot mark, and `app/manifest.ts` is the web app manifest. The old `app/favicon.ico` (the framework default) was removed.
  - The sign-in page uses the new logo.
  - A test (`frontend/lib/brand.test.ts`) fails if "Skill Buddy" comes back anywhere in the web app's code.
- **Privacy and terms** (#80, owner review): the name in both pages, and the terms version `2026-10-08-draft`.
- **Docs:**
  - the README title and intro, and the project description in `CLAUDE.md`;
  - the Codespaces name (`.devcontainer`);
  - the opening line of the pre-launch checklist;
  - the consent-screen app name in the deployment plan;
  - the title of the older design-system page.
- **ADRs 0007, 0008 and 0009** keep their text, with a one-line note at the top that the product was renamed.

## What was kept, and why

| Kept | Why |
| --- | --- |
| The GitHub repository `gsengh24/SkillBuddy` | Renaming it changes every clone URL and link; not part of this change. |
| The Render service `skillbuddy-api`, the Vercel project, the Neon project `skill-buddy-staging`, the Cloudflare Worker `skill-buddy-tick`, and the Google Cloud projects `skill-buddy-mail` and `skillbuddy-signin` | Real resources: their names are part of URLs and settings. The deployment plan still names them as they are. |
| `infra/cloudflare-tick/worker.js` (a comment and its "Skill Buddy scheduler" reply) | The deployed Worker is copied by hand from this file. Changing only the repo would make the two differ. Change it the next time the Worker is redeployed. |
| Environment variable names, database names | None of them contains the name. |
| **Cookies and storage keys** | None contains the old name: the cookies are `session` and `csrf_token`, and the web app uses no localStorage or sessionStorage. Nothing to rename, and nobody is signed out. |
| History: `docs/phase-0-exit-report.md`, the ADR bodies, `docs/design/design-spec.md` and `docs/design/claude-code-prompts.md` | Records of what happened under the old name. |

## Emails

Email sender names and subjects come from the backend's `app_name` setting, so **they change when the owner sets `APP_NAME=Cynergi` on Render**, with no repo change. Until then they say "Skill Buddy". With the new setting the texts read:

| Email | Old text | New text |
| --- | --- | --- |
| Sign-in code: subject | Your Skill Buddy sign-in code | Your Cynergi sign-in code |
| Sign-in code: body | Your Skill Buddy sign-in code is: … / If you didn't try to sign in to Skill Buddy, you can ignore this email. | Your Cynergi sign-in code is: … / If you didn't try to sign in to Cynergi, you can ignore this email. |
| Intro emails: subject | Someone would like to meet you on Skill Buddy / Your intro was accepted on Skill Buddy | … on Cynergi |
| Intro emails: body | You have a new intro on Skill Buddy. … / Someone accepted your intro on Skill Buddy. … | … on Cynergi. … |
| Intro emails: footer (consent wording) | You can turn these emails off in Skill Buddy: Account settings, Emails. | You can turn these emails off in Cynergi: Account settings, Emails. |
| Moderator alert (moderation wording) | Reports waiting on Skill Buddy | Reports waiting on Cynergi |
| Every email: sender name | Skill Buddy | Cynergi |

Only the name changes. Every other word stays the same.

## The backend PR (done)

The backend PR (owner review) did:
- changed the `app_name` default in `backend/app/core/config.py` to "Cynergi";
- updated `APP_NAME` in `backend/.env.example`;
- updated the backend tests that check the default name (`tests/unit/test_config.py` and `tests/unit/test_gmail_sender.py`);
- regenerated `docs/api/openapi.json`, whose title is now "Cynergi API".

The `TERMS_VERSION` default (`2026-10-05-draft`) was not changed: Render's setting is what counts, and the owner set it.

## Steps only the owner can do

1. **Render, the API service, Environment:** set `APP_NAME=Cynergi`, and set `TERMS_VERSION=2026-10-08-draft` so it matches the version the legal pages show.
2. **Google Cloud, the sign-in project's consent screen:** change the app name to Cynergi and upload the logo **before** setting the app to "In production".
3. **Gmail:** change the sender display name to Cynergi.
4. **UptimeRobot:** rename the monitor's label.
