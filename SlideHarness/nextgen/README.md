# SlideHarness Next (Greenfield MVP)

`nextgen/` is the current source-of-truth implementation. The retired v0.10
engine is preserved only under `../archive/v0.10/` and is not imported.

The first vertical slice supports:

- compiling an arbitrary PPTX into design tokens, layout evidence, and repeated chrome,
- reporting when brand decoration is completed-slide-heavy and cannot be fully inherited from masters,
- selecting concrete slide recipes from semantic content,
- composing editable cards, comparisons, KPI blocks, native charts, tables, and flows,
- placing a resolved image while emitting an asset request for unresolved generated imagery,
- structural Design QA, OPC/PPTX package QA, per-slide source-note provenance,
  LibreOffice actual-render QA, and rendered visual QA for text collisions,
  extreme whitespace, missing text, title wraps, and text size.

The second vertical slice adds:

- Markdown, TXT, DOCX, text-PDF, and PPTX source ingestion,
- immutable `source_text` plus normalized `semantic_text`,
- exact fact and required-condition tracking,
- a host-AI planning request/response boundary with no local provider key,
- deterministic fallback architecture with full source-unit coverage,
- cover, section, callout, two-column, three-column, and closing recipes.

The third vertical slice adds completed-slide adaptation:

- evidence-based source-slide selection per recipe,
- exact OOXML slide and relationship cloning,
- semantic text-slot replacement while retaining source ornament,
- natural-photo removal without discarding low-entropy raster decoration,
- native table and editable process replacement,
- source-slide fidelity QA and template-adaptive density QA,
- `auto`, `reconstruct`, and `source-slides` composition modes.

The App Server control and revision slice adds:

- an optional, separately ingested design/image-generation instruction document,
- three-level `low` / `medium` / `high` controls for information density and decorativeness,
- per-page overrides during regeneration,
- isolated one-page regeneration with optimistic revision locking,
- automatic version snapshots and OOXML dependency fingerprints proving every
  unspecified page is unchanged.
- a graph/flow rendering choice between editable PowerPoint-native structures
  and richer host-generated images.

See [SPEC.md](SPEC.md) for the artifact contracts and mode-selection rules.

## Quick start

Use the bundled Codex Python runtime (it includes `python-pptx`, Pillow, and lxml):

```bash
export SLIDEHARNESS_PYTHON=/Users/kazuma/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3

$SLIDEHARNESS_PYTHON -m slideharness_next.cli build \
  --template examples/test-case/inputs/source.pptx \
  --spec examples/representative/deck_spec.json \
  --image examples/representative/assets/generated-template-system.png \
  --out-dir examples/representative/output
```

Run tests:

```bash
$SLIDEHARNESS_PYTHON -m unittest discover -s tests -p 'test_*.py'
```

The command writes canonical intermediate JSON, the editable PPTX, a PDF/PNG
render, a montage, and QA reports into the output directory. `qa-package.json`
checks ZIP integrity, XML readability, content-type registration, presentation
slide registration, every referenced relationship ID, empty structural
placeholders, chart axis/cache integrity, and byte-identical preservation of
the template theme. It also walks the OPC relationship graph and rejects
unreachable slide-owned media, charts, diagrams, and slide parts.
`qa-provenance.json` verifies each source-backed slide's `[Sources]`
speaker-note block, including exact URLs found in source claims and declared
external asset URLs. `qa-visual.json` measures the rendered pages, checks
generated text coverage, font-resolution evidence, and one-line title wrapping,
and separates blocking failures from human-review cues.

Structural QA also blocks unmistakable fixed-frame text-capacity failures. This
guards compact template labels without treating every intentionally tight
source text box as an error.

## Codex App Server

The primary entry point is now a loopback-only Codex App Server:

```bash
npm start
```

Open `http://127.0.0.1:4318`. The browser uploads the template and each source
as separate bounded binary requests. A design/image-generation guide can be
registered separately so its visual rules do not become slide facts. The server
uses the signed-in Codex App Server session to author `plan/deck_spec.json` for
the initial build, one `regeneration/proposed_slide.json` object for a page
revision, and requested generated-image assets; the Python core then
validates, composes, renders, and packages the deck. No provider API key is
accepted or required.

After completion, choose one slide and regenerate it with page-specific density,
decorativeness, and feedback. The server builds a candidate deck, copies only
the target slide package subtree into the current PPTX, and refuses the update
if any non-target page fingerprint changes. Previous revisions are retained
under the run's `versions/` directory. Target-private media and other dependency
parts that the replacement no longer references are removed together with stale
content-type overrides before package QA runs.

