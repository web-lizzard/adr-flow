# Valid ADR example (test fixture)

Canonical ADR markdown that passes **section-gap validation** (`find_missing_or_empty_sections` returns no gaps). Use for manual testing, LLM review smoke tests, and as a reference when writing integration tests.

**Canonical copy in tests:** `backend/tests/review_quality/fixtures/complete.md` (keep in sync).

## Suggested API title

`Use PostgreSQL for persistence`

## Markdown body

```markdown
## Context

We need to choose a database for the project.

## Options

1. PostgreSQL
2. MongoDB

## Decision

We will use PostgreSQL.

## Status

Accepted

## Consequences

Positive: ACID compliance. Negative: operational overhead.
```