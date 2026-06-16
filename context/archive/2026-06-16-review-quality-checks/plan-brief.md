# Review Quality Checks — Plan Brief

> Full plan: `context/changes/review-quality-checks/plan.md`
> Research: `context/changes/review-quality-checks/research.md`

## What & Why

F-01 establishes a minimal verification harness so review output can be checked against required-section and actionability guardrails before the first AI review loop is treated as useful. This protects the product wedge — reliable section-gap detection with concrete corrective suggestions — without building the AI review engine itself.

## Starting Point

The domain already defines `ReviewAnnotation`, `ReviewResult`, and `ReviewAnnotationKind`; `AIReviewCompleted` carries `ReviewResult`; and the five-heading starter template is locked in `backend/domain/adr/template.py`. Nothing else exists: no section parser, graders, fixtures, or `backend/tests/review_quality/` directory. No LLM adapter, review handler, or annotation UI.

## Desired End State

Running `just test-backend` executes a deterministic pytest harness that parses golden ADR fixtures, grades synthetic `ReviewResult` objects for section coverage and actionability, and reports precision/recall metrics. S-04 imports the domain parser and test grader to validate real LLM output before showing annotations to users.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Harness type | Eval-only pytest harness | F-01 is the evaluator; S-04 is the generator | Research |
| Output contract | Grade existing `ReviewResult` VOs | Same shape `AIReviewCompleted` already carries — no parallel schema | Research |
| Empty section rule | Placeholders count as empty | TBD/TODO/N/A sections need review attention same as blank ones | Plan |
| Heading match | Exact, case-sensitive | Matches locked starter template; aliases deferred post-MVP | Plan |
| Actionability | Kind-specific field rules | Missing/conciseness need suggestions; inconsistency needs location+message | Plan |
| Inconsistency scope | Schema/actionability only | Quality grading needs LLM output S-04 doesn't have yet | Plan |
| CI gate | Metrics reported, no hard 80% gate | Golden set proves grader logic; NFR threshold gates S-04 integration | Plan |
| Code layout | Parser in `domain/adr/`, grader in `tests/review_quality/` | Pure domain logic reusable by S-04; eval fixtures stay in tests | Plan |
| Grader assertions | Structure over wording | Avoid brittle LLM prose checks and oracle problems | Research |

## Scope

**In scope:** Domain markdown section parser; golden ADR fixtures; deterministic graders (missing-section precision/recall, actionability); synthetic `ReviewResult` harness tests; aggregate metrics reporting; pytest via `just test-backend`.

**Out of scope:** LLM/OpenRouter calls; review handlers and status transitions; inconsistency quality grading; frontend UI; persisted report artifacts; hard 80% CI threshold; heading aliases; probabilistic eval dataset.

## Architecture / Approach

```
Golden ADR fixtures          Synthetic ReviewResult (hand-crafted)
        │                              │
        ▼                              ▼
 domain/adr/required_sections.py    ReviewResult VO
 (parse, find gaps)                      │
        │                              │
        └──────────┬───────────────────┘
                   ▼
        tests/review_quality/grader.py
        (precision/recall + actionability)
                   │
                   ▼
              pytest + metrics report
                   │
                   ▼
         S-04 imports parser + grader
         to validate real LLM output
```

F-01 is independent of persistence and API layers. All tests are in-memory with no DB or network.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Domain Section Parser | `required_sections.py` + parser tests | Edge cases in markdown heading boundaries |
| 2. Grader Module | `grade_review_output()` + unit tests | Section name extraction from annotation text |
| 3. Fixtures & Harness Tests | Golden fixtures + end-to-end suite + metrics | Fixture ground truth drift vs parser behavior |

**Prerequisites:** F-02 domain vocabulary merged (done); no LLM or review runtime needed.
**Estimated effort:** ~1–2 sessions across 3 phases.

## Open Risks & Assumptions

- Section name extraction from free-text `location`/`message` fields may need refinement when S-04 produces real LLM annotations — grader should prefer `location` when present.
- The soft CI gate (metrics only) means F-01 merge does not block on 80% recall; S-04 must wire the hard gate before user-facing review ships.
- PRD NFR line 134 says "alternatives" but template uses `Options` — implementation follows the five-heading template.

## Success Criteria (Summary)

- Parser correctly identifies missing/empty sections on golden ADR fixtures
- Grader passes synthetic good results and fails deliberately bad ones with clear failure messages
- Aggregate precision/recall metrics are reported in pytest output
- S-04 has a documented import path for parser and grader validation
