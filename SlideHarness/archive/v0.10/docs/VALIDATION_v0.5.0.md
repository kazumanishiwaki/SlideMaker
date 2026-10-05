# Validation Report v0.5.0

**Date:** 2026-08-17  
**Scope:** Image Pipeline / PowerPoint in-place image replacement / actual-render QA / Codex App Server host regression

## Validation result

```text
npm test
11 / 11 test groups PASS
```

Test groups:

- App Server JSONL / streaming / approval
- dependency state / STALE / LOCK
- Deck QA
- project skeleton
- Design Continuity
- editable composition
- repeated LibreOffice render
- Image Pipeline
- intentional-whitespace render QA
- Pixel Diff
- Layout Engine

## Image Harmony PoC

```text
prepared assets              4
selection provider           auto -> local
image harmony blocking       0
image harmony warning        0
deck image coherence warning 0
output QA blocking           0
output QA warning            0
```

Validated behaviors:

- source content visual extraction and lineage
- local candidate ranking
- target-slot crop
- focal-point / negative-space handling
- deck-wide grading
- effective resolution
- source Picture relationship in-place replacement
- source Picture shape ID / geometry / rotation / mask retention
- actual rendered slot change
- mutation-area Pixel Diff
- same-slide visual-series handling
- cross-slide near-duplicate detection
- Recipe Override minimal STALE propagation

## Runtime smoke test

```text
PPT Codex App Server client: http://127.0.0.1:4317
Codex connection is lazy; use the UI Connect button.
```

## Environment doctor

Available:

- Node.js
- npm
- Python
- LibreOffice
- pdftocairo
- pdftotext
- python-pptx
- python-docx
- Pillow
- jsonschema

Not available/configured in this container:

- Codex CLI
- `OPENAI_API_KEY`

Therefore the following are implemented but not counted as live-success validation:

- real Codex App Server + Sol turn
- real OpenAI image generation request

Local/manual image selection, image treatment, PowerPoint replacement, rendering and QA are validated deterministically.
