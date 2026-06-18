---
change_id: llm-refactor
title: Refactor LLM layer — domain instructions, structured output, thin adapters
status: implemented
created: 2026-06-18
updated: 2026-06-18
archived_at: null
---

## Notes

Refactor `backend/infrastructure/llm`: move review instructions and structured-output schema to domain, introduce thin LLM provider adapters, and centralize review business logic in a domain-facing service.