Environment check:

```bash
npm run check:next-app
```

Automatic image generation uses the same signed-in Codex App Server connection;
no external image command or provider API key is required. The server checks
the advertised `imageGeneration` capability, starts one isolated `imagegen`
turn per uncached asset, consumes the native `imageGeneration.savedPath`
completion result, and submits the result to an isolated image-input quality
review. Prompt alignment, composition, visual coherence, slide usability, and
artifact freedom must all score at least 4/5 with no blocking issue. A rejected
first variant is regenerated once with one targeted correction. Only PASS
images enter the content-addressed cache and asset manifest; deterministic
format, dimension, aspect-ratio, visual-variation, and exact-text QA still runs
before the build resumes. Capability, usage-limit, timeout, exhausted retry, or
QA failures return the run to the existing manual upload state. The CLI can also
accept an `--asset-manifest`; `--image` remains a single-image shortcut and
`--no-template-preview` makes unresolved image requests blocking.
Each resolved image path is consumed once by default. Give each visual its own
asset and asset ID; reuse is accepted only when the request explicitly sets
`allow_reuse: true`.

An authorized live quality test consumes signed-in image-generation usage and
writes the accepted image plus its quality report under
`nextgen/examples/image-quality-test/`:

```bash
npm run test:next-image-live
```

Scanned PDF pages with fewer than 24 extractable characters are rasterized and
processed locally with Tesseract (`jpn+eng` by default). OCR text, line boxes,
confidence, page hashes, and preprocessing metadata are retained in source
units and `qa-ocr.json`. Low-confidence pages fail closed instead of being
silently corrected by a generative model.

Build directly from a manuscript:

```bash
$SLIDEHARNESS_PYTHON -m slideharness_next.cli build-source \
  --template examples/test-case/inputs/source.pptx \
  --source examples/source-pipeline/brief.md \
  --information-density medium \
  --decorativeness medium \
  --out-dir examples/source-pipeline/output
```

`--composition-mode auto` is the default. Use `--composition-mode reconstruct`
or `--composition-mode source-slides` to force a mode. Source-slide builds also
write `source_slide_map.json` and `qa-template-fidelity.json`. Source-backed
builds also write path-free `source_notes.json`; the final PPTX stores the same
source-unit IDs in each slide's speaker notes under `[Sources]`.
URLs embedded in adopted source units remain exact. An externally sourced image
can declare `source_url` or `source_urls` plus `source_note` in its image/visual
object; provenance QA blocks the deck if that asset citation is missing from the
final notes.

Drop shadows are opt-in. Builds remove them by default; use `--allow-shadows`
or deck metadata `{"allow_shadows": true}` only when the design instruction
explicitly requests shadows.

Graphs and flows accept `--structured-visual-mode auto|native|generated-image`;
`native` is the backward-compatible default.
Native mode keeps charts, steps, and connectors editable. The `native_chart`
recipe supports bar, column, stacked bar/column, line, area, pie, doughnut, and
scatter charts. Generated-image mode uses the `generated_visual` recipe and
requires `required_text` for chart or flow labels. Tables always remain native.

Each run writes `usage.json`. Deterministic stages, Codex planning, image
generation, duration, cache hits, and available host token counts are recorded.
Exact prepared inputs can reuse a previously QA-PASS plan; OCR and generated
images also use content-addressed caches. Every cache hit still passes through
the same composition and QA gates.

Actual render QA is required for a passing final build. `--no-render` produces
`SKIP`, which fails closed unless the caller also supplies the explicit
draft-only `--allow-render-skip` flag.

Rendered visual QA is also required after a successful render. It blocks
high-confidence text-container collisions, near-empty non-sparse slides,
extreme continuous whitespace, missing generated text, wrapped one-line titles,
and unreadably small rendered words. Generated text uses fixed font sizes rather
than silent auto-shrink. Borderline whitespace or text size is retained as a
`review` finding and surfaced in
`summary.json` without pretending that automated PASS is human approval.

This writes `source_manifest.json`, `source_units.json`, `content_model.json`,
`coverage_requirements.json`, and `planning_request.json` before composition.
Pass a signed-in host-authored deck plan with `--plan`; when omitted, the local
core uses a deterministic fallback and labels it as such.

Automated PASS is not human approval. Every successful build writes
`review_packet.json` with `SAMPLE_REVIEW` for a three-page proof or
`FINAL_REVIEW` for a full montage. Completed-slide-heavy templates are marked
`REVIEW_REQUIRED` in `template_risk_report.json` instead of being described as
fully inherited.
