# Release v0.9.0 — Real-PPT diversity, structured layouts, and Japanese typography

## Scope

v0.9.0 completes the deterministic implementation stage that precedes live Codex testing:

1. independent real-PPT full-generation validation
2. six additional editable layout families
3. Japanese text fitting and rendered-line diagnostics
4. stronger source-image role classification
5. selective source-slide rendering for large templates
6. regression verification on the Aha! Receipt Lite 9-slide Golden Sample

The old SlideHarness v1 remains retired. This release uses only the complete-rewrite Core.

## Independent real-PPT diversity gate

`examples/external-template-diversity/build.py` accepts real PPT files at runtime and executes:

```text
PPT analysis / Design Fingerprint
→ source-slide selection
→ five-slide RECOMPOSE plan
→ Layout Engine
→ editable PPTX composition
→ actual render
→ output QA
```

The gate was run against five independent PPT files with a total of 90 source slides:

- MIRI general presentation template
- 長楽館 editorial/page-plan deck
- UTokyo leaflet working deck
- minimal multi-master sample template
- Agent Skills promotion deck

Each generated cover / timeline / KPI / editable chart / closing. All 25 generated slides completed with Blocking 0 and Warning 0.

Input PPT bytes are not bundled. The report stores source filenames, hashes, structural metrics, and result paths only.

## Structured editable layout families

New deterministic families:

- `cover`
- `section`
- `closing`
- `timeline`
- `kpi`
- `chart`

Previously supported families remain available:

- `statement`
- `grid`
- `process`
- `two_column`
- `photo_text`
- `full_bleed`
- `comparison_matrix`
- `relationship`

Editable implementation details:

- timeline: native PowerPoint nodes and connectors
- KPI: native text and rounded panels
- chart: native PowerPoint chart data, never a raster substitute
- cover / section / closing: deliberate-whitespace fit policies rather than forced canvas fill

The six-family PoC is under `examples/layout-family-v090/` and passes actual-render QA with Blocking 0 / Warning 0.

## Japanese typography

`engine/japanese_typography.py` is used by composition and actual-render QA.

Implemented:

- deterministic Japanese/Latin glyph-width estimation
- role-specific font fitting with minimum-size protection
- basic line-start and line-end kinsoku
- particle-start rebalancing
- number + unit split detection
- bracket orphan detection
- short final-line detection
- display-only line fitting without promoting `render_text` into `semantic_text`
- a shared role safety factor for physical fitting and display wrapping
- token-boundary title rebalancing when conservative wrap would create a one-to-three-character last line

When a title cannot fit within the role minimum, the engine escalates to layout adjustment rather than shrinking indefinitely.

## Image-role classification

Source picture analysis now records and combines:

- identical hash repetition
- stable geometry repetition even when raster bytes differ
- z-order and large back-layer behavior
- nearest text context and distance
- non-generic shape-name hints
- transparency, saturation, edge density, and aspect
- thin decorative raster geometry
- slide-role context

Seed roles include photo / screenshot / icon / background visual / decorative visual. Low-confidence results remain `unknown` and `review_required`.

MIRI benchmark:

```text
Picture assets        182
Template chrome        48
Content visual         92
Unknown                42
Unknown rate        23.08%
Acceptance threshold   30%
```

## Performance and reliability

- large templates render only the selected source pages needed for mutation-mask QA
- Aha! Receipt Lite source rendering was changed from all 17 pages to the eight actually used source pages
- external templates run in isolated child processes
- source renders produced by authoritative QA are reused instead of invoking LibreOffice twice
- removed text mutation masks include a small render-overflow halo, preventing false Pixel Diff failures caused by font glyphs extending beyond the declared text box

## Still deferred

By project policy, the following remain final-stage tasks:

- live Codex App Server + Sol E2E
- live OpenAI image-generation request
- physical module move from `engine/` into `packages/*`

Additional future families include photo grid, organization/hierarchy, screenshot, and document excerpt.
