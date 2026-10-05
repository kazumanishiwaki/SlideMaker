# SlideHarness Next v0.11 Specification

## Objective

Generate compact, editable PowerPoint decks from arbitrary manuscripts and
arbitrary PPTX templates. A template may express its identity in masters and
layouts or directly in completed slides. The system must preserve that identity
without copying another implementation.

## Inputs

- One template PPTX.
- One or more Markdown, TXT, DOCX, text-PDF, or PPTX sources.
- An optional host-authored `deck_spec.json`.
- An optional asset manifest keyed by generated-image request ID.
- An optional design/image-generation guide in Markdown, TXT, DOCX, text-PDF,
  or PPTX format. It is ingested separately from factual source material.
- Information density and decorativeness, each set to `low`, `medium`, or
  `high`.
- Graph/flow rendering mode: `auto`, `native`, or `generated-image`.

The local core is deterministic and provider-independent. Signed-in host AI may
author a plan or generated asset, but no provider API key is accepted by the
core.

## Composition modes

### `reconstruct`

Compile theme tokens, repeated chrome, and layout evidence, then create new
slides from native PowerPoint elements. Use this for master/layout-led
templates.

### `source-slides`

Analyze completed source slides, select one reference slide for each Slide
Recipe, clone its OOXML and relationships, replace semantic text slots, remove
unrelated photographic content, and preserve ornamental components. Charts,
tables, and flows remain native PowerPoint objects.

### `auto`

Use `source-slides` when template risk is `high` and the template is
completed-slide-heavy. Otherwise use `reconstruct`.

## Pipeline

1. Ingest sources into immutable source units.
2. Classify claims, facts, conditions, and required coverage.
3. Produce or validate a deck architecture.
4. Compile the PPTX into tokens, chrome, layouts, and pattern evidence.
5. Resolve `auto` composition mode.
6. Plan each slide with a concrete Slide Recipe.
7. Select a source slide when source-slide mode is active.
8. Compose editable PPTX content, attach source-unit speaker notes, and resolve
   image assets without implicit image reuse.
9. Run content, structural, provenance, package-integrity, template-fidelity,
   actual-render, and rendered visual QA.
10. Emit a review packet; automated PASS never means human approval.

## Source-slide selection

Selection is evidence-based and produces `source_slide_map.json`. Signals
include slide order, native table/chart frames, numeric anchors, horizontal and
grid clustering, title semantics, and bounded reuse penalties. Each selection
records its source slide number, score, and reasons.

## Source-slide cloning and replacement

- Clone the complete slide XML tree.
- Recreate internal and external relationships and remap relationship IDs.
- Preserve slide layout relationships.
- Rebuild the cached `Slide.shapes` view after replacing OOXML.
- Protect repeated brand text and edge chrome.
- Replace title, message, number, heading, and body slots in place.
- Clear unused template copy instead of leaving dummy text.
- Delete or clear every unused structural placeholder in final slide XML.
- Treat high-entropy raster content as replaceable photography; keep
  low-entropy raster ornaments and vector-like decoration.
- Keep off-canvas ornamental shapes as chrome, not semantic content.

## Native editability

- Tables are generated as PowerPoint tables.
- Charts are generated as PowerPoint charts.
- Processes are individual PowerPoint text/shape components.
- Native charts include visible value labels.
- Generated text uses fixed font sizes; automatic shrink-to-fit is prohibited.
- Generated images are restricted to decorative or photographic roles and do
  not replace tables. They may replace charts or flows only when the explicit
  structured-visual policy permits it.

## Graph and flow rendering policy

- `native` uses editable PowerPoint charts and individual flow shapes with
  connectors. The QA layer rejects `generated_visual` on these pages.
- `generated-image` uses `generated_visual` and one target-owned image request.
  The editable title/message retains the factual conclusion; the image prompt
  carries every required label, value, relationship, reading order, and design
  constraint. QA rejects native chart/process recipes for the selected page.
- `auto` prefers native structures for exact data and later editing, and permits
  generated visuals only when richer visual storytelling materially improves
  comprehension.

During isolated page regeneration, a switch to generated-image may pause in
`regeneration_awaiting_images`. Uploading the matching asset ID resumes the same
revision request; non-target isolation checks still run before commit.

Automatic generated images pass a second, image-input Codex review before they
enter the asset manifest. Prompt alignment, composition, visual coherence,
slide usability, and artifact freedom must all score at least 4/5 with no
blocking issue. A rejected first variant is regenerated once from one targeted
improvement instruction. Only review-PASS images enter the content-addressed
cache; exhausted retries return to manual image resolution. Deterministic QA
then checks format, minimum dimensions, aspect ratio, visual variation, and any
required text independently.

