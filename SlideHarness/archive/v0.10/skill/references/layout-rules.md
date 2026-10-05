# Layout Engine Rules

## Goal

Place semantic content at an appropriate visual scale for the page's purpose while preserving source-PPT visual grammar and `template_chrome`.

A layout is not valid merely because it fits a box, nor is it better merely because it occupies more pixels. The engine must distinguish deliberate whitespace from accidental dead space.

## Responsibilities

Codex chooses:
- semantic layout family
- page-level `fill_policy`
- density / whitespace intent
- title / subtitle / item hierarchy
- which source content objects may be rebuilt
- source objects to inherit text styling from

The deterministic engine chooses:
- safe content canvas
- optional source-derived content region for `preserve_source`
- rows / columns
- exact boxes
- gaps / padding
- content extent
- final coordinates

## Supported v0.9 families

- `grid`
- `process`
- `statement`
- `two_column`
- `photo_text`
- `full_bleed`
- `comparison_matrix`
- `relationship`
- `cover`
- `section`
- `closing`
- `timeline`
- `kpi`
- `chart`

## Structured v0.9 families

- `cover`, `section`, and `closing` are message-led and default to deliberate whitespace. Do not expand supporting copy merely to increase occupancy.
- `timeline` uses native PowerPoint nodes and connectors; chronology labels belong in `date` and semantic headings in `title`.
- `kpi` uses native editable text/panels. Fit the card footprint to the value/label/note cluster instead of stretching empty panels.
- `chart` uses native PowerPoint chart data. It is allowed only when categories and numeric series are supplied; never invent data.
- Source-slide style inheritance remains active for all new families, and `template_chrome` remains outside clear regions.

## Japanese fit

The engine uses a deterministic Japanese/Latin width model before actual rendering. Fit order is: preferred font → smaller size within the role minimum → layout escalation. It must not cross the minimum solely to preserve a requested line count. Actual-render QA then checks kinsoku starts/ends, bracket orphans, number/unit splits, particles stranded at line start, and abnormally short final lines.

## Fill policies

### `preserve_source`

Keep the source slide's meaningful empty zones and visual balance. Prefer the region covered by explicitly cleared source content objects. Do not expand into empty areas simply because they exist.

### `intentional_whitespace`

Use whitespace to focus attention on one strong message, single KPI, quotation, cover, section divider, or closing statement. Low occupied area is acceptable only when the focal cluster has sufficient scale and optical balance.

### `balanced`

Use a moderate amount of the content canvas while retaining breathing room. Suitable for overview, photo + text, case summary, and mixed-content pages.

### `content_filled`

Use the content canvas broadly for comparison, process, table, chart, timeline, and multi-item pages. Large unexplained voids are invalid.

### `full_bleed`

Use when a real image or visual is the dominant element. Do not use this policy for text-only slides or to stretch a weak visual.

## Balanced item geometry

- 2 items: prefer 2×1
- 3 items: prefer 3×1 on wide canvases
- 4 items: prefer 2×2; avoid 3+1
- 5–6 items: prefer 3×2
- 7–8 items: prefer 4×2
- center ragged last rows

Do not use meaningless imagery or duplicate copy merely to increase occupancy.

`full_bleed` is executable only when the slide has a real selected/processed visual asset. The engine must plan the visual slot first, synchronize it into the Image Recipe, place the visual behind template chrome, and reject unresolved imagery at the Final Export Gate.


## Two-column component fit

- `open` is an editorial column with deliberate whitespace.
- `card` uses a restrained source-compatible panel, but its height must be fitted to semantic copy length rather than stretched to the full content canvas.
- Estimate title/body line footprint and inherit source component font scale before centring the cluster.
- A large empty panel is accidental dead space even when its outer bbox raises occupied-area metrics.

## Photo-aware geometry

- `photo_text` resolves image/text sides from semantic request plus Image Recipe negative-space intent.
- `full_bleed` uses the exact presentation size, not a rounded template-profile size.
- Plan image slot geometry before candidate selection; synchronize bbox, target aspect, source lineage, and requested negative space into `planning/image_recipes.json`.
- Reuse a source Picture shape in-place when available. Preserve shape identity, mask, outline, effects, and z-order lineage while moving it to the semantic slot.
- Keep `template_chrome` outside broad clear regions and above full-bleed imagery.
- `comparison_matrix` is a native editable PowerPoint table.
- `relationship` is built from native editable nodes and connectors.

## `LAYOUT_FIT_TO_INTENT`

Each layout plan records, and the effective policy is also appended idempotently to Decision Trace with its reason, confidence, quality result, and rerun scope:
- `fill_policy`
- `content_extent_width_ratio`
- `content_extent_height_ratio`
- `occupied_area_ratio`
- left / right / top / bottom void ratios
- optical center offsets
- expected / rendered semantic item count
- `intentional_whitespace`
- `accidental_dead_space`
- reason codes
- score and pass/fail status

Policy-specific thresholds apply. `intentional_whitespace` and `preserve_source` do not fail merely because edge void is large. They fail when the content becomes a tiny island, loses semantic items, or has no credible focal balance.

A failed fit-to-intent check is blocking QA.

## Template safety

`template_chrome` is outside the mutable semantic region whenever possible. Pixel diff may vary inside the declared layout canvas and explicitly removed source-object regions, but must remain materially stable elsewhere.

## Design continuity
- RECOMPOSE is not a blank-canvas redesign. Preserve recognizable lineage from the source deck.
- Prefer at least one macro cue (axis/grid/whitespace), one component cue (card/frame/numbering), and one micro cue (type/color/line/chrome) when available.
- A slide may use one primary source slide plus at most two supporting component sources.
- Do not add filler visuals merely to create apparent continuity.
- New images inherit deck-wide art direction and must be validated in the rendered slide context.
