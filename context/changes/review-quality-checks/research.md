---
date: 2026-06-16T19:02:00+02:00
researcher: Cursor
git_commit: unavailable
branch: unavailable
repository: adr-flow
topic: "Harness needs in an agentic system for Review-quality-checks"
tags: [research, codebase, review-quality-checks, harness, ai-review, evals]
status: complete
last_updated: 2026-06-16
last_updated_by: Cursor
---

# Research: Harness needs in an agentic system for Review-quality-checks

**Date**: 2026-06-16T19:02:00+02:00
**Researcher**: Cursor
**Git Commit**: unavailable
**Branch**: unavailable
**Repository**: adr-flow

## Research Question

What harness does the agentic system need for the `review-quality-checks` change, keeping MVP scope simple, and using `context/changes/review-quality-checks/harness-good-practices.md` as input?

## Summary

F-01 should build a **minimal evaluation harness**, not an agent runtime. Its job is to prove that future AI review output satisfies the product guardrails before S-04 wires in the real LLM review flow.

For the MVP, the harness needs:

- Fixture ADR markdown cases with known missing or empty required sections.
- A deterministic parser for the fixed ADR headings: `Context`, `Options`, `Decision`, `Status`, and `Consequences`.
- A structured output contract based on existing `ReviewResult` and `ReviewAnnotation` value objects.
- Deterministic graders for schema validity, required-section detection, and annotation actionability.
- A pytest runner that reports pass/fail and simple per-section precision/recall.

It should not include OpenRouter calls, prompt orchestration, LLM-as-judge, human calibration, OpenTelemetry, browser tests, or a production monitoring backend in F-01. Those belong to S-04 or post-MVP once the runtime review loop exists.

## Detailed Findings

### Product Boundary

The roadmap defines F-01 as a foundation slice where review output can be checked against required-section and actionability guardrails before the first review loop is treated as useful (`context/foundation/roadmap.md:76-87`). The change file repeats the same boundary: minimal verification harness, not a full review engine, and independent enough to run in parallel with F-02 (`context/changes/review-quality-checks/change.md:10-16`).

The PRD makes the quality bar concrete. The starter template has five required markdown headings (`context/foundation/prd.md:92`), AI review returns missing-section, inconsistency, and conciseness annotations (`context/foundation/prd.md:110-114`), and the business logic treats missing or empty sections plus concrete corrective suggestions as the output contract (`context/foundation/prd.md:143-149`).

The NFR wording says at least 80% of AI reviews should detect missing required ADR sections (`context/foundation/prd.md:134`) and every detected issue should have a concrete corrective action (`context/foundation/prd.md:135`). F-01 does not need to prove real LLM quality yet; it needs to establish the deterministic contract used to measure it.

### Runtime Harness vs Evaluation Harness

The good-practices research separates the runtime agent harness from the evaluation harness. Runtime concerns include tools, orchestration, memory, sandboxing, policy, and observability; evaluation concerns include task loading, isolated runs, trace capture, grading, metrics, and release gates (`context/changes/review-quality-checks/harness-good-practices.md:26-39`, `context/changes/review-quality-checks/harness-good-practices.md:76-86`).

For F-01, only the evaluation side is in scope. The research explicitly says F-01 is the eval harness and the AI review engine lands in S-04 (`context/changes/review-quality-checks/harness-good-practices.md:30-35`). It recommends deterministic graders first, golden fixture ADRs, structure-over-wording assertions, and a CI gate contract (`context/changes/review-quality-checks/harness-good-practices.md:34-39`).

The runtime agent path is already reserved in the architecture: `ADRSubmittedForReview` leads to a `RunAiReview` handler, which calls an LLM adapter and appends `AIReviewCompleted` (`context/foundation/application-architecture.md:116-124`, `context/foundation/application-architecture.md:157-167`). That flow is S-04, not F-01.

### Existing Code Contract

The backend already has review vocabulary to build on. `ReviewAnnotationKind` defines `missing_section`, `inconsistency`, and `conciseness`; `ReviewAnnotation` carries `kind`, `message`, optional `location`, and optional `suggestion`; `ReviewResult` wraps annotations with `reviewed_at` and optional reviewed content (`backend/domain/adr/value_objects.py:42-62`).

