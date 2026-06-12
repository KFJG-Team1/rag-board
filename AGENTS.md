# Agent Instructions

Before starting work in this repository, read these documents:

- `docs/PR_COLLISION_ATLAS_BRIEF.md`
- `docs/spec.md`
- `docs/rag.md`

Document roles:

- `docs/PR_COLLISION_ATLAS_BRIEF.md`: product purpose, user experience, scope, milestones.
- `docs/spec.md`: overall system architecture, data flow, major components.
- `docs/rag.md`: RAG/analysis architecture, algorithms, input/output contracts.

Working rules:

- Do not modify code unless the user explicitly asks for code changes.
- If the user asks for document work, change documents only.
- Before implementation work, align with the three documents above.
- Treat the existing PostgreSQL import foundation as the current source of truth.
- Prefer this build order: RAG/analysis pipeline, API layer, frontend Path Atlas.
- Frontend renders analysis outputs; it should not own risk logic.
- RAG is a judgment aid, not the product goal.
- Add new tables only when caching, persistence, sharing, or layout stability requires them.
