---
name: n2p-html-illustration
description: Create and manage consistent n2p-style generated illustrations for HTML websites, landing pages, web proposals, and static pages after the page content or component structure exists. Use when working on n2p-branded HTML/CSS/JS projects and the user asks to add, generate, retake, replace, optimize, or manage content-aware web illustrations with gpt-image2, including concept diagrams, workflow visuals, metaphor illustrations, abstract visuals, and section-supporting images. This skill selects only page sections where an illustration improves understanding, generates images in a fixed n2p tone, stores prompts and intent outside the skill directory, inserts adopted assets into HTML with editable text kept in HTML/CSS, and preserves retake history.
---

# n2p HTML Illustration

## Purpose

Add generated illustrations to n2p HTML pages without changing the brand tone or turning the page into a decorative landing page. Be conservative: generate illustrations only where they clarify content or provide a useful visual anchor.

This skill is the HTML counterpart of `n2p-slide-illustration`. Use it for websites, landing pages, HTML prototypes, static pages, and componentized frontend projects. Keep generated-image text minimal; headings, labels, captions, and explanations should remain editable HTML text.

## Workflow

1. Inspect the existing HTML, component files, or page copy after the content structure exists.
2. Select candidate sections using `references/selection-and-style.md`.
3. For each selected section, decide the image type, aspect ratio, responsive placement, alt text, and why the illustration improves understanding.
4. Create or update the image asset folder with `scripts/create_image_slot.py`.
5. Write `intent.md` and `prompt-vN.md` before generating.
6. Generate with direct `gpt-image2` access when available. Keep the illustration visual-only or low-text, and avoid baking important text into the image.
7. Save generated files as `image-vN.png` or `image-vN.webp` in the section folder. Keep previous versions.
8. Insert the adopted image into the HTML using `img` or `picture`. Add labels, captions, and nearby copy as HTML text, not image text.
9. When the user requests a retake, append to `retake-log.md`, create the next prompt/version when a raster image changes, and update the HTML to reference the adopted version.

## Asset Layout

Use one folder per illustrated page section under the project workspace. Do not write project-specific assets, logs, prompts, generated images, or test outputs inside this skill directory; keep the skill redistributable and clean.

```text
generated-assets/<project-name>/<page-or-route>/<section-id>/
  intent.md
  prompt-v1.md
  image-v1.png
  prompt-v2.md
  image-v2.png
  retake-log.md
```

Examples:

```text
generated-assets/company-site/home/hero/
generated-assets/company-site/home/process/
generated-assets/proposal-demo/lp/problem-statement/
```

Use stable section IDs that match or resemble HTML anchors/classes, such as `hero`, `problem`, `workflow`, `solution`, or `comparison`.

## Selection Rules

Default to restrained density. For a single landing page, start with 2-4 illustrated sections unless the page clearly needs more.

Prioritize sections with:

- abstract concepts that need a mental model
- before/after contrast
- process, workflow, or stakeholder flow
- relationship between teams, systems, users, or decisions
- dense text where a visual anchor would reduce cognitive load
- a key argument that should be memorable

Do not add generated illustrations to every section. Avoid illustrations in simple navigation, footer, legal, plain CTA, or already-clear content blocks unless the user asks or the visual materially improves comprehension.

## Style Rules

Default illustration tone:

- white or transparent-feeling white background that blends into the page
- black or dark gray linework and simple fills
- n2p yellow `#E8E800` only as a small accent
- calm Japanese business proposal tone
- generated image text should usually be absent; labels and explanation should be HTML text
- no shadows, perspective/tilted views, glossy effects, loud gradients, ornate decoration, or generic AI-looking visuals
- keep illustration detail low, close to an extremely simple business diagram
- use one core metaphor or 3-4 large simple objects; avoid detailed scenes and background patterns

For the full type mapping, prompt blocks, and negative constraints, read `references/selection-and-style.md`.

## HTML Insertion Guidance

Use semantic, accessible markup:

```html
<figure class="section-illustration">
  <img
    src="/assets/generated/home-process-v2.png"
    alt="共通ルールをAI依頼へ渡す流れを示す図"
    width="1200"
    height="675"
    loading="lazy"
    decoding="async"
  />
  <figcaption>必要なら短い補足をHTMLテキストで置く</figcaption>
</figure>
```

For responsive assets, prefer `picture` or `srcset` when multiple sizes exist. Keep dimensions stable with CSS to avoid layout shift.

```css
.section-illustration {
  margin: 0;
}

.section-illustration img {
  display: block;
  width: 100%;
  height: auto;
}
```

Keep text editable in HTML:

- headings
- labels
- captions
- step names
- rule names
- button/callout text

Do not place these inside generated images unless explicitly requested.

## Layout Guidance

Place illustrations based on section content:

- explanation section: text column + right-side illustration
- process section: wide illustration below heading or between copy blocks
- dense section: compact visual anchor next to text
- hero: use only if it reveals the actual subject or a useful concept, not as decorative filler

Do not force a single tall raster image into a short viewport. Keep responsive height conservative and preserve scanability on mobile.

Use flat, front-facing, orthographic compositions. Do not use drop shadows, cast shadows, perspective tilt, angled screens, isometric camera angles, or depth cues that make the image look three-dimensional.

## Retake Rules

Humans decide whether a retake is needed. Do not auto-retake based only on model self-critique.

When retaking:

- keep all previous images and prompts
- create the next version number
- write the human instruction exactly in `retake-log.md`
- state what changed in the new prompt
- update HTML/CSS to reference only the adopted version

Use `references/retake-workflow.md` for the log format and common retake patterns.

## Generation Routes

Use this priority order:

1. Direct Codex-accessible image generation with `gpt-image2` if available.
2. A local or product integration through Codex App Server when the project provides one.
3. Browser-operated ChatGPT image generation only as a fallback when the user approves or explicitly requests it.

Before implementing a new direct API or App Server integration, verify current OpenAI/Codex documentation because model names and App Server surfaces can change.