`AIReviewCompleted` already carries a `ReviewResult` (`backend/domain/adr/events.py:22-24`). Current ADR tests only construct the vocabulary and event objects; they do not grade review quality, parse sections, or validate actionability (`backend/tests/domain/test_adr.py:86-100`).

This means F-01 should not invent a separate JSON contract for harness output. It should grade the same domain value-object shape that S-04 will eventually produce.

### Current Gaps

There is no review-quality harness implementation yet:

- No section parser for ADR markdown.
- No fixed required-section detector.
- No missing-vs-empty section rule.
- No actionability validator.
- No golden ADR fixture set.
- No grader module or runner.
- No CI/report artifact beyond normal backend tests.
- No LLM adapter or AI review handler implementation.
- No frontend annotation UI.

This gap is expected. F-01 is the slice intended to introduce the verification harness before S-04 introduces the runtime review path.

### Test Strategy Fit

The test plan identifies AI review quality as Risk #1 and says the cheapest MVP protection is fixture ADRs with known section presence, structured annotations that flag the right sections, and schema-valid JSON conforming to F-01's contract (`context/foundation/test-plan.md:42-54`).

It also explicitly excludes full probabilistic AI review evaluation with F-scores as an MVP gate (`context/foundation/test-plan.md:27-35`, `context/foundation/test-plan.md:142-150`). That supports keeping F-01 deterministic and small.

The existing backend test command is `just test-backend`, which runs `cd backend && uv run pytest` (`Justfile:20-21`). F-01's first harness should fit that path instead of adding a new toolchain.

### Recommended MVP Harness Shape

Keep the first implementation close to backend tests and domain code:

```text
backend/tests/review_quality/
  fixtures/
    complete.md
    missing_context.md
    empty_decision.md
    missing_multiple_sections.md
  cases.py
  grader.py
  test_required_sections.py
  test_annotation_actionability.py
```

If the implementation needs reusable production logic, put pure markdown parsing and section detection under `backend/domain/adr/` because the domain layer is pure business logic and has no FastAPI/SQL dependencies (`context/foundation/application-architecture.md:29-39`). Keep test-only fixture loading, expected cases, metric aggregation, and report formatting under tests.

The harness-good-practices document suggests a broader `fixtures/`, `graders/`, `runner/`, `reports/` artifact shape (`context/changes/review-quality-checks/harness-good-practices.md:186-194`). For MVP simplicity, collapse that into pytest files first. A separate report directory can wait until CI or prompt iteration needs persistent artifacts.

Recommended interface:

```python
@dataclass(frozen=True)
class ReviewQualityCase:
    name: str
    markdown: str
    missing_sections: frozenset[str]


@dataclass(frozen=True)
class ReviewQualityVerdict:
    passed: bool
    missing_section_precision: float
    missing_section_recall: float
    failures: tuple[str, ...]


def grade_review_output(
    case: ReviewQualityCase,
    result: ReviewResult,
) -> ReviewQualityVerdict:
    ...
```

### Grader Needs

F-01 needs three deterministic grader families:

1. **Section parser checks**: Parse markdown headings and decide which of the five required sections are missing or empty. The PRD makes the fixed section set the structural contract (`context/foundation/prd.md:92`, `context/foundation/prd.md:145`).
2. **Missing-section annotation checks**: For a fixture case, require a `missing_section` annotation for each expected missing or empty section. Grade precision and recall by section name instead of exact wording.
3. **Actionability checks**: Every annotation should have a useful `message`; missing-section and conciseness annotations should have a concrete `suggestion` when the issue needs a corrective action. The PRD binds every detected issue to a concrete corrective proposal (`context/foundation/prd.md:135`, `context/foundation/prd.md:147`).

The first implementation should avoid judging inconsistency quality. Inconsistency detection is an AI capability from FR-011, but it is harder to make deterministic without turning F-01 into a larger dataset and rubric project.

### Fixture Needs

Start with a small but representative golden set:

- A complete valid ADR.
- One missing required section.
- One empty required section.
- Multiple missing sections.
- Wrong heading synonym, such as `## Alternatives`, to decide whether MVP accepts only `## Options`.
- Extra sections that should not fail the required-section contract.
- Case/spacing variations if the parser deliberately supports them.

