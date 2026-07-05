---
change_id: review-validation-logs-only
title: Review validation logs only
status: archived
created: 2026-06-19
updated: 2026-07-05
archived_at: 2026-07-05T00:30:11Z
---

## Notes

Superseded by `adr-validation-re-shape` (R-01). The logs-only gate — completing reviews with invalid LLM output after logging validation failures — is replaced by a three-phase pipeline with deterministic static gap detection, parallel per-section ratings, and strict merge validation that fails the review on any validation error.
