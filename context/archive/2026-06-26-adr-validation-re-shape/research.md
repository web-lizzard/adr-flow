---
date: 2026-06-26T12:00:00+00:00
researcher: Composer
git_commit: 89d7742fe276303916c463abb9bd479e4fa6a5da
branch: main
repository: adr-flow
topic: "ADR validation reshape — pre-LLM static analysis + per-section parallel LLM with 0–5 ratings"
tags: [research, codebase, adr, validation, llm, review-quality, section-ratings]
status: complete
last_updated: 2026-06-26
last_updated_by: Composer
last_updated_note: "Added per-section 0–5 rating rubric grounded in ADR best practices and rubric design literature"
scope_notes: "Extend annotations with per-section 0–5 ratings; parallel LLM calls; supersedes S-07 mechanism"
---

# Research: ADR Validation Reshape

**Date**: 2026-06-26
**Researcher**: Composer
**Git Commit**: `89d7742fe276303916c463abb9bd479e4fa6a5da`
**Branch**: main
**Repository**: adr-flow

## Research Question

Changes to the LLM/EM validation logic:

- **Today**: one LLM call reviews the entire document; post-LLM `validate_review_result` checks whether relevant sections are missing (among other rules).
- **Proposed**:
  1. Missing-section detection becomes **static analysis** during a **pre-LLM validation phase** (before any model work).
  2. Documents are divided into sections; each section is evaluated **separately** by the LLM via **parallel** calls.
  3. Each per-section LLM agent is independent and returns a **0–5 compliance rating** for that section's requirements.
  4. Final output records: **(a)** static-analysis conclusions (missing sections) and **(b)** per-section LLM conclusions (ratings + feedback), **alongside** existing annotation kinds.

**Scope decisions (confirmed):**

- Output model: **extend** `ReviewResult` with section ratings; keep `missing_section` / `inconsistency` / `conciseness` annotations.
- Parallelism: **parallel LLM calls** (`asyncio.gather`).
- S-07: **superseded** — new validation shape replaces the F-01 post-LLM gate story (not the user outcome of delivering review output).

## Summary

The codebase already has production-ready **static section parsing** in `domain/adr/required_sections.py` (`parse_adr_sections`, `find_missing_or_empty_sections`) that is today used as an **oracle** for post-LLM validation and duplicated in the fake LLM — not as a pre-LLM gate. The reshape **promotes this parser to Phase 0** of review: deterministic `missing_section` annotations with templated suggestions, then **5+ parallel structured LLM calls** (one per `SectionName`, plus optional cross-section tasks for inconsistency/conciseness) that return **per-section 0–5 ratings** merged into an extended `ReviewResult`.

Primary implementation surface:

| Layer | Change |
|-------|--------|
| **Pre-LLM static phase** | New builder in application/domain: gaps → `missing_section` annotations before any `LlmCompletionPort` call |
| **Per-section LLM** | `AdrReviewService.review_adr` → `asyncio.gather` over section-scoped prompts; merge payloads |
| **Schema** | Add `SectionRating` + `section_ratings` on `ReviewResult`; extend `ReviewPayload` / prompts |
| **Handler** | `RunAiReviewHandler` can keep retry loop but `validate_review_result` missing-section leg becomes redundant |
| **API / UI** | Router currently flattens annotations only — ratings need new response fields and UI |

This reshape **supersedes S-07's mechanism** (keep `validate_review_result` unchanged, log F-01 failures) while preserving its user outcome (deliver review output). It **forces a redesign** of S-09 re-review eligibility (`len(annotations) > 0` breaks when static gaps always produce annotations). F-01's **parser half promotes to runtime**; its **LLM missing-section precision/recall grader** is largely obsolete. PRD FR-010–012 and the 80% section-gap NFR need reframing.

## Detailed Findings

### Current pipeline (single LLM + post-LLM validation)

```
ADRSubmittedForReview
  → RunAiReviewHandler (up to 2 attempts)
      → AdrReviewService.review_adr(full markdown)
          → 1× LlmCompletionPort.complete_structured(ReviewPayload)
      → validate_review_result(markdown, result)
          → find_missing_or_empty_sections vs missing_section annotations
          → actionability checks
      → on pass OR exhausted retries → AIReviewCompleted
      → on final exception → AIReviewFailed
```

Key files:

- Handler orchestration: `backend/application/handlers/run_ai_review.py:62-144`
- Single LLM call: `backend/application/services/adr_review_service.py:18-39`
- Post-LLM validator: `backend/application/review_quality.py:24-32`
- Monolithic prompt (asks LLM to detect gaps): `backend/domain/adr/review_instructions.py:9-32`
- Output wire schema: `backend/domain/adr/review_llm_schema.py:29-57`

S-07 has partially landed: validation failures no longer block completion when the LLM returns parseable output (`run_ai_review.py:130-137`), but `validate_review_result` still runs for measurement and drives retry feedback (`:85-102`).

### Static analysis — already exists, not used pre-LLM

`backend/domain/adr/required_sections.py` provides pure-domain capabilities:

| Function | Lines | Behavior |
|----------|-------|----------|
| `REQUIRED_SECTION_HEADINGS` | 6-12 | Exact `## Context`, `## Options`, etc. |
| `parse_adr_sections` | 49-75 | Splits markdown into per-section bodies |
| `find_missing_or_empty_sections` | 78-85 | Missing heading, empty body, or placeholder (`tbd`/`todo`/`n/a`) |

`ParsedAdrSections.body_for(section)` returns per-section text for LLM prompts (`:39-46`). Caveats: headings are **case-sensitive**; `## Alternatives` does not map to Options.

Today static analysis is consumed:

1. **Post-LLM** — `validate_review_result` compares parser gaps vs LLM `missing_section` annotations (`review_quality.py:85-101`)
2. **Fake LLM** — `FakeLlmCompletionPort` duplicates gap detection (`fake_completion.py:28-37`)
3. **F-01 harness** — golden fixtures vs `find_missing_or_empty_sections` (`tests/review_quality/`)

It is **not** called before the real LLM in `AdrReviewService` or `RunAiReviewHandler`.

### Proposed pipeline (target architecture)

```
Phase 0 — Static (no LLM)
  gaps = find_missing_or_empty_sections(markdown)
  static_annotations = [ templated missing_section per gap ]
  static_summary = { missing: [section names], present: [...] }

Phase 1 — Per-section LLM (parallel)
  parsed = parse_adr_sections(markdown)
  tasks = [
    review_section(section, parsed.body_for(section), section_requirements)
    for section in SectionName
  ]
  + optional cross-section task (Decision+Status inconsistency)
  + optional document-level task (conciseness)
  section_results = await asyncio.gather(*tasks)

Phase 2 — Merge
  section_ratings = [ { section, score: 0-5, feedback } per result ]
  llm_annotations = merge annotation payloads from section + cross-section calls
  ReviewResult(
    annotations = static_annotations + llm_annotations,
    section_ratings = section_ratings,
    reviewed_at, reviewed_content,
  )

Phase 3 — Handler
  validate (actionability on LLM annotations; optional rating schema checks)
  → AIReviewCompleted
```

**Recorded outputs (user requirement):**

1. **Static analysis conclusions** — which sections are missing/empty (deterministic); surfaced as `missing_section` annotations with `location` (e.g. `## Context`) and templated `message`/`suggestion`.
2. **Per-section LLM conclusions** — `section_ratings` tuple with `section`, `score` (0–5), `feedback`; plus any `inconsistency`/`conciseness` annotations from cross-section or section-scoped LLM work.

### Per-section rating rubric (0–5)