Resolved image paths are single-use by default, including command-line and
template-preview fallbacks. Reuse requires `allow_reuse: true` on the specific
asset request. A rejected duplicate remains `awaiting_image` and records the
conflicting asset ID.

External assets declare a stable `asset_id`, exact `source_url` or
`source_urls`, and optional `source_note`. Generated images do not invent an
external URL. Simple process connectors are created before nodes so they remain
behind labels and entity shapes.

## Effects policy

Drop shadows are disabled by default. The composer removes `outerShdw` and
`prstShdw` effects from generated and cloned source slides, and structural QA
blocks any remaining unrequested drop shadow. Shadows are preserved only when
the deck metadata contains `"allow_shadows": true` or the build receives the
explicit `--allow-shadows` option.

## Three-level controls

Information density controls grouping and recipe selection, not only a label:

- `low`: one primary statement and 1–2 supports with deliberate breathing room.
- `medium`: one primary statement and 2–4 supports with balanced occupancy.
- `high`: one primary statement and 4–6 grouped supports, favoring native
  tables, grids, charts, and flows while retaining readable type.

Decorativeness controls the permitted visual budget:

- `low`: essential typography, rules, containers, and template structure;
  unrelated source-slide decoration is removed.
- `medium`: restrained template ornament and one purposeful visual focus.
- `high`: richer template components and purposeful generated imagery or
  diagrammatic accents, never generic whitespace filler.

The registered design guide governs image tone, subject placement, palette,
texture, crop, and prohibited motifs. It never becomes content evidence.

## Isolated page regeneration

Page regeneration accepts a stable `slide_id`, feedback, expected revision, and
optional page-specific density/decorativeness values. Codex may write only a
single proposed slide object. The App Server validates and merges that object;
the planning turn cannot rewrite the deck plan.

The core builds a full candidate in a temporary revision workspace, then copies
only the target slide and its private OOXML dependency closure into the current
PPTX. A changed dependency shared with another page blocks the update. Before
commit, every non-target page is fingerprinted from its slide XML,
relationships, and recursive dependency closure. The update is committed only
when every fingerprint is identical. `qa-page-isolation.json` records the proof,
and the previous plan/PPTX are snapshotted under `versions/rev-NNNN/`. Any
dependency that belonged only to the old target closure and is absent from the
replacement closure is removed, along with its content-type override, so an
isolated revision cannot leave orphan media, charts, notes, or relationship
parts behind.

## QA artifacts

- `qa-content.json`: source-unit and required-condition coverage.
- `qa-structural.json`: bounds, density, voids, fonts, conservative fixed-frame
  text-capacity checks, unresolved assets, native editability, and leftover
  placeholder markers.
- `qa-package.json`: ZIP CRC, required package parts, XML readability,
  content-type coverage, relationship targets and referenced relationship IDs,
  presentation slide registration, empty placeholders, chart axis/cache
  consistency, byte-identical preservation of original theme parts, and
  reachability of slide-owned media, chart, diagram, embedding, and slide parts.
  Template findings are identified separately from regressions, but broken
  output package relationships remain blocking.
- `qa-provenance.json`: presence and validity of each slide's path-free
  `[Sources]` speaker-note block against ingested source-unit IDs, exact URLs in
  adopted source text, and declared external asset IDs/URLs.
- `qa-template-fidelity.json`: preserved source components/chrome per slide.
- `qa-render.json`: LibreOffice PDF/PNG render and blank-render detection.
- `qa-visual.json`: rendered-page edge density and quiet-band measurements,
  high-confidence generated text-container overlap, generated-text coverage,
  one-line title wrapping, and PDF word-height checks. Quiet bands are reconciled
  with the PPTX semantic-content extent so light template rules are not mistaken
  for missing content. Frequent explicit PPTX fonts are also compared with
  `pdffonts` evidence; unresolved substitutions become explicit review findings.
  Findings are either `blocking` or explicit `review` cues for full-size review.
- `review_packet.json`: human review checklist and pending approval state.
- `qa-page-isolation.json`: target page, dependency changes, and before/after
  fingerprints for every non-target page after isolated regeneration.

Source-slide mode uses template-adaptive density thresholds because intentional
whitespace in a selected completed slide is part of the design evidence. It
still blocks unexplained large voids, missing source decoration, unresolved
assets, out-of-bounds semantic content, and non-native structural visuals.

Final verification fails closed when render QA is `SKIP`. A caller may opt into
render skipping only for a draft with the explicit `--allow-render-skip` flag;
that exception is recorded in the summary as `render_policy: skip_allowed`.
Visual QA is `SKIP` whenever render QA is unavailable and follows the same
draft-only exception. A successful final source build requires provenance and
visual QA `PASS`. Final verification after isolated regeneration receives the
original template and sources again, so theme preservation and speaker-note
provenance are checked on the merged PPTX rather than inferred from the
candidate build.
