# Forum Reply Assistant: Project Spec

> Working name: `forum-assist`. A human-in-the-loop tool that watches topical forums, finds threads where a knowledge base (KB) can add value, and drafts replies for manual review. **It never posts without explicit approval.**

---

## 1. Goals and Non-Goals

### Goals

- Ingest a KB (markdown/text/HTML docs) into a searchable vector index with source metadata.
- Poll one or more forums via official APIs and detect new threads/posts.
- Score each thread for "can the KB add something useful that hasn't been said yet?"
- Generate a grounded, cited, tone-matched draft reply.
- Provide a review queue (CLI first) to approve, edit, reject, and log outcomes.

### Non-Goals (v1)

- Autonomous posting.
- Scraping HTML where an API or RSS feed exists.
- Multi-user / hosted deployment.
- Fine-tuning models.

### Success Criteria

- On a hand-labeled set of ~50 threads, relevance filter reaches **>= 80% precision** on "should reply".
- **>= 70% of generated drafts** are rated "usable with light edits" in review.
- Zero drafts contain claims unsupported by retrieved KB chunks (verified by citation check).

---

## 2. Architecture

```
KB docs ──► [Ingest] ──► Vector store (Chroma)
                              │
Forum APIs ─► [Fetch] ─► threads table (SQLite)
                              │
                       [Candidate filter]  embed thread → top-k KB chunks → similarity threshold
                              │
                       [Relevance judge]   LLM → {should_reply, reason, confidence}
                              │
                       [Draft generator]   LLM + thread + existing replies + KB chunks
                              │
                       [Review queue]      drafts table (SQLite) → CLI approve/edit/reject
                              │
                       [Publisher] (optional, v2, approved drafts only)
```

### Key design decisions

- **Adapter pattern for forums.** One `ForumAdapter` interface; each platform is a plugin.
- **Two-stage filtering.** Cheap embedding similarity first, LLM judge second, to control cost.
- **Structured outputs.** The judge returns JSON via tool use, validated with Pydantic.
- **Idempotency.** Every thread is keyed by `(platform, external_id)`; reruns never duplicate work.
- **Everything is logged.** Prompts, retrieved chunk IDs, model outputs, and reviewer decisions are stored for evaluation.

---

## 3. Tech Stack

| Concern           | Choice                                             | Notes                                                                            |
| ----------------- | -------------------------------------------------- | -------------------------------------------------------------------------------- |
| Language          | Python 3.14                                        |                                                                                  |
| Packaging         | `uv` + `pyproject.toml`                            |                                                                                  |
| CLI               | Typer                                              |                                                                                  |
| Config            | Pydantic Settings + `.env` + `config.yaml`         |                                                                                  |
| Vector store      | ChromaDB (local persistent)                        | Swappable behind `VectorStore` protocol                                          |
| Embeddings        | Voyage AI or a local `sentence-transformers` model | Anthropic does not offer an embeddings endpoint; keep behind `Embedder` protocol |
| LLM               | Anthropic Python SDK                               | Smaller model for judge, larger for drafting                                     |
| DB                | SQLite via SQLAlchemy 2.x + Alembic                |                                                                                  |
| HTTP              | `httpx`                                            |                                                                                  |
| Reddit            | PRAW                                               |                                                                                  |
| Discourse         | REST API via `httpx`                               |                                                                                  |
| Scheduling        | APScheduler (or plain cron)                        |                                                                                  |
| Testing           | pytest, pytest-asyncio, `respx` for HTTP mocks     |                                                                                  |
| Lint/format/types | ruff, mypy                                         |                                                                                  |

### Reference docs