The open rule to settle during planning is **what counts as empty**. A conservative MVP rule is: a required heading is present but empty when the content before the next required heading is blank or placeholder-only (`TBD`, `TODO`, `N/A`). This should be explicit in test cases rather than inferred from implementation behavior.

### S-04 Integration Contract

F-01 should leave S-04 with a clear target: any AI review handler that receives ADR markdown must return a `ReviewResult` that passes the F-01 graders before output is considered showable to the user.

S-04 will own:

- OpenRouter/LLM adapter.
- Prompt and model configuration.
- Async event handler from `ADRSubmittedForReview` to `AIReviewCompleted`.
- Raw LLM output parsing.
- Runtime trace capture.

F-01 should only define how the output is checked. This keeps the MVP simple while still protecting the product wedge.

## Code References

- `context/foundation/roadmap.md:76-87` - F-01 scope, unlocks, and independence from persistence.
- `context/changes/review-quality-checks/change.md:10-16` - Change note defining minimal verification harness scope.
- `context/changes/review-quality-checks/harness-good-practices.md:26-39` - Prior research summary distinguishing runtime and eval harness responsibilities.
- `context/changes/review-quality-checks/harness-good-practices.md:76-86` - Minimum evaluation harness capabilities.
- `context/changes/review-quality-checks/harness-good-practices.md:112-116` - Lightweight three-layer eval model suitable for F-01.
- `context/changes/review-quality-checks/harness-good-practices.md:169-178` - Mapping of F-01 requirements to deterministic harness practices.
- `context/foundation/prd.md:92` - Required ADR starter template headings.
- `context/foundation/prd.md:110-114` - Annotation classes expected from AI review.
- `context/foundation/prd.md:134-135` - Section-gap and actionability NFRs.
- `context/foundation/prd.md:143-149` - Business logic input/output contract for review.
- `context/foundation/test-plan.md:42-54` - Risk #1 and cheapest MVP protection.
- `context/foundation/test-plan.md:142-150` - Probabilistic eval is deferred post-MVP.
- `context/foundation/application-architecture.md:116-124` - S-04 async runtime review path.
- `backend/domain/adr/value_objects.py:42-62` - Existing review annotation and result value objects.
- `backend/domain/adr/events.py:22-24` - `AIReviewCompleted` carries `ReviewResult`.
- `backend/tests/domain/test_adr.py:86-100` - Existing tests construct review vocabulary but do not grade quality.
- `Justfile:20-21` - Backend pytest command that F-01 should use.

## Architecture Insights

F-01 is the evaluator, not the generator. The evaluator should be deterministic, cheap, and close to the domain/test layer. The generator arrives later as the S-04 runtime path.

The harness should grade structure and contract, not exact LLM prose. This avoids brittle wording assertions and matches the good-practices recommendation to evaluate structured outputs and trajectories rather than final phrasing alone (`context/changes/review-quality-checks/harness-good-practices.md:37-39`, `context/changes/review-quality-checks/harness-good-practices.md:97-99`).

The fixed five-section rule is an MVP product convention, not persisted ADR state. Persistence research says configurable ADR rules can come later and should remain outside the ADR aggregate for now (`context/changes/persistence-scaffold/research.md:158-162`).

Observability should be designed into S-04, but F-01 can start with pytest failures and optional JSON-serializable verdict objects. Structured JSONL traces, token/cost metrics, and OpenTelemetry are useful later but too much for this foundation slice.

## Historical Context

- `context/changes/persistence-scaffold/research.md:34-36` - Review annotations are embedded in ADR for MVP, not modeled as a separate review aggregate.
- `context/changes/persistence-scaffold/research.md:76-77` - The review annotation/result schema that F-01 should grade.
- `context/changes/persistence-scaffold/research.md:158-162` - Five required sections should stay an implementation detail of review/domain validation, not persisted state.
- `context/archive/2026-06-15-testing-critical-path-domain-auth/research.md` - Prior test rollout work established domain/API testing patterns, but does not contain F-01-specific harness design.

## Related Research

- `context/changes/review-quality-checks/harness-good-practices.md` - Web research on agentic runtime and evaluation harness best practices.
- `context/changes/persistence-scaffold/research.md` - Domain aggregate and review annotation storage research that defines the review output shape.
- `context/archive/2026-06-15-testing-critical-path-domain-auth/research.md` - Historical testing research for earlier hardening work.

