---
name: n2p-slide-illustration
description: Create and manage consistent n2p-style generated illustrations for PPTX proposal decks after the deck has been drafted. Use when working on n2p PPTX slides or proposal materials and the user asks to add, generate, retake, replace, or manage content-aware slide illustrations with gpt-image2, including conceptual diagrams, workflow visuals, metaphorical illustrations, abstract visuals, and isometric business/system illustrations. This skill selects only slides where an illustration improves understanding, generates images in a fixed n2p tone, stores prompts and intent beside each image, inserts the selected version into the PPTX, and preserves retake history.
---

# n2p Slide Illustration

## Purpose

Add generated illustrations to existing n2p PPTX proposal decks without changing the deck's tone. Be conservative: generate illustrations only when they clarify content, not to decorate every slide.

Use this skill together with the root `n2p-pptx` skill. The root skill controls slide layout, brand color, typography, logo, and footer rules; this skill controls illustration planning, generation, asset management, and retake history.

## Workflow

1. Inspect the PPTX or its generation script after the deck content exists.
2. Select candidate slides using `references/selection-and-style.md`.
3. For each selected slide, decide the image type, aspect ratio, placement, and why the illustration improves understanding.
4. Create or update the image asset folder with `scripts/create_image_slot.py`.
5. Write `intent.md` and `prompt-vN.md` before generating.
6. Generate with direct `gpt-image2` access when available for polished raster illustration. Keep the illustration's visual craft, but avoid baking important text into the image.
7. Save generated files as `image-vN.png` or `image-vN.webp` in the slide folder.
8. Insert the accepted version into the PPTX and add labels or explanatory copy as editable PPTX text. Never overwrite older generated versions.
9. When the user requests a retake, append to `retake-log.md`, create the next prompt/version when a raster image changes, and update the PPTX to use the adopted version or editable layout.

## Asset Layout

Use one folder per illustrated slide under the deck/project workspace. Do not write deck-specific assets, logs, prompts, generated images, or test outputs inside this skill directory; keep the skill redistributable and clean.

```text
generated-assets/<deck-name>/slide-04/
  intent.md
  prompt-v1.md
  image-v1.png
  prompt-v2.md
  image-v2.png
  retake-log.md
```

Use `slide-XX` with the actual slide number from the PPTX. Add a short suffix only when the slide has multiple image slots, for example `slide-07-flow`.

## Selection Rules

Default to a restrained density. For an 8-12 page proposal deck, start with 2-4 illustrated slides unless the content clearly needs more.

Prioritize slides with:

- abstract concepts that need a mental model
- before/after contrast
- process, workflow, or stakeholder flow
- relationship between teams, systems, users, or decisions
- dense text where a visual anchor would reduce cognitive load
- a key argument that should be memorable

Do not add generated illustrations to every slide. Avoid adding images to simple agenda slides, section dividers, or summary slides unless the user asks or the visual materially improves comprehension.

## Style Rules

Default illustration tone:

- white background
- black or dark gray linework and simple fills
- n2p yellow only as a small accent
- calm Japanese business proposal tone
- keep generated image text to a minimum; labels and explanation should be editable PPTX text
- 3D isometric visuals are allowed when they clarify systems, teams, or operations
- avoid all shadows, perspective/tilted views, glossy effects, loud gradients, ornate decoration, and generic AI-looking visuals

For the full type mapping, prompt blocks, and negative constraints, read `references/selection-and-style.md`.

## Retake Rules

Humans decide whether a retake is needed. Do not auto-retake based only on model self-critique.

When retaking:

- keep all previous images and prompts
- create the next version number
- write the human instruction exactly in `retake-log.md`
- state what changed in the new prompt
- update the PPTX to use only the adopted version

Use `references/retake-workflow.md` for the log format and common retake patterns.

## Generation Routes

Use this priority order:

1. Direct Codex-accessible image generation with `gpt-image2` if available.
2. A local or product integration through Codex App Server when the project provides one.
3. Browser-operated ChatGPT image generation only as a fallback when the user approves or explicitly requests it.

Before implementing a new direct API or App Server integration, verify the current OpenAI/Codex documentation because model names and App Server surfaces can change.

## PPTX Insertion Guidance

Place illustrations based on slide content:

- left text / right illustration for explanation slides
- central illustration for process or relationship slides
- wide illustration for flows
- small supporting illustration when text is primary

Do not over-decompose a polished illustration into PPTX primitives. The expected pattern is a finished textless or low-text illustration image plus editable PPTX labels. Only rebuild with PPTX shapes when the generated image cannot support later edits or when the user explicitly asks for shape-level editability.

Use flat, front-facing, orthographic compositions. Do not use drop shadows, cast shadows, perspective tilt, angled screens, isometric camera angles, or depth cues that make the image look three-dimensional.

Keep vertical height conservative. Leave room for the h1 area, lead copy, footer, and any slide-native explanation; do not fill the slide with a single tall raster image.

Keep existing n2p layout rules intact: margins, footer, logo, typography, and yellow usage remain controlled by the `n2p-pptx` skill.
