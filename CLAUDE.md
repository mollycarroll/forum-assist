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