This rubric defines how each `SectionName` is scored. It follows rubric-design guidance to use **observable, measurable criteria** with **clear grade distinctions** ([Microsoft Copilot Studio rubric best practices](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/kit-rubrics-best-practices)), and aligns section expectations with established ADR literature: Nygard's original Context/Decision/Status/Consequences model ([Cognitect, 2011](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)), MADR's problem/options/drivers structure ([MADR template](https://adr.github.io/madr/)), Zimmermann's seven-question review checklist ([ADR review practices](https://ozimmer.ch/practices/2023/04/05/ADRReview.html)), and agent-readiness checks ([Vercel ADR skill review checklist](https://github.com/vercel/ai/blob/08cdf6ae/skills/adr-skill/references/review-checklist.md)).

#### Design principles

| Principle | Application |
|-----------|-------------|
| **Score 0 is static-only** | Assigned by `find_missing_or_empty_sections` before any LLM call. No model invocation for absent/placeholder sections. |
| **Scores 1–5 are LLM-assigned** | One parallel structured call per present section, using the section-specific rubric below. |
| **Problem vs solution separation** | Context must stay problem-focused; solution language in Context caps the score at 1–2 (common anti-pattern in ADR review literature). |
| **Actionability at 4+** | Scores 4–5 require content a future reader (or coding agent) could act on without clarifying questions. |
| **Honest tradeoffs** | Consequences and Options sections penalize cherry-picking (only positives, straw-man alternatives). |
| **Proportionality** | Short but complete sections can score 4; verbosity without substance does not earn 5 (economy axis from [ADR-49 proportionality rubric](https://rigor.typedduck.fail/reference/adr/49-adr-authoring-guidelines/)). |

#### Universal score anchors

These anchors apply to every section. Section-specific tables below add **what "on-topic" means** for each heading.

| Score | Label | Universal meaning |
|-------|-------|-------------------|
| **0** | Absent | Heading missing, body empty, or placeholder-only (`tbd`/`todo`/`n/a`). **Determined by static analysis — not scored by LLM.** |
| **1** | Off-topic / wrong role | Body exists but does not serve this section's purpose: unrelated subject matter, content belonging in another section, or solution-pitch where problem/context is required. |
| **2** | Topic-adjacent, insufficient | Touches the right area but too vague, assumes tribal knowledge, or misses mandatory elements for this section (see per-section table). |
| **3** | Adequate draft | Reader understands intent; section fulfills its role partially but lacks specificity, tradeoffs, or evidence needed for confident use. |
| **4** | Strong | Meets ADR conventions for this section: specific, balanced, actionable; only minor improvements possible. |
| **5** | Exemplary | Would pass expert ADR review checklists with no material gaps; concise and complete for the decision's stakes. |

#### Section-specific criteria

##### Context (`## Context`)

*Purpose (Nygard/MADR):* Value-neutral description of forces, constraints, and the problem — **not** the chosen solution.

| Score | Criteria |
|-------|----------|
| 0 | Static gap |
| 1 | Content unrelated to the architectural decision; implementation/solution details dominate; reads as a technology pitch rather than a problem statement |
| 2 | Problem implied but unclear; acronyms/systems undefined; no trigger (what changed or will break); tribal knowledge assumed |
| 3 | Problem understandable; missing one of: current state, constraints (time/budget/tech), scope boundary, or competing forces |
| 4 | Clear problem-focused context: trigger, current state, constraints, and scope; value-neutral language; 3–5 substantive paragraphs or equivalent ([ork ADR checklist](https://github.com/yonatangross/orchestkit/blob/main/plugins/ork/skills/architecture-decision-record/checklists/adr-review-checklist.md)) |
| 5 | Above plus quantified drivers where relevant (load, cost, users), links to issues/prior ADRs, and explicit forces in tension |

**Common score caps:** Solution language in Context → max **2**. Single sentence with no constraints → max **2**.

##### Options (`## Options`)

*Purpose (MADR/Zimmermann):* Genuine alternatives with real tradeoffs — not a post-hoc justification of an already-made choice.

| Score | Criteria |
|-------|----------|
| 0 | Static gap |
| 1 | Lists unrelated technologies, restates the Decision as the only path, or describes implementation steps instead of alternatives |
| 2 | Only one substantive option, or "do nothing" straw man; no pros/cons; options cannot plausibly solve the stated problem |
| 3 | Two or more options named but comparison is thin; missing rejection rationale or unbalanced pros/cons |
| 4 | ≥2 genuine alternatives, each with real pros **and** cons; chosen option's advantage over rejected ones is inferable; options could solve the problem ([Zimmermann Q2–Q3](https://ozimmer.ch/practices/2023/04/05/ADRReview.html)) |
| 5 | MECE decision drivers, explicit tradeoff prioritization when criteria conflict, and clear why each rejected option was ruled out |

**Common score caps:** Only one option listed → max **2**. Options that don't address Context problem → max **1**.

##### Decision (`## Decision`)

*Purpose (Nygard):* Active-voice statement of **what we will do** — specific enough to implement.

| Score | Criteria |
|-------|----------|
| 0 | Static gap |
| 1 | Hedging without commitment ("consider", "might"), discusses options without recording a choice, or contradicts Options/Context |
| 2 | Names a direction but not actionable: no technology/version, unbounded scope, passive voice, or "use a better approach" vagueness |
| 3 | Specific choice stated but missing bounded scope (what's in/out), implementation approach, or measurable success criteria |
| 4 | Active voice ("We will…"); named technology/approach; clear scope; another team could start implementation ([Vercel agent-readiness](https://github.com/vercel/ai/blob/08cdf6ae/skills/adr-skill/references/review-checklist.md)) |
| 5 | Fully implementable without clarifying questions; explicit non-goals; constraints referenced from Context |

**Common score caps:** Passive voice only → max **3**. No specific technology/approach named → max **2**.

##### Status (`## Status`)

*Purpose (Nygard/Fowler):* Lifecycle state of **this** decision — must align with Decision content.

| Score | Criteria |
|-------|----------|
| 0 | Static gap |
| 1 | Value unrelated to the recorded decision (e.g. document draft state), or contradicts Decision (Decision says "Accepted" but Status says "Rejected") |
| 2 | Valid lifecycle word but ambiguous or generic ("In progress") without tying to the architectural choice |
| 3 | Reflects decision state at high level (Proposed/Accepted/Deprecated) but lacks clarity on whether the team has committed |
| 4 | Clear, standard status (`Accepted`, `Proposed`, `Deprecated`, `Superseded by ADR-NNN`) consistent with Decision |
| 5 | Above plus validity period, review/revisit trigger, or supersession link when circumstances would warrant re-evaluation ([Microsoft WAF ADR guidance](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record), [Fowler ADR bliki](https://martinfowler.com/bliki/ArchitectureDecisionRecord.html)) |

**Note:** Status/decision **inconsistency** is also checked by a separate cross-section LLM call (existing `inconsistency` annotation kind). A rating ≤2 here should correlate with an inconsistency annotation when both sections have substantive content.

**Common score caps:** Contradicts Decision → max **1**.

##### Consequences (`## Consequences`)

*Purpose (Nygard):* **All** outcomes — positive, negative, and neutral — after the decision.

| Score | Criteria |
|-------|----------|
| 0 | Static gap |
| 1 | Unrelated outcomes, restates Decision verbatim, or aspirational fluff ("will improve quality") with no concrete effect |
| 2 | Only positive consequences, or only vague negatives ("may be harder to maintain"); disguised restatement of Decision |
| 3 | Mix of positive and negative but shallow; operational impact (monitoring, on-call, debugging) not addressed |
| 4 | Balanced, honest assessment: ≥2 substantive positives and ≥2 substantive negatives/tradeoffs; explains why each matters ([ork consequences checklist](https://github.com/yonatangross/orchestkit/blob/main/plugins/ork/skills/architecture-decision-record/checklists/adr-review-checklist.md)) |
| 5 | Quantified where possible (latency, cost, team impact); long-term maintenance cost; follow-up tasks identified (migrations, tests, docs) |

**Common score caps:** Only positives listed → max **2**. No negatives when Decision has clear tradeoffs → max **3**.

#### Static vs LLM responsibility split

```
find_missing_or_empty_sections(markdown)
  → gap sections: score = 0 (static), emit missing_section annotation, SKIP LLM call
  → present sections: invoke LLM with section body + section rubric → score 1–5 + feedback
```

This resolves the prior open question on missing sections: **score 0 is assigned statically; LLM is not invoked for gaps.**

#### LLM output contract per section

Each parallel section call returns structured JSON:

```json
{
  "section": "Context",
  "score": 4,
  "feedback": "Problem and constraints are clear. Add a quantified scale driver (e.g. request volume) to reach exemplary.",
  "annotations": []
}
```

- `score` must be 1–5 for present sections (0 is never LLM-assigned).
- `feedback` is required, actionable, and references specific gaps or strengths (aligns with PRD actionability NFR).
- `annotations` optional per section: `conciseness` for verbose sections (especially Context); section-scoped quality notes. `missing_section` annotations come **only** from static phase.

#### Cross-section and document-level checks (unchanged annotation kinds)

| Check | Owner | Output |
|-------|-------|--------|
| Missing sections | **Static** | `missing_section` annotations + rating 0 |
| Decision ↔ Status alignment | **Cross-section LLM** | `inconsistency` annotation when substantive mismatch |
| Verbose bodies | **Section LLM (Context primary) or doc-level call** | `conciseness` annotation with trim suggestion |

#### Aggregate metrics (for NFR replacement)

| Metric | Definition | Replaces |
|--------|------------|----------|
| **Section coverage** | % of sections with score ≥ 1 (i.e. not statically gap) | 80% section-gap detection NFR (now trivially 100% for gaps via static) |
| **Section quality** | Mean score across present sections; flag any section ≤ 2 | New primary quality NFR candidate |
| **Review readiness** | All sections ≥ 3 AND no `inconsistency` annotations | "Clean review" for S-09 eligibility |
| **Actionability** | Every annotation has required fields; every rating has non-empty `feedback` | Existing actionability NFR |

**Suggested S-09 re-review trigger (proposal):** any section rating ≤ 2 **or** any `inconsistency`/`conciseness` annotation — excludes deterministic `missing_section` from static analysis so incomplete ADRs are handled by ratings/annotations separately.

#### Prompt embedding guidance

Per-section system prompts should include:

1. The universal anchor table (scores 1–5 only).
2. The section-specific criteria table for that `SectionName`.
3. Common score caps as hard rules ("never assign 4 if only one option is listed").
4. Instruction to cite specific phrases from the section body in `feedback`.
5. Reminder: return JSON only; do not emit `missing_section` (gaps are pre-computed).

Example prompt fragment for Context:

> Score 1 if the text is unrelated to the architectural decision or reads as a solution pitch. Score 2 if the problem is vague or assumes tribal knowledge. Score 3 if intent is clear but constraints or scope are missing. Score 4 if problem, current state, constraints, and scope are value-neutral and clear. Score 5 if exemplary per MADR context guidance with quantified drivers and explicit forces.

### Extension points for parallel per-section LLM

| Location | Role |
|----------|------|
| `adr_review_service.py:18-39` | **Primary fork** — replace single `complete_structured` with `asyncio.gather` |
| `required_sections.py:49-75` | Feed per-section bodies into prompts |
| `review_instructions.py:9-32` | Split monolithic system prompt into section-scoped + cross-section variants |
| `review_instructions.py:35-53` | Add `build_section_user_message`; filter `validation_feedback` per section |
| `review_llm_schema.py:29-57` | Add section rating payload + `merge_review_payloads` |
| `fake_completion.py:18-65` | Mirror per-section behavior for local dev/tests |

**Cross-section rules cannot be isolated to one section:**

- Inconsistency (Decision vs Status): `review_instructions.py:24-27`, `fake_completion.py:39-46`
- Conciseness (often doc-wide): `review_instructions.py:28-30`, `fake_completion.py:48-56`

Recommendation: **5 parallel section calls + 1 cross-section call** (Decision+Status) + optional document-level conciseness call, or fold conciseness into Context section call with full-doc length hint.

**Concurrency:** No rate limiting today. Five section calls × two handler attempts = up to 10–12 LLM requests per review. Consider `asyncio.Semaphore` or a config knob.

**Handler / ports:** `AdrReviewPort.review_adr(markdown, validation_feedback) -> ReviewResult` can stay unchanged if merge is internal. `RunAiReviewHandler` retry loop remains one `review_adr` per attempt.

### ReviewResult schema extension

Current domain model (`value_objects.py:51-71`):

```python
class ReviewResult(BaseModel):
    annotations: tuple[ReviewAnnotation, ...]
    reviewed_at: datetime
    reviewed_content: str | None = None
```

Proposed addition (backward-compatible if optional):

```python
class SectionRating(BaseModel):
    section: str  # SectionName value
    score: int      # 0–5, validated
    feedback: str

class ReviewResult(BaseModel):
    annotations: tuple[ReviewAnnotation, ...]
    section_ratings: tuple[SectionRating, ...] = ()
    reviewed_at: datetime
    reviewed_content: str | None = None
```

**Persistence:** `adrs.review_annotations` JSONB stores full `ReviewResult.model_dump()` (`adr_projection.py:64-81`). Optional `section_ratings` key requires **no column migration** — old rows deserialize with default `()`.

**API gap:** `_to_adr_response` maps **annotations only** (`adr.py:388-411`). Ratings are silently dropped unless `SectionRatingResponse` + `section_ratings` are added to `AdrResponse`.

**Frontend gap:** `AdrReviewAnnotations.vue` groups by annotation kind only. Ratings need new UI (score + feedback per section). Empty state logic (`after_review` + zero annotations) must account for ratings-only reviews.

### Validation model changes (supersedes S-07)

| Today (S-07 + F-01) | After reshape |
|---------------------|---------------|
| LLM discovers missing sections | Static analysis discovers gaps **pre-LLM** |
| `validate_review_result` cross-checks LLM vs parser | Missing-section leg **redundant** if gaps never from LLM |
| `validation_feedback` retry fixes false neg/pos | Retry only for LLM annotation actionability / rating schema |
| `handler.run_ai_review.validation_failed` logs F-01 parity | Logs shift to rating validation, partial parallel failures |
| 80% section-gap NFR measures LLM recall | Gap detection **deterministic** — NFR reframed to rating quality |

S-07 user outcome (always deliver LLM output in `after_review`) remains compatible. S-07 plan item "do not change `validate_review_result`" (`review-validation-logs-only/plan.md:41`) is **obsolete** under this change.

### Impact on S-09 conditional re-review

S-09 defines "errors" as non-empty actionable annotations (`conditional-adr-re-review/research.md:143-160`, `roadmap.md:197`).

With static `missing_section` annotations, **every incomplete ADR automatically has annotations** → always eligible for re-review under `len(annotations) > 0`.

With per-section ratings, a structurally complete ADR may have **zero LLM annotations** but five ratings — eligibility undefined.

**Product decisions needed before S-09:**

1. Rating threshold (e.g. any section ≤ 2 counts as error)?
2. Exclude deterministic `missing_section` from re-review trigger?
3. Are ratings user-visible or internal metadata?

### F-01 harness fate

| Component | Fate |
|-----------|------|
| `required_sections.py` parser | **Promotes to production** (pre-LLM) |
| Missing-section precision/recall grader | **Demoted** — regression on static synthesis only |
| Actionability grader | **Retained** for LLM-generated inconsistency/conciseness |
| Golden fixtures (`complete.md`, etc.) | **Retained** for parser + aggregation tests |
| New harness work | Section rating schema, parallel merge, rating-threshold calibration |

## Code References

- `backend/domain/adr/required_sections.py:6-89` — static parser and gap detection
- `backend/application/review_quality.py:24-111` — current post-LLM validator
- `backend/application/handlers/run_ai_review.py:62-144` — retry loop and completion paths
- `backend/application/services/adr_review_service.py:18-39` — single LLM call (primary extension point)
- `backend/domain/adr/review_instructions.py:9-53` — monolithic prompt + validation feedback
- `backend/domain/adr/review_llm_schema.py:14-57` — LLM wire schema and mapping
- `backend/domain/adr/value_objects.py:51-71` — `ReviewResult` / `ReviewAnnotation`
- `backend/infrastructure/llm/fake_completion.py:28-56` — fake duplicates static + heuristic LLM rules
- `backend/infrastructure/adapters/persistence/projections/adr_projection.py:64-81` — JSONB persistence
- `backend/infrastructure/api/routers/adr.py:388-411` — API flattens annotations only
- `frontend/app/components/adr/AdrReviewAnnotations.vue` — annotation-only UI
- `backend/tests/review_quality/grader.py:9-50` — F-01 eval harness

## Architecture Insights

1. **Clean separation today** — domain parser, application validator, service orchestration, handler gating are already distinct layers. Reshape moves gap detection earlier without violating layer boundaries.
2. **Fake LLM is a blueprint** — `fake_completion.py` already uses `find_missing_or_empty_sections` pre-annotation; production should follow the same pattern, then narrow LLM scope.
3. **Merge contract** — handler, events, and projection expect one `ReviewResult` per review. Parallel calls must converge to a single merged result before `_complete_review`.
4. **Placeholder duplication** — `_PLACEHOLDER_TOKENS` exist in both `required_sections.py:28` and `review_instructions.py:6-7`; unify during implementation.
5. **`ParsedAdrSections` not exported** from `domain.adr.__init__` — export or import from `required_sections` when application layer uses it for prompts.
6. **Cross-section rules** need explicit design: extra parallel call vs sequential post-pass vs embedding Decision+Status bodies in both section prompts.

## Historical Context (from prior changes)

- `context/changes/review-validation-logs-only/research.md` — S-07 assumes F-01 post-LLM gate; reshape supersedes that mechanism while preserving deliver-output outcome.
- `context/changes/review-validation-logs-only/plan.md` — Phase 1 handler changes landed; Phase 2–3 may be moot or need rework under reshape.
- `context/changes/conditional-adr-re-review/research.md` — S-09 eligibility predicate must be redesigned for ratings + static gaps.
- `context/changes/valid-adr-example/research.md` — two-level validation (parser vs post-LLM) becomes three-level (pre-LLM static → per-section LLM → merge validation).
- `context/archive/2026-06-16-review-quality-checks/plan.md` — F-01 defined LLM-vs-parser grading; parser promotes to runtime.
- `context/archive/2026-06-18-llm-refactor/plan.md` — explicitly kept post-LLM gate; reshape reverses that decision.
- `context/foundation/roadmap.md:26,171-181` — S-07 as post-core focus; reshape should be documented as new slice superseding Stream B measurement story.
- `context/foundation/prd.md:110-115,134-135` — FR-010–012 and section-gap NFR assume single-call annotation model.

## Related Research

- `context/changes/review-validation-logs-only/research.md` — S-07 blocking vs logs-only (superseded mechanism)
- `context/changes/conditional-adr-re-review/research.md` — re-review eligibility and event model
- `context/changes/valid-adr-example/research.md` — canonical ADR fixture and validation levels
- `context/archive/2026-06-18-llm-refactor/research.md` — handler retry and validation gate analysis

## Open Questions

1. ~~**Section rating rubric**~~ — **Resolved.** See [Per-section rating rubric (0–5)](#per-section-rating-rubric-05) above.
2. ~~**Missing sections and ratings**~~ — **Resolved.** Score 0 assigned statically; skip LLM for gap sections.
3. **Annotation overlap** — can LLM still emit `missing_section`, or is that kind static-only after reshape? *(Recommendation: static-only.)*
4. **Re-review eligibility (S-09)** — adopt proposed threshold (rating ≤ 2 or inconsistency/conciseness annotation)?
5. **User-visible output** — show ratings in review panel immediately, or annotations only with ratings as metadata?
6. **Partial parallel failure** — if 2 of 5 section calls fail, complete with partial ratings or `_fail_review`?
7. **Cost/latency budget** — 5–7 parallel calls per submit vs PRD FR-008 "one AI review" wording.
8. **F-01 replacement metrics** — adopt mean section score + review-readiness threshold as new NFRs?
9. **S-07 disposition** — close as superseded or finish Phase 2–3 tests before reshape lands?
10. **PRD amendment scope** — FR-010–012 output model, NFR reframing, FR-008 call-count semantics.
11. **Rubric calibration** — golden fixtures with expected scores per section for harness regression (Microsoft recommends ≥80% alignment on rubric grading).

## External Sources (rating rubric research)

- [Documenting Architecture Decisions (Nygard, Cognitect 2011)](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions) — original Context/Decision/Status/Consequences semantics
- [Architecture Decision Record (Martin Fowler)](https://martinfowler.com/bliki/ArchitectureDecisionRecord.html) — brevity, status lifecycle, explicit consequences
- [MADR template and primer](https://adr.github.io/madr/) — Context/Options/Decision Drivers/Consequences structure
- [How to review ADRs — Zimmermann checklist](https://ozimmer.ch/practices/2023/04/05/ADRReview.html) — seven review questions, actionability, repeatability
- [Vercel ADR skill review checklist](https://github.com/vercel/ai/blob/08cdf6ae/skills/adr-skill/references/review-checklist.md) — agent-readiness, problem/solution separation
- [Microsoft Azure WAF — ADR guidance](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record) — tradeoffs, confidence level, revisit triggers
- [ork ADR review checklist](https://github.com/yonatangross/orchestkit/blob/main/plugins/ork/skills/architecture-decision-record/checklists/adr-review-checklist.md) — per-section quality indicators and red flags
- [ADR-49 authoring guidelines (proportionality rubric)](https://rigor.typedduck.fail/reference/adr/49-adr-authoring-guidelines/) — stakes-weighted economy axis
- [Microsoft Copilot Studio — rubric best practices](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/kit-rubrics-best-practices) — observable criteria, clear grade distinctions, 80% alignment target
- [NC State rubric best practices](https://teaching-resources.delta.ncsu.edu/rubric_best-practices-examples-templates/) — analytic rubrics with parallel descriptors per level
