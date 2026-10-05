# SlideHarness v0.10 implementation instructions

Read `docs/SIMPLIFICATION_v0.10.0.md`, `README.md`, and `docs/IMPLEMENTATION_STATUS.md` before changing the system.

## Architecture

- UI/App Server host: `server.mjs`, `src/`, `public/`
- deterministic engine: `engine/`
- agent workflow: `skill/`
- run state: `workspace/<project>/`

## Source-of-truth rules

1. Never mutate `inputs/`.
2. Output PPTX is not upstream truth.
3. Keep `source_text`, `semantic_text`, and `render_text` separate.
4. User overrides beat automatic decisions.
5. Change only dependent downstream nodes to STALE.
6. Do not change unrelated APPROVED or LOCKED slides.
7. Preserve template chrome; replace content visuals; keep frames when feasible.

## Simplified planning boundary

AI-authored planning is limited to:

- `planning/deck_plan.json`
- `planning/slide_plans.json`

Visual Plan, Source Match, Fill Policy, Image Intent, and Continuity are fields or deterministic projections of Slide Plan. Do not reintroduce separate model calls for them.

Normal planning uses two model calls. One slide may request at most one semantic repair proposal before `REVIEW_REQUIRED`.

## Layout

The model never emits absolute coordinates. Map public families into five deterministic groups:

- statement
- grid
- media
- flow
- data

Use the semantic compatibility table in `engine/planning.py`. Add a new rule only when a real Golden Sample cannot be expressed with an existing relation/family pair.

Explicit user/Slide Plan line breaks are locked semantic boundaries. Do not rebalance them for equal line length.

## QA

Keep only three user-relevant categories:

- Technical
- Content
- Design

Technical and Content blocking failures stop export. Design findings are review items and must not create unbounded repair loops.

## Performance

- Analyze all source assets lightly; inspect only selected source slides deeply.
- Render representative pages and changed pages; avoid whole-deck renders after every phase.
- Keep PDF text matching shape-local.
- Cache source renders by file hash.
- Do not log insignificant coordinate or font adjustments in Decision Trace.

## Current Golden Sample

`examples/aha-receipt-full-deck/aha-receipt-lite-golden-v0.10.0.pptx`

It must retain the exact title break:

```text
必要な機能を標準化するから、
導入しやすい
```

Do not expand Layout Families, split physical packages, or run live Codex/OpenAI integration until this simplified Golden Sample remains human-approved and actual-render QA passes.
