# Lessons Learned

> Append-only register of recurring rules and patterns. Re-read at start by /frame, /research, /plan, /plan-review, /implement, /impl-review.

## Never raise bare DomainError for domain invariants

- **Context**: Backend domain layer — aggregate command methods, rehydrators, and command handlers when rejecting illegal transitions or business-rule violations.
- **Problem**: Raising `DomainError("message")` produces untyped errors (`kind` is always `domain_error`), so API layers and tests must match string messages instead of stable error types. Seen with submit-from-non-draft and edit-while-in-review guards.
- **Rule**: Never raise `DomainError` directly with ad-hoc messages. Always define a dedicated exception class inheriting from `DomainError`, set a stable default message in `__init__` when needed (mirror `AdrInvalidPublishStatus`), and raise that type instead.
- **Applies to**: plan, implement, impl-review