## Open Questions

1. Should a present but placeholder-only section (`TBD`, `TODO`, `N/A`) count as empty for the MVP grader? Recommendation: yes.
2. Should `## Alternatives` be accepted as an alias for `## Options`? Recommendation: no for MVP; the template/FR contract says `Options`, and configurable conventions are post-MVP.
3. Should all annotation kinds require `suggestion`, or only kinds where a correction is expected? Recommendation: require `suggestion` for `missing_section` and `conciseness`; require at least `location` plus `message` for `inconsistency` until S-04 clarifies richer semantics.
4. Where should reusable parser code live if S-04 uses it directly? Recommendation: pure parser in `backend/domain/adr/`; eval-only case loading and metrics in `backend/tests/review_quality/`.
5. Should F-01 produce persisted reports? Recommendation: no for first MVP pass; pytest output and verdict objects are enough until CI or prompt iteration needs artifact history.
---
date: 2026-06-16T00:00:00+00:00
researcher: Cursor
git_commit: unknown
branch: unknown
repository: adr-flow
topic: "Best practices for creating a harness for agentic systems (eval + runtime)"
tags: [research, harness, evaluation, observability, agentic-systems, review-quality-checks, F-01]
status: complete
last_updated: 2026-06-16
last_updated_by: Cursor
last_updated_note: "Web research via Exa on agent harness and evaluation harness best practices"
---

# Research: Agent harness best practices (for F-01 review-quality-checks)

**Date**: 2026-06-16
**Researcher**: Cursor
**Repository**: adr-flow
**Change**: F-01 — `review-quality-checks`

## Research Question

What are current best practices for creating a harness for agentic systems — both the runtime scaffold around a model and the evaluation harness that verifies agent output — and what applies to adr-flow's minimal review-quality verification harness (F-01)?

## Summary

An **agent harness** is the runtime layer around a foundation model: tools, orchestration, memory, sandbox, policy, and observability. A separate **evaluation harness** runs that agent against tasks, captures full trajectories, grades outcomes, and gates releases. Production quality depends on both, designed together from the start.

For F-01 specifically, the roadmap calls for a **minimal verification harness, not a full review engine**. The research strongly supports building F-01 as an **evaluation harness** with deterministic graders first, full trace capture, and CI gates — not as a general-purpose agent runtime. The product wedge (reliable section-gap detection and actionable annotations) is validated by grading **trajectories and structured outputs**, not final prose alone.

Key takeaways for adr-flow:

1. **Separate runtime from eval** — F-01 is the eval harness; the AI review engine lands in S-04.
2. **Deterministic graders first** — schema validation, required-section checks, and actionability rubrics before any LLM-as-judge.
3. **Golden dataset from day one** — fixture ADRs with known section presence (aligns with `test-plan.md` Phase 1).
4. **Evaluate structure, not wording** — flag the right sections and require concrete corrective actions; avoid asserting exact LLM phrasing.
5. **CI gate with drift tracking** — smoke tier for fast feedback, full regression before S-04 integration.
6. **Observability as architecture** — log every review run (input ADR, prompt version, raw model output, parsed annotations, grader verdicts).

## Definitions

| Term | Meaning |
|------|---------|
| **Agent harness (scaffold)** | System that processes inputs, orchestrates tool calls, manages context, and returns results. You evaluate harness + model together, not the model alone. |
| **Evaluation harness** | Infrastructure that runs tasks concurrently, records every step, grades outputs, and aggregates results. |

**Brain / Hands / Session** model (Anthropic production patterns):

- **Brain** — Model + control loop (stateless inference)
- **Hands** — Sandboxed execution where tools run
- **Session** — Append-only event log of thoughts, tool calls, and observations

## Runtime harness architecture (reference)

Converging practice identifies seven core layers (ETCLOVG taxonomy):

| Layer | Purpose |
|-------|---------|
| Execution environment | Sandboxed, resettable substrate |
| Tool interface | Typed tool registry, schemas, permission gates |
| Context management | Prompt assembly, compaction, progressive skill loading |
| Lifecycle / orchestration | Subagents, delegation, handoffs |
| Observability | Traces, structured logs, cost/latency metering |
| Verification | Self-check hooks, tests, evaluators |
| Governance | Policy engine, approvals, audit trail |

