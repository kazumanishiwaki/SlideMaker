---
name: slide-builder
description: Existing-PPT adaptive slide planning and generation. Use when a project contains source.pptx, a manuscript, design.md, and the user wants a new editable PPT that preserves the source deck's visual grammar while changing content safely. Do not use for unrelated document or image tasks.
---

# Slide Builder v0.10

Operate on one slide-project directory. Treat inputs as immutable and the PPTX as a rendered output, not as upstream truth.

## Required principles

1. Never edit `inputs/`.
2. Preserve `source_text`, `semantic_text`, and `render_text` separately.
3. User overrides remain effective until explicitly cleared.
4. Mark only dependent downstream data STALE.
5. Never modify unrelated APPROVED or LOCKED slides.
6. Never fabricate facts, data, or missing conditions.
7. Keep `template_chrome`; replace `content_visual`; preserve `container_or_frame` when feasible.
8. Do not add words, pictures, icons, or ornaments merely to fill space.

## Simplified workflow

```text
Input Analysis
→ Deck Plan
→ Slide Plan
→ Compose
→ Validate
```

Normal generation should require two semantic model turns:

1. create/refine Deck Plan
2. create/refine all Slide Plans

A failed slide may receive at most one semantic re-proposal before it becomes `REVIEW_REQUIRED`.

## Read before planning

When present, read:

- `project.json`
- `inputs/design.md`
- `analysis/manuscript_analysis.json`
- `analysis/template_profile.json`
- `analysis/source_slides.json`
- `analysis/source_assets.json`
- `analysis/design_fingerprint.json`
- `state/project_state.json`
- `planning/deck_plan.json`
- `planning/slide_plans.json`

`visual_plan.json` and `slide_matching.json` are compatibility projections. Do not treat them as separate AI-authored truth.

## Deck Plan

Write one primary message per slide by default. Merge duplicates, split overloaded content, and preserve source conditions. The Deck Plan contains page order, role, message, and source content units.

Stop for structure review when requested. Do not render just because structure planning is complete.

## Slide Plan

Each slide has one compact record containing:

- `message`
- `semantic_chunks`
- `semantic_relation`
- `visual.type / purpose`
- `source.slide_id / mode`
- `layout.family / density / fill_policy / request`
- `image`
- runtime content blocks and mutations

Choose the representation from meaning:

- statement → statement or media
- sequence → process or timeline
- cause/effect → process, cause-effect, or timeline
- comparison → comparison matrix, table, chart, or two-column
- containment/expansion → containment, process, or comparison matrix
- evidence → screenshot, photo-text, chart, table, or comparison matrix
- data → KPI, chart, or table

Do not use a generic relationship layout for cause/effect. Do not use disconnected equal cards for a sequence or containment relation.

## Renderer groups

Public Layout Families map to five deterministic renderers:

```text
statement  cover / section / statement / closing
grid       grid / two_column / comparison_matrix
media      photo_text / full_bleed / photo_grid / screenshot
flow       process / timeline / relationship / cause_effect / containment
data       kpi / chart / table
```

The model never emits absolute `x/y/w/h`. `engine/layout_engine.py` owns geometry.

## Typography

Use presentation-scale typography. In the calibrated sample:

- regular titles are generally 42–52pt
- card titles are at least 22pt
- normal body/card copy is generally 17pt or larger
- notes may be smaller only when truly secondary

Line-break priority:

1. explicit user break
2. `semantic_chunks`
3. punctuation/phrase boundary
4. deterministic font fit

Never rebalance a locked semantic break merely to equalize line lengths.

Correct example:

```text
必要な機能を標準化するから、
導入しやすい
```

## Image handling

Use images when they provide evidence, product understanding, or a useful scene—not as filler.

- prefer actual screenshots/product visuals
- use editable PowerPoint shapes for tables, diagrams, processes, and charts
- use user-supplied images before generation
- target a real source Picture or deterministic layout slot
- crop and grade using the deck art direction
- preserve source Picture shape formatting when replacing its content

Only selected source slides and actual image targets receive detailed analysis. Do not run expensive Vision classification over every source image by default.

## Text adaptation

When content does not fit:

1. remove redundancy
2. restructure
3. compress supporting copy
4. change content region
5. try one layout variant
6. ask for review or propose a split

Shrinking text is the last option. Never repeatedly shorten already-shortened `render_text`; regenerate from source or semantic text.

## QA

Use three categories only.

### Technical

- PPTX validity
- overflow / overlap / out-of-bounds
- image ratio
- editable table/chart/diagram
- template chrome integrity
- mutation-mask Pixel Diff

### Content

- primary message retained
- facts, numbers, and conditions retained
- no production/internal notes in customer copy

### Design

- presentation-scale type
- semantic line breaks
- meaningful visual/layout choice
- balanced deliberate whitespace
- useful image/evidence coverage

Technical and Content Blocking failures stop export. Design findings produce one scoped re-proposal at most, then `REVIEW_REQUIRED`.

## Partial regeneration

Use minimum scope:

- image only → image, render, slide QA, deck harmony
- visual/layout change → slide plan, layout, render, slide QA, deck harmony
- message change → that slide's slide plan and descendants
- merge/delete → affected deck structure and descendants

Never regenerate unrelated slides.

## Decision logging

Log material decisions only:

- deck structure
- primary message
- semantic relation / visual type
- source slide / layout family
- user override
- meaning-changing rewrite
- blocking QA repair

Do not fill Decision Trace with minor coordinate or font adjustments.

## Final export

Export only when required upstream data is current, all required images resolve to real assets, every layout is executable, and Technical/Content blocking QA is zero. Design review status must be visible; it must not silently trigger whole-deck regeneration.
