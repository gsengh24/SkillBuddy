# 7. AI gateway: free LLM providers, local embeddings, LLM-first matching with a fallback

- **Status:** Accepted
- **Date:** 2026-10-01
- **Supersedes:** part of ADR 0004, decision 2 (see "Relation to ADR 0004")

## Context

Skill Buddy launches on a single college campus in about a week, in English only, for a few
thousand students. Constraints:

- **Zero spend, no credit card** on any account (ADR 0004).
- **Matching must use AI.** The LLM is a core stage of the pipeline: it understands
  profiles, makes the final selection and writes the explanations (ARCHITECTURE.md §3,
  stages 1 and 4). It runs on every match request by default.
- **No leaks of student data.** Real profile text may only go to providers whose terms
  forbid training on it. Names, emails and contact handles are never sent at all.
- **Free hosting** (ADR 0003): a 512 MB API host that sleeps when idle, Neon Free (0.5 GB),
  and no free always-on worker.
- **No real data yet.** The schema still stores `vector(768)`, so the embedding dimension
  can change with a migration and no backfill.

This ADR compares the options, with the figures checked on **2026-10-01**. Free tiers change
without notice, so the dated rows in [docs/free-tier-limits.md](../free-tier-limits.md) must
be re-checked before launch.

## Options considered

### 1. Embeddings

**(a) A small open-source model, run in-process with an ONNX runtime (fastembed)**

These are the fastembed-supported English models small enough for a free host:

| Model | Dims | Model size | Licence | MTEB avg / retrieval |
| --- | --- | --- | --- | --- |
| **BAAI/bge-small-en-v1.5** | **384** | **67 MB** | **MIT** | **62.2 / 51.7** |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | 90 MB | Apache-2.0 | lower (older model) |
| snowflake/snowflake-arctic-embed-xs | 384 | 90 MB | Apache-2.0 | n/a |
| snowflake/snowflake-arctic-embed-s | 384 | 130 MB | Apache-2.0 | n/a |
| jinaai/jina-embeddings-v2-small-en | 512 | 120 MB | Apache-2.0 | n/a |
| BAAI/bge-base-en-v1.5 | 768 | 210 MB | MIT | 63.6 / 53.3 |
| nomic-ai/nomic-embed-text-v1.5 | 768 | 520 MB | Apache-2.0 | n/a |

bge-base gains only about 1.4 MTEB points over bge-small. In return it triples the model
size, doubles the vector storage, and doesn't fit comfortably in 512 MB.

**RAM, based on published figures (not measured here):**

- fastembed with bge-small's ONNX build uses about **170–230 MB** resident.
- One report of a FastAPI app with this model measured about 75 MB for the app plus about
  245 MB for the model, peaking near **375 MB** under batch load.
- The same model under PyTorch (sentence-transformers) needs 1–1.5 GB, so PyTorch is ruled
  out.

**Fit on a 512 MB host:** yes, but tightly. It needs:

- one uvicorn process;
- ONNX Runtime limited to 1 thread;
- batches of 8 texts or fewer, with inputs truncated to 256 tokens;
- the model loaded lazily on first use, not at import.

**Cold start:** no published benchmark was found. Our estimate is about 1–3 s to import
ONNX Runtime and load a 67 MB model from local disk. That is small next to Render's roughly
one-minute wake from sleep. The model files must be baked into the image at build time; a
download from Hugging Face at start-up would add time and an external dependency. Measuring
RSS and load time in CI is build step 3.

**Catches:**

- RAM headroom is about 130 MB, so a memory leak or a large batch can push the process into
  an out-of-memory restart.
- CPU time on a shared or 0.1 vCPU free instance is slow. Embedding is therefore done in
  background jobs, never inline in a request.
- fastembed adds onnxruntime, tokenizers, numpy and huggingface-hub (about 60 MB) to the
  image.

**(b) The same model as a private service on a free Hugging Face Space: not viable.**

As of 2026-10-01:

- Creating Gradio or Docker Spaces requires a paid plan (PRO). Free accounts can create
  static Spaces only, plus up to two ZeroGPU Gradio Spaces (verified email, account older
  than 30 days).
