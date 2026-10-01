# Free-tier limits

Living record of every external service we use, on its free tier (see the zero-cost
constraint, [ADR 0004](adr/0004-zero-cost-constraint.md)). Providers change their limits
without notice: re-check the source before relying on a row, and update the date.

**Adding a service:** check its current free tier first, then add a row with the plan,
limits, catches (sleeping, size caps, rate limits, data-use terms, card requirement) and
the date checked. If it needs a credit card, it cannot be used.

| Service | Plan | Limits | Catches | Checked |
| --- | --- | --- | --- | --- |
| GitHub Actions | Free, public repository | Standard GitHub-hosted runners are free for public repos. Up to 20 concurrent jobs; 6 hours per job. Cache: 10 GB per repository. (Private repos would get only 2,000 minutes and 500 MB artifact storage per month.) | Free only while the repo is **public**; making it private switches to the 2,000-minute quota, after which runs are blocked (no payment method). Larger runners are always billed; never use them. | 2026-10-01 |
| GitHub Codespaces | GitHub Free personal account | 120 core-hours and 15 GB-month storage per month. A 2-core machine (our devcontainer's 8 GB size) uses 2 core-hours per hour, so about **60 hours/month**. Idle timeout 30 min by default (5–240 min allowed). | Usage is **blocked** for the rest of the month once the quota is used (no payment method). Stopped codespaces and prebuilds still use storage; delete old codespaces. Prebuilds would also use Actions minutes and storage, so we don't use them. | 2026-10-01 |
| Dependabot | Free (all repositories) | Version and security updates run on standard runners and do not count towards Actions minutes. We cap open PRs at 5 per ecosystem in `.github/dependabot.yml`. | Each Dependabot PR triggers our full CI run. Keep the open-PR limit low and group minor/patch updates. Dependabot on larger runners would be billed. | 2026-10-01 |

Planned staging providers (Vercel Hobby, Render Free / Koyeb Free, Neon Free, Upstash Free)
are evaluated in [deployment-plan.md](deployment-plan.md); add each here when it is
actually adopted.

**Sources:** GitHub Docs: Actions billing and limits, Codespaces billing and timeout
settings, Dependabot on GitHub Actions runners.
