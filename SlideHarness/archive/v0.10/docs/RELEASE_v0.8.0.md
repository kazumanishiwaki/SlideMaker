# Release v0.8.0 — Calibration + Safe Feedback

## Completed

### Aha! Golden Sample calibration
- cover now preserves recognizable source-template orange chrome instead of clearing the whole source page
- process/grid card height is fitted to semantic text density rather than inflated to canvas occupancy
- closing CTA now surfaces 30-minute demo / quote request / Lite vs full-version consultation
- fit-to-intent remains blocking-safe; no filler content is added

### Safe page feedback
New deterministic `engine/feedback.py` supports:
- primary_message
- visual_type
- source_slide
- layout_family
- layout_density
- render_text

Every change writes Decision Trace + version history and marks only the dependent phases STALE. `render_text` changes never promote into `semantic_text` or `source_text`.

### App Server bridge
- `ProjectStore.applyFeedback()` added
- `/api/projects/:id/feedback` endpoint added
- LOCK / STALE_LOCKED are respected

### UI verification
The complete-rewrite UI already has the intended three screens:
1. Input
2. Structure / production
3. Final review

Local server health and all three screen nodes were verified.

## Generic full-generation compatibility
- MIRI native source template: 3-page full-generation / actual-render QA PASS (blocking 0, warning 0)
- generated v0.6/v0.5 decks were not accepted as independent external-template compatibility fixtures; they expose duplicate-slide OOXML / render limitations and are not counted as diversity coverage

## GitHub migration
- `legacy-v1-final` branch exists and points at the original v1 commit
- clean v2 source package is ready
- default-branch replacement is still pending because the current GitHub connector does not provide bulk local-directory upload; do not claim main has been replaced until the full source tree is actually present there
