---
date: 2026-06-16T00:00:00+00:00
researcher: Cursor
git_commit: unknown
branch: unknown
repository: adr-flow
topic: "Harness good practices for agentic systems (eval + runtime)"
tags: [research, harness, evaluation, observability, agentic-systems, review-quality-checks, F-01]
status: complete
last_updated: 2026-06-16
last_updated_by: Cursor
last_updated_note: "Web research via Exa on agent harness and evaluation harness best practices"
---

# Harness good practices (for F-01 review-quality-checks)

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