- ZeroGPU gives a free account **5 minutes of GPU time per day**, and only for Gradio apps.
- The free CPU Basic hardware (2 vCPU, 16 GB) can't be used without a paid plan.
- Free hardware sleeps after an idle period that isn't published, so the first call waits
  for a cold start.
- A private Space is reachable only by its owner and collaborators (others get a 404), so
  privacy would be acceptable. It doesn't matter, because the Space can't be created for
  free.

**(c) Hosted embeddings on Cloudflare Workers AI (`@cf/baai/bge-small-en-v1.5`): kept as a
fallback.**

- It is the same model at the same 384 dimensions.
- It costs 1,841 neurons per million input tokens. Embedding 1,000 profiles (4 facets,
  about 1,200 tokens each) uses about 2,200 neurons, well inside the 10,000/day free
  allocation.
- Profile text leaves our servers, but Cloudflare's terms forbid training on it (see 3).
- Vectors from a different runtime are close to fastembed's but not identical. The two must
  never be mixed in one index: `model_version` tells them apart, and switching runtime means
  re-embedding everyone (minutes of work at campus scale).

### 2. Embedding model and dimension

**bge-small-en-v1.5, 384 dimensions.** It is the smallest model with strong English
retrieval scores, it is MIT-licensed, it fits the RAM budget, and the storage budget already
assumes 384 (about 84 KB per user, about 4,000 users within 350 MB;
[storage-budget.md](../storage-budget.md)). Queries use bge's query instruction prefix, and
documents are embedded without it. `model_version` stores `bge-small-en-v1.5@fastembed-onnx`.

**Migration needed (0003).** There is no real data, so no backfill is needed. Staging
embeddings, if any, are synthetic and are regenerated by the re-embed job.

1. Drop the index `ix_profile_embeddings_embedding_hnsw`.
2. `DELETE FROM profile_embeddings`. Embeddings are derived data, and pgvector can't cast a
   768-dimension vector to 384.
3. `ALTER TABLE profile_embeddings ALTER COLUMN embedding TYPE vector(384)`.
4. Recreate the HNSW index with `vector_cosine_ops`.
5. `downgrade()` reverses steps 1–4 back to 768 (deleting rows the same way).

In code:

- `EMBEDDING_DIMENSIONS` in `app/models/profile_embedding.py` becomes 384, so that
  `alembic check` shows no drift.
- New settings `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` are added. The worker refuses
  to start if the setting differs from the column's dimension.

A pgvector column with an HNSW index needs a fixed dimension. "Configurable" (ADR 0004,
rule 3) therefore means that the dimension is one setting plus one migration away, with a
guard against mismatches. It does not mean the dimension can change at runtime. Storage
drops from about 97 KB to about 84 KB per user.

### 3. Free LLM APIs (limits and training terms)