High-leverage separation patterns:

- **Runtime vs. computer** — agent process separate from the machine it controls
- **Think vs. act** — reasoning and execution in distinct trust boundaries
- **Planner / Generator / Evaluator** — do not let one agent grade its own work

These matter for S-04 (the review engine), not F-01 directly — but F-01's graders should assume the review output is produced by a harness that may later adopt these patterns.

## Evaluation harness best practices

### Minimum capabilities per run

1. **Task loading** — versioned golden dataset (production failures, edge cases, adversarial inputs)
2. **Isolated runner** — pinned model, temperature, prompts, tool definitions
3. **Full trace capture** — every observation, action, tool call/result, tokens, latency, timestamps
4. **Grading** — deterministic + model-based + human (hybrid is non-negotiable for production; F-01 can start deterministic-only)
5. **Metric aggregation** — success, cost, latency, safety, slice-based breakdowns
6. **CI gate** — thresholds per environment; track drift over time, not just pass/fail

### Three grader types

| Grader | Best for |
|--------|----------|
| **Deterministic** | Schema checks, regex, structural assertions, "flagged the correct section" |
| **LLM-as-judge** | Faithfulness, tone, rubric adherence — calibrate against humans |
| **Human-in-the-loop** | High-stakes decisions, ground-truth labeling, judge calibration |

**Preference order:** deterministic where possible; LLM judges with an "Unknown" escape hatch and per-dimension rubrics; human review for calibration and high-risk cases.

### Evaluate trajectories, not just final answers

Most agent failures are wrong tool selection or bad context, not bad prose. Score tool-use accuracy, reasoning coherence, error recovery, and end-to-end trajectory quality. For adr-flow: validate that annotations reference the correct ADR sections and include actionable fixes — not that the LLM used specific wording.

### Layered testing stack

**Six-layer model** (Atlan):

- **L0** — Certify data sources before evals
- **L1** — Unit-test individual tool calls (deterministic)
- **L2** — Integration-test multi-step workflows
- **L3** — End-to-end simulation with fault injection
- **L4** — Adversarial / red-team testing
- **L5** — CI gates + continuous production monitoring

**Three-layer eval model** (lighter, suitable for F-01 MVP):

- **L1** — Task completion / structural pass (fast CI gate)
- **L2** — Quality (correct sections flagged, actionability)
- **L3** — Production monitor (post-S-04 deployment)

### Multi-dimensional metrics (production systems)

Beyond accuracy, evaluate as a system:

- **Quality** — task completion, tool selection, reasoning coherence
- **Performance** — latency, throughput
- **Cost** — tokens, invocations, $/task
- **Responsibility** — safety, guardrails
- **Reliability** — error recovery, consistency across perturbations

F-01 MVP scope: **quality** (section-gap detection, actionability) only.

### Isolation and determinism

- Every eval trial starts from a **clean environment** — shared state causes correlated failures and inflated scores
- Pin random seeds, benchmark versions, tool/environment versions
- Separate deterministic bugs from sampling variance; rerun borderline comparisons

### Observability

Observability is a **harness architecture property**, not post-hoc logging.

**Two layers:**

- **Runtime** — logs, traces, health, resource usage, errors with full context
- **Process** — plans, sprint contracts, evaluator rubrics, acceptance criteria

**Instrument at minimum:**

- Every LLM call (prompt, completion, tokens, cost)
- Every tool invocation
- Session/metadata for incident replay
- Custom spans at branching/decision points

**OpenTelemetry** is the converging standard. Start simple: **structured JSONL per session** before adopting a full backend.

**Close the loop:** traces → aggregate failure modes → targeted harness changes.

## Practical build sequence

1. Define task contract — what success means, failure cost, operating budget
2. Build minimal runtime harness — tools, sandbox, hooks, trace recorder *(S-04)*
3. Seed golden dataset — 20–50 high-signal cases from real failures *(F-01)*
4. Add deterministic graders first — fast, cheap CI gates *(F-01)*
5. Add LLM judges — calibrate against human samples *(post-MVP or F-01 stretch)*
6. Wire CI gate — smoke tier (fast) + full regression (release) *(F-01)*
7. Add production monitoring — from day one of S-04 deployment
8. Iterate harness from traces — not just from benchmark scores

