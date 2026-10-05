# Selection and Style Guide

## Candidate Selection

Use a conservative first pass. The goal is to clarify the deck, not to make it visually busy.

Score each slide from 0-2 for each item:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Concept abstraction | concrete | partly abstract | highly abstract |
| Process/relationship | none | simple relation | multi-step or multi-party |
| Text density | light | moderate | dense |
| Strategic importance | supporting | useful | core argument |
| Visual replaceability | visual would decorate | visual helps | visual changes comprehension |

Initial rule: illustrate slides scoring 6 or higher. If too few slides are selected, lower the threshold to 5 after reviewing deck intent. If too many are selected, keep the highest strategic importance slides first.

## Illustration Type Mapping

| Slide intent | Preferred image type | Use when |
|---|---|---|
| Explain a structure | concept diagram | the slide names parts, layers, tradeoffs, or causes |
| Show steps | workflow visual | the slide describes a sequence, handoff, review, or operation |
| Make a claim memorable | metaphor illustration | the slide needs emotional recall without becoming decorative |
| Create atmosphere | abstract visual | cover-like or transition moments need a restrained visual anchor |
| Show system/team overview | isometric business/system view | multiple actors, systems, or workspaces need a bird's-eye view |

Prefer one polished illustration concept per slide. The illustration may remain a raster image, but important text must stay editable in PPTX. Do not bake labels, step names, rules, or explanatory copy into the generated image unless the user explicitly asks for that.

## Aspect Ratio Decision

Choose based on intended placement:

- Right column: 4:3 or 1:1
- Center-wide flow: 16:9
- Concept mark or metaphor: 1:1
- Isometric workspace/system: 4:3 or 16:9

If uncertain, generate at a flexible horizontal ratio and crop/fit inside the PPTX with clear margins.

## Base Prompt Block

Include this block in every prompt:

```text
Create a clean n2p proposal slide illustration on a pure white background. Use black and dark gray linework, simple gray fills, and very small n2p yellow accents only. Keep the style calm, minimal, business-oriented, flat, front-facing, and suitable for a Japanese proposal deck. Avoid all shadows, perspective tilt, isometric camera angles, strong gradients, glossy surfaces, decorative particles, excessive depth of field, and generic AI-looking decoration.
```

## Text and Editability Rules

Default: put text in PPTX, not inside generated images. The slide's native text has priority over image text, while the image carries the visual metaphor or scene.

Use generated image text only when:

- the label is extremely short
- the text is not duplicated by slide body text
- the user explicitly wants the label baked into the image
- the image will not need later editing

Prefer editable PPTX text for:

- Japanese labels
- step names
- rules
- before/after text
- arrows and callouts
- anything likely to be revised by a director

Avoid long explanations, small UI text, dense tables, and tiny labels inside generated images. If a generated image contains too much text, do not use it as-is; recreate the structure with PPTX shapes or regenerate a textless version.

Do not replace a useful illustration with plain PPTX shapes just to make every visual primitive editable. Editability is required for text; the visual can stay raster.

Keep illustration detail moderate. Prefer the clarity of a simple proposal diagram over a highly polished, dense, or over-produced illustration. If the image starts to look like a finished infographic on its own, simplify it.

## Negative Prompt Block

Add or adapt this block:

```text
Do not use photorealistic people, stock-photo style, manga style, hand-drawn sketch style, neon colors, vivid gradients, glassmorphism, glowing blobs, any shadows, perspective tilt, angled screens, isometric camera angles, busy backgrounds, clutter, tiny unreadable text, fake detailed UI screenshots, or decorative elements that do not explain the slide.
```

## Prompt Template

```text
Slide: <slide number and title>
Purpose: <what the viewer should understand faster because of this image>
Image type: <concept diagram | workflow visual | metaphor illustration | abstract visual | isometric overview>
Composition: <where objects sit; how many groups; expected aspect ratio>
Labels: <prefer "no labels"; if needed, list only labels that cannot be placed in PPTX>
Style: <base prompt block>
Content details: <slide-specific objects and relationships>
Avoid: <negative prompt block plus slide-specific mistakes>
Output: clean textless or low-text illustration, no border, white background, ready to place in a PPTX slide.
```

## Placement Notes

Keep the PPTX layout primary. The image supports the slide; it does not become a second competing slide.

Common placements:

- Explanation slide: text left, illustration right
- Flow slide: title top, wide illustration center
- Dense text slide: compact illustration right or lower right
- Summary slide: usually no illustration unless requested

Preserve n2p slide margins and footer space when inserting.

## Height and Layout Guardrails

Avoid making a single raster image occupy most of the slide height. Before inserting, check:

- the image does not collide with the h1 area
- the image does not crowd the footer
- the slide body text remains primary
- no content is duplicated between image text and PPTX text
- any required editable text remains in PPTX text boxes

When height is tight, split the visual into smaller PPTX elements, reduce image size, or use a simple right-side icon/metaphor instead of a full diagram.

## Flatness Rules

Use flat orthographic illustration only:

- no drop shadows or cast shadows
- no perspective, tilt, skew, or angled screens
- no isometric camera angle
- no 3D depth cues
- no floating objects with ground shadows
- no over-rendered devices, panels, or decorative micro-details

If a generated image includes these effects, reject it or regenerate before inserting.
