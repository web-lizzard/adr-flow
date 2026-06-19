# Lessons Learned

> Append-only register of recurring rules and patterns. Re-read at start by /frame, /research, /plan, /plan-review, /implement, /impl-review.

## Never raise bare DomainError for domain invariants

- **Context**: Backend domain layer — aggregate command methods, rehydrators, and command handlers when rejecting illegal transitions or business-rule violations.
- **Problem**: Raising `DomainError("message")` produces untyped errors (`kind` is always `domain_error`), so API layers and tests must match string messages instead of stable error types. Seen with submit-from-non-draft and edit-while-in-review guards.
- **Rule**: Never raise `DomainError` directly with ad-hoc messages. Always define a dedicated exception class inheriting from `DomainError`, set a stable default message in `__init__` when needed (mirror `AdrInvalidPublishStatus`), and raise that type instead.
- **Applies to**: plan, implement, impl-review

## Keep class public API minimal

- **Context**: Backend domain aggregates (`domain/*/aggregate.py`), application services, and similar classes with a command/query surface plus internal helpers.
- **Problem**: Public transition helpers (e.g. `with_*` on `ADR`) invite callers to bypass command-method guards and invariant checks. The surface blurs which methods are the external contract vs replay-only building blocks.
- **Rule**: Expose only the minimal public API — command methods and factories (e.g. `create`). Prefix internal transition and helper methods with `_` (e.g. `_with_content_updated`).
- **Applies to**: plan, implement, impl-review
