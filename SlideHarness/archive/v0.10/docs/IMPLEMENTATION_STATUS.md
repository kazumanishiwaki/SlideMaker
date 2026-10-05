# Implementation status — v0.10.0

## Current position

SlideHarness v0.10 is a simplification release of the complete-rewrite core.

```text
Immutable inputs
→ Input Analysis
→ Deck Plan
→ Slide Plan
→ Compose
→ Validate
```

## Implemented

- compact `planning/slide_plans.json`
- deterministic legacy-view projection for Visual Plan / Source Match
- standard two-call planning contract
- one-repair-call limit per slide
- five internal renderer groups
- semantic-layout allowlist
- explicit semantic line-break preservation
- page-scoped feedback / STALE
- Technical / Content / Design QA categories
- local word filtering for actual-render PDF text matching
- source/content/render text separation
- source image treatment and editable PPTX composition

## v0.10 Golden Sample

- Aha! Receipt Lite, 9 slides
- correct semantic title break
- larger presentation typography
- three evidence/media pages plus editable tables and flows
- corrected cause-effect / sequence / containment semantics
- Technical, Content, Design failures: 0
- Image Harmony failures: 0
- Deck Harmony warnings: 0

## Deferred

- live Codex App Server + Sol
- live OpenAI image generation
- physical `packages/*` split
- additional Layout Family expansion

These remain deferred until the simplified core and human-reviewed Golden Sample are stable.
