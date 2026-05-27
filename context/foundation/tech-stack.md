---
project_name: adr-flow
architecture_mode: split
components:
  frontend:
    product_type: web
    starter_id: nuxt
    package_manager: pnpm
    hints:
      language_family: js
      deployment_target: vercel
      bootstrapper_confidence: verified
      quality_override: false
      path_taken: custom
      dev_tooling:
        formatter: prettier
        linter: eslint
        type_checker: typescript
  backend:
    product_type: api
    starter_id: fastapi
    package_manager: uv
    hints:
      language_family: python
      deployment_target: fly
      bootstrapper_confidence: first-class
      quality_override: false
      path_taken: standard
      dev_tooling:
        formatter: ruff
        linter: ruff
        type_checker: ty
hints:
  team_size: solo
  ci_provider: github-actions
  ci_default_flow: auto-deploy-on-merge
  path_taken: custom
  self_check_answers: null
  has_auth: true
  has_payments: false
  has_realtime: false
  has_ai: true
  has_background_jobs: true
---

## Why this stack

ADR Flow is a hosted web app with email/password auth, per-user ADR storage, and one-shot AI review on publish — a natural split between a Nuxt UI and a Python API. Nuxt (Vue, SSR via Nitro) fits a markdown editor, card-based history, and status-driven flows on a tight three-week, after-hours MVP; Vercel is the default deploy path. FastAPI carries Pydantic-typed request/response models, OpenAPI for agent-friendly boundaries, and async-friendly handlers for review jobs triggered from `draft` → `in_review`, with Fly.io as the API home. GitHub Actions auto-deploys on merge. Auth and persistence live in the backend; the frontend calls the API — no realtime collaboration in MVP. Ruff + ty on the API and Prettier/ESLint/TypeScript on the UI keep both sides explicit and convention-aligned for solo development.
