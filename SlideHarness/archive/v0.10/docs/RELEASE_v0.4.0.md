# Release v0.4.0 — Design Continuity & Art Direction

## Added
- `analysis/design_fingerprint.json`: source deck design DNA (composition, typography, color roles, image treatment).
- `analysis/component_catalog.json`: reusable source layout/component catalog with a constrained mixing policy.
- `planning/continuity_plan.json`: per-slide lineage plan for macro / component / micro inheritance.
- `planning/deck_art_direction.json`: deck-wide image/visual direction to keep generated assets coherent.
- `planning/image_recipes.json`: per-slide image recipe seeds for photo/illustration/screenshot visuals.
- `qa/continuity_qa.json`: `SOURCE_CONTINUITY` check; RECOMPOSE cannot silently become blank-canvas redesign.
- GUI continuity summary: source lineage and inherited design DNA are visible under the existing disclosure UI.

## UX principle
The UI may say a slide is “based on” a source slide only when the continuity plan contains traceable inherited cues. It does not hide the amount of adaptation; it communicates the lineage that makes the result feel like the same deck.

## Image principle
New raster images are not considered finished when generated. They must follow deck art direction, target slot geometry, and source frame treatment, and should ultimately be evaluated after being placed into the rendered slide.