| Provider | Free limits (2026-10-01) | Training on inputs | Card | Verdict |
| --- | --- | --- | --- | --- |
| **Groq** (free plan) | Per model: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` each have **30 RPM, 1K requests/day, 8K tokens/min, 200K tokens/day**. Over the limit returns 429 with `retry-after`. | **Forbidden.** Services Agreement (modified 2026-06-22): Groq "is not permitted to use Inputs or Outputs for training or fine-tuning" unless the customer allows it. No retention by default; logs up to 30 days for troubleshooting or abuse; self-serve **Zero Data Retention** in Data Controls. | Not needed | **Primary** |
| **Cloudflare Workers AI** (Workers Free) | **10,000 neurons/day**, resetting at 00:00 UTC. `@cf/openai/gpt-oss-20b`: 18,182 neurons/M input, 27,273/M output. `llama-3.1-8b-instruct-fp8-fast`: 4,119/M input, 34,868/M output. | **Forbidden.** Cloudflare "does not use your Customer Content to (1) train any AI models … or (2) improve any Cloudflare or third-party services". | Not needed | **Secondary** (overflow, and outages) |
| Mistral La Plateforme (Experiment) | About 1B tokens/month at about 1 request/s, per third-party sources; Mistral no longer publishes exact figures. "Evaluation" use. | **Trains on free-tier inputs by default** (commercial terms of 2026-03-12). An Admin → Privacy opt-out exists, but its availability on the free plan isn't confirmed. | Phone verification | **Excluded for now.** Reconsider only if the opt-out is confirmed in writing for the free plan. |
| Google Gemini API (free) | Generous limits | **Used to improve products, with human review; can't be turned off** outside the EEA, Switzerland and the UK. Terms also bar services likely to be used by under-18s. | Not needed | **Excluded** |
| Cerebras | Trial credits | n/a | **Payment method required** (since July 2026) | **Excluded** |
| OpenRouter `:free` models | 20 RPM, **50 requests/day** unless 10+ credits are bought (needs a card) | Varies by upstream provider; some log or train | Card for usable limits | **Excluded** |
| GitHub Models | Retired 2026-07-30 | n/a | n/a | **Excluded** |
| Local LLM on our host | n/a | No data leaves | n/a | **Excluded.** Even a 0.5B model doesn't fit next to the API in 512 MB, and would take seconds per token on a 0.1 vCPU. |

**Catches:**

- Groq's terms say the service is "not for consumer use". We are the customer and the
  students use our product, so this fits, but a lawyer hasn't reviewed it.
- Groq's free-service liability is capped at $5,000.
- `gpt-oss` models produce reasoning tokens, which count towards the token limits. Calls
  set low reasoning effort, and the budget below assumes that.
- Neither provider offers a service-level agreement on the free tier.

### 4. Daily call budget and supported daily active users

**Calls per user action:**

| Call | When | Tokens (input + output, estimate) | Cached by |
| --- | --- | --- | --- |
| Profile understanding (stage 1) | Profile created or text edited | about 1,000 + 500 = **1,500** | Hash of (normalised text, prompt version, model); the result is stored on the profile, so an unchanged text is never parsed again |
| Request understanding (stage 1) | Folded into the match call; no separate call | n/a | n/a |
| Selection and explanations (stage 4) | Fresh match request: one batched call with the top 15 candidates as compact summaries of about 110 tokens each | about 2,800 + 700 = **3,500** | Results stored as match rows with prompt version. Re-opening matches costs nothing. A new request with an unchanged profile, request text and candidate set reuses the stored result. |

**Free capacity per day:**

| Provider | Binding limit | Match calls/day (3,500 tokens) |
| --- | --- | --- |
| Groq | 200K tokens/day × 3 models, budgeted at 190K each = 570K | about 160 |
| Cloudflare (`gpt-oss-20b`) | 9,000 of the 10,000 neurons (10% kept for embedding fallback); about 70 neurons per call (2,800 × 18,182/M + 700 × 27,273/M) | about 130 |
| **Total** | | **about 290 match-call equivalents per day (about 1M tokens)** |

Groq's 8K tokens/minute per model allows only about 2 match calls per minute per model, so
about 6 per minute across Groq. Jobs therefore go through a queue, and a 429 moves the call
to the next model or provider instead of waiting.

**Supported daily active users** (assuming 0.2 profile parses per user per day in steady
state, plus 20% headroom for retries and cache misses):

- **About 200 daily active users** if every one of them makes one fresh match request a day,
  at about 3,800 tokens each.
- **About 500 daily active users** if 40% make a fresh request and the rest only view stored
  matches or chat (about 1,700 tokens each). This is the more realistic pattern; viewing and
  chatting cost no LLM calls.
- A campus of 3,000 users at 10–20% daily activity means 300–600 daily active users. That
  is at or slightly above the free capacity, so the per-user cap and invite waves below
  matter, and some days the busiest hours will fall back to templates.

**Launch spike:**

- 1,500 sign-ups in two days need about 2.25M tokens of profile parsing alone, which is more
  than 2 days of the whole free capacity.
- Mitigations:
  - invite the campus in waves of about 300 per day (ARCHITECTURE.md §3 already suggests
    cohort seeding);
  - prioritise the queue: match requests first, then parses of users with no parse yet,
    then re-parses;
  - let the fallback path handle any overflow, and run a nightly backfill job that re-parses
    and re-explains with the next day's quota.

**Caps (settings):**

| Setting | Default | Meaning |
| --- | --- | --- |
| `AI_USER_DAILY_MATCH_REQUESTS` | 3 | Fresh match requests per user per day |
| `AI_LLM_DAILY_CALL_CAP` | 400 | Global cap across all providers |
| Per-provider budgets | 190K tokens/model for Groq; 9,000 neurons for Cloudflare | Kept just under each free limit, so we stop before the provider does |

Counters live in Valkey and are keyed by UTC date, which costs a few commands per call.

### 5. Privacy design

What leaves our servers, and only to Groq or Cloudflare:

- **Stage 1:** the user's own free-text description, after redaction.
- **Stage 4:** the requester's request text, and the candidates' **structured summaries**
  (skills, interests, goals, availability band), each labelled with an opaque per-call alias
  (`C1`…`C15`). User IDs, names, emails, photos and contact handles are never sent.

**Redaction, before any text is sent:**

- Emails, phone numbers, URLs and `@handles` are replaced with placeholders such as
  `[email]`.
- The user's own name, if it appears in the text, is replaced with `[name]`.
- Redaction runs in the gateway and has unit tests. The redacted text is what gets embedded
  too, so contact details never end up in vectors.

**Provider settings:**

- Groq Zero Data Retention is switched on in Data Controls before the first real call. This
  is a manual dashboard step for the owner.
- API keys live only in the hosting dashboard.

**Prompt safety:**

- Untrusted text goes in as quoted JSON data fields.
- The output must reference only the aliases provided, and is schema-validated.
- Ranking weights are applied in code (ARCHITECTURE.md §7, "Guardrails").

**Our own storage:**

- Raw prompts and responses are not stored. Debug capture is off by default; when it is on,
  captures are purged after 7 days.
- Logs keep metadata only: prompt version, provider, model, latency, token counts and
  outcome.

**Consent line for onboarding** (shown next to the "About you" box; agreeing is part of
creating a profile):

> Your description is read by AI to find and explain your matches. We send only this text
> (never your name, email or contact details) to our AI providers, Groq and Cloudflare, and
> their terms don't allow them to train on it. [How we use AI](/privacy#ai)

**Privacy-policy wording** (replaces the draft paragraph under "How matching uses your
information"):

> **How we use AI to match you.** Matching is automated. When you write or change your
> profile, our servers turn your description into numbers (an "embedding") that let us find
> people with related skills and interests. This step runs on our own servers.
>
> To understand your description, choose your best matches and explain each suggestion, we
> also send text to an AI provider: currently Groq, Inc., with Cloudflare, Inc. as a backup.
> We send your description with email addresses, phone numbers, links, social handles and
> your name removed. When someone else asks for matches, a short summary of your profile
> (skills, interests, goals and availability, without your name or contact details) may be
> sent so the AI can compare candidates. We never send your name, email address or contact
> details.
>
> These providers process the text only to return a result to us. Their terms don't allow
> them to use it to train AI models. We have asked Groq not to retain it.
>
> We keep the results (your structured profile, your matches and the reasons shown), but not
> the messages exchanged with the AI provider. If the AI service is unavailable, we suggest
> matches using our own scoring and a simpler explanation.
>
> Suggestions are only suggestions: nobody can contact you unless you both agree. Deleting
> your account deletes your profile, its embeddings and your matches (see "Deleting your
> data").

The privacy page already exists as a draft. The text above goes in with the Phase 1 build,
and it needs a legal review against India's DPDP Act before launch.

### 6. Graceful degradation

The LLM path is the normal mode. The fallback is used only when there is no LLM to call:

| Trigger | Behaviour |
| --- | --- |
| A provider returns 429, a 5xx error or times out | The call moves to the next provider in the chain: Groq model A, then Groq model B, then Cloudflare `gpt-oss-20b`. The failed provider is skipped until its `retry-after` passes, or until UTC midnight once its daily budget is used. |
| All providers exhausted, or `AI_LLM_ENABLED=false` (feature flag, an operational kill switch) | **Fallback path.** No parse means the raw redacted text is embedded for every facet and the profile is marked `parse_status=pending`. Stage 4 takes the top 5 by code score (stage 3), with template explanations built from overlapping structured fields when they exist (for example "You both mention *machine learning*; they offer *UI design*, which you're looking for"), or from a generic line otherwise. Matches are marked `explanation_source=template`. |
| Output invalid after one retry (CLAUDE.md rule 5) | Logged loudly as an error, then handled like a provider failure (next provider, then fallback). Bad output is never used. |
| Embedding runtime unavailable or out of memory | Cloudflare bge-small embeddings, under a separate `model_version`. The switch is all-or-nothing, with a re-embed. |

**Settings:**

- `AI_LLM_ENABLED` (default `true`);
- `AI_LLM_PROVIDERS` (ordered list, default `groq,cloudflare`);
- `AI_LLM_TIMEOUT_SECONDS` (default 20 per call);
- the caps in section 4.

The daily backfill job re-parses `pending` profiles and may re-explain template matches that
are still unanswered, once quota is available. Monitoring logs the fallback rate per day. A
sustained fallback rate above about 10% means the budget is too small for the load.

### 7. Gateway interface

One module (`app/ai/`) is the only code allowed to talk to models (CLAUDE.md rule 4).
Product code asks for **tasks**, not providers:

```python
class AIGateway:
    async def understand_profile(self, text: str, *, owner_name: str | None) -> ParsedProfile | None
    async def select_and_explain(self, request: RequestSummary,
                                 candidates: Sequence[CandidateSummary]) -> Selection | None
    async def embed(self, texts: Sequence[str], *, kind: Literal["query", "passage"]) -> Embeddings