- Anthropic: [tool use](https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview), [prompt engineering](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview), [Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [PRAW](https://praw.readthedocs.io), [Discourse API](https://docs.discourse.org), [Stack Exchange API](https://api.stackexchange.com/docs)
- [ChromaDB](https://docs.trychroma.com), [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/), [Typer](https://typer.tiangolo.com), [Pydantic](https://docs.pydantic.dev)

---

## 4. Repository Layout

```
forum-assist/
├── CLAUDE.md                 # Claude Code working agreement (see §9)
├── SPEC.md                   # this file
├── pyproject.toml
├── config.example.yaml
├── .env.example
├── src/forum_assist/
│   ├── cli.py                # Typer entrypoint
│   ├── config.py
│   ├── db/                   # models.py, session.py, migrations/
│   ├── kb/                   # loader.py, chunker.py, indexer.py
│   ├── embeddings/           # base.py, voyage.py, local.py
│   ├── vectorstore/          # base.py, chroma.py
│   ├── forums/               # base.py, reddit.py, discourse.py, stackexchange.py
│   ├── pipeline/             # candidates.py, judge.py, drafter.py, runner.py
│   ├── llm/                  # client.py, prompts/ (versioned .md/.jinja files)
│   ├── review/               # queue.py, tui.py
│   └── eval/                 # dataset.py, metrics.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/             # sample threads, KB docs, recorded API responses
└── data/                     # gitignored: chroma/, sqlite db, raw KB
```

---

## 5. Data Model

**`kb_chunks`** (mirrored in vector store metadata)
`id, doc_path, source_url, heading_path, text, content_hash, indexed_at`

**`threads`**
`id, platform, external_id, url, title, body, author, created_at, fetched_at, reply_count, has_accepted_answer, status`
`status`: `new | skipped_low_similarity | skipped_judge | drafted | approved | rejected | posted | stale`

**`judgments`**
`id, thread_id, should_reply, reason, confidence, model, prompt_version, retrieved_chunk_ids, created_at`

**`drafts`**
`id, thread_id, body, cited_chunk_ids, model, prompt_version, created_at, review_status, reviewer_notes, edited_body`

---

## 6. Pipeline Specifications

### 6.1 KB Ingestion

- Load `.md`, `.txt`, `.html` from a configured directory (and later URLs).
- Chunk by heading structure first, then by token window (~400 tokens, 50 overlap).
- Store `heading_path` and `source_url` for citation.
- Re-index only changed files (content hash).
- **CLI:** `forum-assist kb index [--path DIR] [--rebuild]`

### 6.2 Forum Fetching

`ForumAdapter` interface:

```python
class ForumAdapter(Protocol):
    name: str

    def fetch_new(self, since: datetime | None) -> Iterable[ForumThread]: ...
    def fetch_replies(self, thread_id: str) -> list[ForumPost]: ...
```

- Config specifies communities/categories/tags and keyword prefilters.
- Respect rate limits (honor response headers; exponential backoff).
- Skip threads older than `max_age_days`, locked threads, and threads with accepted answers.
- **CLI:** `forum-assist fetch [--platform reddit]`

### 6.3 Candidate Filter

- Embed `title + body[:N]`; query top-k KB chunks.
- Pass if top similarity >= `candidate_threshold` (tunable; start by inspecting the score distribution on labeled data).
- **CLI:** `forum-assist candidates --explain` prints scores and matched chunks.

### 6.4 Relevance Judge (LLM)

Input: thread, existing replies (truncated), top-k chunks.
Output (tool-use schema):

```json
{ "should_reply": true, "reason": "...", "confidence": 0.0-1.0,
  "gap": "what the KB adds that existing replies lack" }
```

Rules: reject if already well answered, off-topic, a rant, asks for personal opinions, or requires info not in the KB.

### 6.5 Draft Generator

- Inputs: thread, replies, chunks, forum style guide (from config).
- System prompt constraints: answer **only** from provided context; cite sources inline; admit uncertainty; no marketing language; required disclosure text per platform; length cap.
- Post-check: every factual claim maps to a cited chunk ID; drafts failing validation are flagged, not queued as "ready".
- **CLI:** `forum-assist draft --thread ID`

### 6.6 Review Queue

- `forum-assist review` steps through pending drafts: show thread, draft, sources, confidence.
- Actions: **approve / edit (opens `$EDITOR`) / reject (with reason tag) / skip**.
- Approved drafts are exported (copy to clipboard or printed with the thread link). Auto-posting is v2 and platform-permitting.

### 6.7 Orchestration

- `forum-assist run` executes fetch → candidates → judge → draft once.
- `forum-assist schedule` runs it on an interval via APScheduler.

---

## 7. Milestones

Each milestone ends with passing tests and a demoable CLI command.

### M0: Scaffold

- `uv` project, ruff/mypy/pytest config, CI workflow, config loading, SQLite + Alembic baseline.
- **Done when:** `forum-assist --help` works and CI is green.

### M1: KB Ingestion and Retrieval

- Loader, chunker, embedder, Chroma store, `kb index` and `kb search "query"`.
- **Done when:** searching a known question returns the expected chunk in the top 3 on a fixture KB.

### M2: One Forum Adapter (start with Reddit or Discourse)

- Fetch, dedupe, persist, filter stale/answered threads.
- **Done when:** repeated `fetch` runs insert zero duplicates (integration test with recorded responses).

### M3: Candidate Filter and Judge

- Similarity gating, judge prompt, Pydantic-validated tool-use output, `judgments` table.
- **Done when:** a labeled eval set (`eval/`) produces precision/recall report via `forum-assist eval judge`.

### M4: Draft Generation

- Drafter, citation validation, prompt versioning.
- **Done when:** drafts for the eval set all pass citation validation; manual rating script exists.

### M5: Review Queue

- CLI review flow, outcome logging, reject-reason tags.
- **Done when:** a full run produces drafts that can be approved/rejected end to end.

### M6: Orchestration and Observability

- `run`, `schedule`, structured logging, token/cost tracking per run.
- **Done when:** a scheduled run completes unattended and writes a run summary.

### M7: Second Adapter and Hardening

- Add another platform via the same interface; retry/backoff, error budgets.
- **Done when:** the second adapter is added without touching pipeline code.

### v2 Candidates

Approved-draft publishing, feedback-driven threshold tuning, web UI, reranking, KB gap reports ("threads we couldn't answer").

---

## 8. Testing and Evaluation

- **Unit:** chunker, similarity gating, prompt builders, citation validator, adapter parsing.
- **Integration:** adapters against recorded HTTP fixtures (`respx`); full pipeline with a fake LLM client.
- **LLM tests:** a small golden set with labeled threads (`tests/fixtures/eval_threads.jsonl`). Live-model tests are opt-in (`pytest -m live`).
- **Metrics tracked:** candidate pass rate, judge precision/recall, draft approval rate, edit distance between draft and approved text, cost per approved draft.

---

## 9. Claude Code Working Agreement (`CLAUDE.md` starter)

```markdown
# forum-assist

Human-in-the-loop forum reply drafting tool. See SPEC.md for the full plan.

## Commands

- Install: `uv sync`
- Test: `uv run pytest` (live LLM tests: `uv run pytest -m live`)
- Lint/format: `uv run ruff check . && uv run ruff format .`
- Types: `uv run mypy src`

## Rules

- Work one milestone at a time from SPEC.md. Do not start the next until the current one's "Done when" is met.
- Never add code that posts to a forum automatically.
- All external I/O (forums, LLM, embeddings, vector store) goes behind a protocol so it can be faked in tests.
- Prompts live in `src/forum_assist/llm/prompts/` and are versioned; never inline long prompts in code.
- Check official docs for any library API before using it; do not guess signatures.
- Secrets only via env vars; never commit `.env` or `data/`.
- Add or update tests with every change. Keep functions small and typed.
- Ask before adding new dependencies.
```

**Suggested workflow:** start Claude Code in plan mode, point it at SPEC.md, and have it produce a task breakdown for M0 only. Review, then execute. Commit per milestone.

---

## 10. Risks and Mitigations

| Risk                                                 | Mitigation                                                                                                       |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Forum ToS prohibits automated posting or bot replies | Human review and manual posting; read each platform's API terms before building its adapter; include disclosures |
| Hallucinated or ungrounded claims                    | Context-only prompting, mandatory citations, citation validator                                                  |
| Spammy or low-value replies                          | Strict judge criteria, per-forum daily caps, "already answered" detection                                        |
| API rate limits / bans                               | Official APIs only, conservative polling, caching, backoff                                                       |
| Cost creep                                           | Cheap embedding gate before LLM calls, smaller judge model, per-run budget cap                                   |
| Stale KB                                             | Content-hash re-indexing; KB freshness date shown in review UI                                                   |

---

## 11. Open Questions

1. What is the KB (product docs, personal notes, a specific domain), and how large is it?
2. Which forum to target first, and does its ToS allow assisted (human-posted) replies?
3. Is a disclosure statement required or desired in each reply?
4. Embeddings: hosted (Voyage) or fully local?
5. Desired review surface after the CLI: web UI, Slack/Discord notification, or email digest?
