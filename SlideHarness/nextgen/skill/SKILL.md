---
name: slideharness-next-planner
description: Author a full evidence-linked deck plan or one isolated replacement slide for a prepared SlideHarness Next App Server run. Use only inside a run workspace after source and template preparation.
---

# SlideHarness Next Planner

Operate in exactly one of these modes:

- Full planning: create `plan/deck_spec.json`.
- Single-slide regeneration: when `regeneration/request.json` exists and the
  task explicitly names it, create `regeneration/proposed_slide.json` only.

The App Server validates, composes, renders, and packages the result. It owns
the merge and never permits the planning turn to rewrite unspecified slides.

## Evidence

Read these prepared artifacts completely:

- `prepared/planning_request.json`
- `prepared/content_model.json`
- `prepared/source_units.json`
- `prepared/coverage_requirements.json`
- `prepared/template_system.json`
- `run_config.json`

When `run_config.json.design_guide` is present, also read
`prepared/design-guide/source_units.json` completely. It is a visual-direction
and image-generation instruction document, not slide content. Apply its tone,
subject treatment, palette guidance, prohibited motifs, crop, texture, and
image-generation constraints without citing it as factual source material.

Treat `inputs/` and `prepared/` as immutable. Do not run the composer, edit the
template, create image files, or modify server state.

## Three-level controls

Use the exact `information_density` and `decorativeness` values from
`run_config.json`, or the target-page overrides in `regeneration/request.json`.

Information density:

- `low`: one primary statement and 1–2 supporting points; generous breathing
  room; prefer statement, title/body, image/text, or two simple columns.
- `medium`: one primary statement and 2–4 supporting points; balanced occupancy;
  prefer compact cards, comparisons, tables, charts, and short processes.
- `high`: one primary statement and 4–6 tightly grouped supporting points;
  prefer native tables, KPI grids, 2x2 cards, 3-column structures, charts, or
  multi-step flows. Do not reduce type below readable limits.

Decorativeness:

- `low`: typography, whitespace, rules, and essential containers only. Do not
  request decorative imagery.
- `medium`: restrained template ornaments and at most one meaningful visual
  focus where it improves comprehension.
- `high`: richer template components and purposeful image generation, diagram,
  chart, or visual accents. Every element must support the message; never fill
  empty space with generic decoration.

Drop shadows remain prohibited at all three levels unless
`run_config.json.allow_shadows` is exactly `true`.

## Graph and flow rendering mode

Obey `structured_visual_mode` for graphs and flow diagrams. Tables remain
native PowerPoint tables in every mode.

- `native`: use `native_chart` for graphs and `process` for flows. Keep labels,
  values, steps, and connectors editable as PowerPoint objects. Select
  `chart_type` from `bar`, `column`, `stacked-bar`, `stacked-column`, `line`,
  `area`, `pie`, `doughnut`, or `scatter`. Use time series for `line`,
  part-to-whole data for `pie` or `doughnut`, numeric x/y pairs for `scatter`,
  and routine category comparison for `bar` or `column`. Never substitute
  `generated_visual`.
- `generated-image`: use `generated_visual` with
  `content.visual.type` set to `chart` or `flow`. Include a stable `asset_id`,
  a concrete `purpose`, a non-empty `required_text` array containing every exact
  label and value, and a prompt containing every required relationship, reading
  order, design-guide constraint, and aspect ratio.
  State the slide's factual conclusion in editable title/message text as well;
  do not leave the meaning only inside pixels.
- `auto`: prefer native objects for exact numbers, dense labels, later editing,
  and routine business diagrams. Choose `generated_visual` only when richer
  visual storytelling materially improves comprehension and the design guide
  supports it. Never choose it merely because decorativeness is `high`.

Generated charts and flows are intentionally not editable. Their image must be
reviewed for label/value fidelity before the deck is accepted.

## Plan contract

- Use only recipe IDs listed in `planning_request.json`.
- Use one primary message per slide and normally 2–5 supporting source units.
- Reference every adopted fact through `source_unit_ids`.
- Cover every required source unit and exact fact without inventing values,
  dates, prices, conditions, or capabilities.
- Prefer a compact slide over multiple thin or repetitive slides.
- Keep charts, tables, and flows as native PowerPoint structures.
- Add an image request only when it materially improves understanding; never
  request imagery just to occupy whitespace.
- Give every requested visual a unique `asset_id`. Do not reuse one image across
  pages unless the request intentionally and explicitly sets `allow_reuse` to
  `true`.
- For an externally sourced image, preserve its exact public URL in
  `source_url` (or `source_urls`) and add a concise `source_note`. Do not add a
  fabricated URL to a host-generated image.
- Do not use drop shadows unless `run_config.json` explicitly sets
  `allow_shadows` to `true`.

The JSON root must contain `title`, `metadata`, and a non-empty `slides` array.
Each slide must contain `slide_id`, `title`, `message`, `recipe`,
`source_unit_ids`, and recipe-appropriate `content`. Use stable sequential IDs
such as `S001`.

Set `metadata.planner` to `codex_app_server`, and copy the active
`information_density`, `decorativeness`, and `structured_visual_mode` values
into metadata. Do not include absolute paths, prompts, source text dumps, or
unsupported fields.

## Single-slide regeneration contract

Read `regeneration/request.json`, the current target object from
`plan/deck_spec.json`, the relevant source units, the available recipes, and the
design guide when present. Write one complete slide object to
`regeneration/proposed_slide.json`.

- Preserve the exact target `slide_id` and its narrative role.
- Address only the supplied page feedback and target policy levels.
- Keep evidence links valid and do not invent facts.
- Change recipe only when the feedback requires it and the replacement recipe
  is available.
- A switch to `generated-image` may introduce one target-owned image request.
  The App Server will pause at image resolution and resume the same isolated
  regeneration after that exact asset ID is uploaded.
- Never write `plan/deck_spec.json`, any other slide, or an entire deck in this
  mode.