```

- `None` means "use the fallback", and the caller takes the template path.
- Providers sit behind two small protocols:

  ```python
  class ChatProvider(Protocol):
      name: str          # e.g. "groq:openai/gpt-oss-120b"
      async def complete_json(self, prompt: RenderedPrompt, schema: type[BaseModel],
                              timeout: float) -> ChatResult  # parsed output + usage
  class Embedder(Protocol):
      model_version: str
      dimensions: int
      async def embed(self, texts: Sequence[str], kind: EmbedKind) -> list[list[float]]
  ```

- Both Groq and Cloudflare offer OpenAI-compatible chat endpoints, so one
  `OpenAICompatibleChatProvider` (plain `httpx`, no vendor SDK) covers both, configured with
  a base URL, model and key.
- `FastEmbedEmbedder` and `CloudflareEmbedder` implement `Embedder`.
- `FakeChatProvider` and `FakeEmbedder` serve tests and CI, so no test calls a real
  provider.

The gateway owns everything around those calls:

- redaction;
- loading versioned prompt files (`app/ai/prompts/<task>/v<N>.md`);
- the provider chain and its circuit breaker;
- budget counters and the timeout;
- schema validation with one retry;
- logging metadata.

Swapping or adding a provider means a new settings entry, plus one class only if the API
isn't OpenAI-compatible. No product code changes.

All gateway calls run in background jobs, never in the API request path (ADR 0002). The
API stores a match request, enqueues it and returns. The client then polls the request
resource.

## Decision

1. **LLM-first matching.** Stage 1 (profile understanding) and stage 4 (final selection and
   explanations) call an LLM for every profile change and every fresh match request, by
   default. The rule-based and template path is a **fallback only**, used when quotas are
   exhausted, providers are down, or the kill switch is off.
2. **Providers:** Groq free plan as primary (`gpt-oss-120b` for selection,
   `gpt-oss-20b` for parsing, `qwen3.8-27b` as spill-over), and Cloudflare Workers AI free
   (`gpt-oss-20b`) as secondary. Mistral, Gemini, Cerebras, OpenRouter and GitHub Models are
   not used. Only providers whose terms forbid training on inputs, and that need no card, may
   receive real data.
3. **Embeddings:** `BAAI/bge-small-en-v1.5`, **384 dimensions**, run with fastembed (ONNX)
   inside the process that runs jobs, with the model baked into the image. Cloudflare's
   hosted bge-small is the fallback. Hugging Face Spaces are rejected (no free Gradio,
   Docker or CPU Spaces).
4. **Migration 0003** changes `profile_embeddings.embedding` to `vector(384)`, as described
   in section 2.
5. **Privacy:** only redacted free text and alias-labelled structured summaries leave our
   servers; Groq Zero Data Retention is switched on; the consent line and policy wording in
   section 5 are adopted.
6. **Budget:** per-user, global and per-provider daily caps, a 20 s timeout, the
   `AI_LLM_ENABLED` kill switch, and caching of parses and match results. Sized for about
   200–500 daily active users.
7. **Interface:** the task-level gateway with swappable provider protocols in section 7.

### Relation to ADR 0004

ADR 0004 decision 2 said "an optional free-tier LLM provider", that "the matching pipeline
must work end to end with no LLM call", and that "an LLM, when available, only improves
quality". This ADR **supersedes the "optional" stance**:

- the LLM is a core stage, used by default;
- the no-LLM path stays only as a fallback, so the product keeps working when a free quota
  or a provider fails.

The local open-source embedding model and the gateway requirement from decision 2 still
apply. Decision 4 (no real data to providers that may train on it) is unchanged and is
applied here.

## Consequences

**Positive**

- AI matching at zero cost, with no card on any account.
- Student text goes only to two providers whose terms forbid training on it. Contact details
  never leave our servers, and embeddings are computed on our own servers.
- Quota exhaustion or an outage reduces quality but never breaks matching.
- Providers can be swapped through settings, which leaves a path to a paid or self-hosted
  model later.
- 384 dimensions halves vector storage and fits the existing storage budget.

**Negative / risks**

- **Capacity is about 200–500 daily active users.** A busy launch week or exam-season spike
  pushes users onto template explanations. Invite waves and the per-user cap are required,
  not optional.
- **Two external dependencies whose free terms can change** without notice. Re-check both
  before launch and monthly (free-tier-limits.md).
- **Prompts must be small.** 15 candidates at about 110 tokens each leaves little room;
  richer context costs capacity.
- **Tight RAM.** The embedding model takes about half of a 512 MB host. It must be measured
  before launch, with Cloudflare embeddings ready as the fallback.
- **Job runner prerequisite.** Every model call runs in a background job, but staging has no
  free always-on worker (ADR 0003). How jobs run on free hosting needs its own ADR before
  launch, and email sending (ADR 0006) has the same dependency.
- Groq's "not for consumer use" clause and the privacy wording have not had legal review.
- Evaluation quality depends on the offline eval set (`backend/evals`), which is still 100
  unreviewed drafts. Prompt changes can't be judged until those pairs are reviewed.

**When to revisit**

- When daily active users or the fallback rate exceed the figures above.
- If either provider changes its training or retention terms.
- When a budget exists: a paid tier would raise limits without changing the interface.

## Build order

1. **Job runner on free hosting (ADR 0008).** Decide where background jobs run at zero cost.
   This blocks everything below, and email too.
2. **Migration 0003 and settings:** `vector(384)`; `EMBEDDING_MODEL` and
   `EMBEDDING_DIMENSIONS` with the start-up guard; `.env.example` entries; storage-budget
   update.
3. **Embedder:** fastembed dependency, model baked into the image, `FastEmbedEmbedder`, and
   a CI step that records RSS and load time (it must stay under about 400 MB peak).
4. **Gateway core** (`app/ai/`): protocols, fake providers, redaction (with tests), prompt
   file loader, schema validation with one retry, metadata logging, budget counters, timeout,
   circuit breaker, kill switch.
5. **Providers:** `OpenAICompatibleChatProvider` for Groq and Cloudflare, and
   `CloudflareEmbedder`. Unit tests use recorded fixtures; real keys never reach CI.
6. **Stage 1:** profile-understanding prompt v1, the `ParsedProfile` schema, a parse job with
   hash-based caching, `parse_status`, and the backfill job.
7. **Stages 2–3:** retrieval by facet and code scoring (the fallback ranking, and the input
   to stage 4).
8. **Stage 4:** selection-and-explanation prompt v1, alias mapping, the template fallback,
   and stored match rows with prompt version and `explanation_source`.
9. **Onboarding and privacy text:** the consent line, the policy wording, and a
   `terms_version` bump.
10. **Eval run:** review the eval pairs and record precision@5 for the LLM path and the
    fallback path.
11. **Before launch (owner, in dashboards):**
    - create the Groq and Cloudflare accounts without a card;
    - turn on Groq Zero Data Retention;
    - put the keys in the hosting dashboard;
    - re-check free-tier-limits.md.