**Insight:** harness/scaffold choice can matter as much as model choice. Mid-range difficulty tasks (30–70% historical pass rate) give the best signal for improvement.

## Implications for adr-flow F-01

| F-01 requirement (roadmap / PRD) | Harness practice |
|----------------------------------|------------------|
| Required-section guardrails | Deterministic grader: parse ADR markdown, compare against template section list |
| Actionability guardrails | Deterministic or rubric-based grader: every annotation must include a concrete corrective action |
| ≥80% section-gap detection accuracy | Golden dataset of fixture ADRs with known gaps; measure precision/recall per section |
| Minimal verification harness | L1 + L2 eval layers only; no full agent runtime, no LLM-as-judge in MVP unless calibrated |
| Unlocks S-04 / S-05 | CI gate contract that S-04's review pipeline must pass before merge |
| Parallel with F-02 | Eval harness is independent of persistence — fixture files in repo suffice |

**Anti-patterns to avoid** (from `test-plan.md`):

- Building a full evaluation dataset as MVP gate
- Asserting exact LLM wording instead of structural properties
- The oracle problem (expected value copied from the implementation)

**Recommended F-01 artifact shape:**

```
review-quality-checks/
├── fixtures/          # ADR markdown files with known section gaps
├── graders/           # Deterministic section + actionability checks
├── runner/            # Execute review output (or mock) against fixtures
└── reports/           # Aggregate pass/fail + per-section metrics
```

## Sources

- [Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [AWS — Evaluating AI agents: lessons from Amazon](https://aws.amazon.com/blogs/machine-learning/evaluating-ai-agents-real-world-lessons-from-building-agentic-systems-at-amazon/)
- [ML Digest — How to Evaluate Agentic Systems](https://ml-digest.com/agentic-system-evaluation/)
- [InfoQ — Evaluating AI Agents in Practice](https://www.infoq.com/articles/evaluating-ai-agents-lessons-learned/)
- [Conceptualise — AI Agent Evaluation: Building a Testing Harness](https://www.conceptualise.de/en/blog/ai-agent-evaluation-testing-harness)
- [Atlan — Six-Layer Guide to Testing AI Agent Harnesses](https://atlan.com/know/how-to-test-ai-agent-harness/)
- [NiteAgent — Building an Agent Eval Harness: 500 Runs](https://niteagent.com/blog/building-agent-eval-harness-2026/)
- [LangChain — Improving Deep Agents with harness engineering](https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering)
- [Addy Osmani — Agent Harness Engineering](https://addyosmani.com/blog/agent-harness-engineering/)
- [Walking Labs — Observability inside the harness](https://walkinglabs.github.io/learn-harness-engineering/en/lectures/lecture-11-why-observability-belongs-inside-the-harness/)
- [Rahul Kashyap — Observability in Agent Harnesses](https://rahulkashyap.dev/blog/harness-observability.html)
- [67 AI Lab — Reference Blueprint for a Production Agent Harness](https://67ailab.com/posts/harness-13-reference-blueprint/)
- [innobu — Agentic Harness Engineering framework](https://www.innobu.com/en/agentic-harness-engineering.html)
- [Towards AI — Anthropic harness patterns for long-running agents](https://pub.towardsai.net/stop-calling-it-an-agent-anthropic-calls-it-a-harness-4774d5056e7b)
- [ETCLOVG survey — Agent Harness Engineering (PDF)](https://picrew.github.io/LLM-Harness/main.pdf)
- [arXiv — From Model Scaling to System Scaling](https://arxiv.org/html/2605.26112)
- [Microsoft — Agent Governance Toolkit: Observability & Tracing](https://microsoft.github.io/agent-governance-toolkit/tutorials/13-observability-and-tracing/)
- [Arthur.ai — AI Agent Tracing Python Guide](https://www.arthur.ai/column/ai-agent-tracing-python-guide)
- [UniHarness — Runtime/computer separation](https://github.com/UnicomAI/UniHarness)
- [Parallax — Think/act separation architecture](https://arxiv.org/html/2604.12986v1)
