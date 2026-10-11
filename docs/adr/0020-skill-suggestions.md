# 20. Skill suggestions from a bundled list

- **Status:** Accepted
- **Date:** 2026-10-12
- **Relates to:** [ADR 0004](0004-zero-cost-constraint.md), [ADR 0007](0007-ai-gateway.md)

## Context

People describe themselves in free text, and the LLM extracts "can help with" and "wants to
learn" tags. The same skill ends up spelled many ways ("JS", "javascript", "Java Script"),
which makes tags harder to compare and the You page slower to fill in. A reference note
suggested borrowing a large skills taxonomy through an API (Lightcast Open Skills, Google
Cloud Talent Solution, O*NET) and forcing a pick from an autocomplete.

## Decision

- **Suggest, do not force.** The skill tag editors on the You page show matching names as
  people type. They can pick one or press Enter to add their own words. Interests and hobbies
  are core to the product, and no occupational taxonomy covers "sourdough" or "chess", so a
  forced pick would block real use. Tags stay plain strings; nothing is stored about whether
  a tag came from the list.
- **Bundled, not called.** The list lives in the repo (`backend/app/data/`): O*NET's
  "Technology Skills" names (CC BY 4.0, filtered by `backend/scripts/build_skill_list.py`)
  plus a short hand-written list of general skills and interests. `GET /api/v1/skills/suggest`
  searches it in memory: whole-name prefix first, then a word prefix, then (from three
  characters) any substring, in list order.
- **Why not a live API.** Google Cloud Talent Solution is paid and needs a card (ADR 0004).
  Lightcast and the O*NET web service need an account, add a runtime dependency and a
  quota to watch, and would receive what people type. A bundled file has no quota, works in
  CI and sends nothing anywhere.
- **No database, no migration, no AI.** The endpoint needs sign-in (so it is not an open
  list) and makes no database write, so it adds no storage and needs no rate-limit counter.
  The editor waits 200 ms after typing stops, and a failed search just shows no suggestions.

## Consequences

- The list is small (about 930 names). Coverage of non-technical skills grows by editing
  `skills_curated.txt`; a larger taxonomy such as ESCO could be added later as another file.
- The O*NET copy goes stale until regenerated. Attribution must stay in the file header.
- Matching is unchanged: it still reads the saved tags and the about text. Normalising tags
  to canonical ids (so "JS" and "JavaScript" match exactly) is a possible later step and
  would need its own ADR.
