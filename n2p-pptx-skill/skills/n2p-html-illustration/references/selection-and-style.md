# Selection and Style Guide

## Candidate Selection

Use a conservative first pass. The goal is to clarify the web page, not to make it visually busy.

Score each section from 0-2 for each item:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Concept abstraction | concrete | partly abstract | highly abstract |
| Process/relationship | none | simple relation | multi-step or multi-party |
| Text density | light | moderate | dense |
| Strategic importance | supporting | useful | core argument |
| Visual replaceability | visual would decorate | visual helps | visual changes comprehension |

Initial rule: illustrate sections scoring 6 or higher. If too few sections are selected, lower the threshold to 5 after reviewing page intent. If too many are selected, keep the highest strategic-importance sections first.

## Illustration Type Mapping

| Section intent | Preferred image type | Use when |
|---|---|---|
| Explain a structure | concept diagram | the section names parts, layers, tradeoffs, or causes |
| Show steps | workflow visual | the section describes a sequence, handoff, review, or operation |
| Make a claim memorable | metaphor illustration | the section needs recall without becoming decorative |
| Create atmosphere | abstract visual | a hero or transition needs a restrained visual anchor |
| Show system/team overview | system overview | multiple actors, systems, or workspaces need a high-level view |

Prefer one extremely simple illustration concept per section. The illustration may remain a raster image, but important text must stay editable in HTML. Do not bake labels, step names, rules, or explanatory copy into the generated image unless the user explicitly asks for that.

Keep prompt concepts sparse:

- use 1 core metaphor or 3-4 large simple objects at most
- specify the exact object count when the section could drift into a busy diagram
- prefer icons, cards, folders, documents, nodes, arrows, and simple panels over detailed scenes
- leave generous whitespace and avoid background patterns
- remove people unless the section specifically needs human roles

## Aspect Ratio Decision

Choose based on intended responsive placement:

- Right column beside text: 4:3 or 1:1
- Full-width process block: 16:9
- Concept mark or metaphor: 1:1
- Hero/section header visual: 16:9 or wide horizontal

If uncertain, generate 16:9 and use CSS `object-fit: contain` to preserve the image without cropping important content.

## Base Prompt Block

Include this block in every prompt:

```text
Create an extremely simple n2p web illustration on a pure white background. Use only clean black or dark gray linework, two light gray fills at most, and one tiny n2p yellow (#E8E800) accent. Keep the style calm, minimal, business-oriented, flat, front-facing, and suitable for a Japanese business website. Use large whitespace and consistent line weight. Avoid all shadows, perspective tilt, isometric camera angles, strong gradients, glossy surfaces, decorative particles, background patterns, excessive depth of field, and generic AI-looking decoration.
```

## Text and Editability Rules

Default: put text in HTML, not inside generated images. The page's native text has priority over image text, while the image carries the visual metaphor or scene.

Use generated image text only when:

- the label is extremely short
- the text is not duplicated by HTML text
- the user explicitly wants the label baked into the image
- the image will not need later editing

Prefer editable HTML text for:

- Japanese labels
- step names
- rules
- before/after text
- callouts
- captions
- anything likely to be revised by a director

Avoid long explanations, small UI text, dense tables, and tiny labels inside generated images. If a generated image contains too much text, do not use it as-is; regenerate a textless version or move text into HTML.

Keep illustration detail low. Prefer the clarity of a simple web diagram over a highly polished, dense, or over-produced illustration. If the image starts to look like a finished infographic on its own, simplify it by reducing object count, removing background elements, and keeping one core metaphor.

## Negative Prompt Block

Add or adapt this block:

```text
Do not use photorealistic people, stock-photo style, manga style, hand-drawn sketch style, neon colors, vivid gradients, glassmorphism, glowing blobs, any shadows, perspective tilt, angled screens, isometric camera angles, busy backgrounds, clutter, tiny unreadable text, fake detailed UI screenshots, or decorative elements that do not explain the section.
```

## Prompt Template

```text
Section: <page/section id and heading>
Purpose: <what the viewer should understand faster because of this image>
Image type: <concept diagram | workflow visual | metaphor illustration | abstract visual | system overview>
Composition: <where objects sit; exact object/group count; expected aspect ratio; whitespace guidance>
Labels: <prefer "no labels"; if needed, list only labels that cannot be placed in HTML>
Style: <base prompt block>
Content details: <section-specific objects and relationships>
Avoid: <negative prompt block plus section-specific mistakes>
Output: clean textless or low-text illustration, no border, white background, ready to place in an HTML page.
```

## Simple Prompt Pattern

Use this shorter pattern when the section needs a clean visual anchor rather than a rich scene:

```text
Create an extremely simple n2p web illustration on a pure white background.
Use only clean black linework, two light gray fills, and one tiny n2p yellow (#E8E800) accent.
Flat, front-facing, minimal Japanese business website tone.

Composition: <three or four large simple symbols in a wide horizontal flow / compact cluster / triangle loop>.
Use no text, no people, no extra objects, no background pattern, no shadows, no gradients.
Keep the drawing sparse with generous whitespace and consistent line weight.

Output: clean textless illustration, no border, white background, ready to place in an HTML page.
```

## HTML Layout Notes

Keep the web layout primary. The image supports the section; it should not become a competing page inside the page.

Common placements:

- Explanation section: text column + illustration column
- Flow section: heading/copy above, wide illustration below
- Dense text section: compact visual anchor beside text
- Hero: only when it communicates the real offer/concept, not as decoration

Preserve responsive behavior:

- define `width` and `height` attributes on `img`
- use CSS dimensions or aspect ratio to avoid layout shift
- keep labels/captions in HTML text
- use `loading="lazy"` except for above-the-fold hero images
- write useful `alt` text unless the image is purely decorative

## Flatness Rules

Use flat orthographic illustration only:

- no drop shadows or cast shadows
- no perspective, tilt, skew, or angled screens
- no isometric camera angle
- no 3D depth cues
- no floating objects with ground shadows
- no over-rendered devices, panels, or decorative micro-details

If a generated image includes these effects, reject it, regenerate, or mechanically clean it before insertion.

## Yellow Rules

Use n2p yellow `#E8E800` for small accents. If generated yellow drifts orange, mechanically recolor yellow pixels to `#E8E800` before adopting the asset.
