# Image classification

## template_chrome
Repeated brand/decorative elements whose meaning does not depend on slide content. Default action: keep.

## content_visual
Photo, chart, screenshot, infographic, diagram or meaningful icon that contributes to the slide's claim. Default action: replace/rebuild for the current manuscript.

## container_or_frame
Visual container, card, photo mask or background panel that belongs to the template grammar. Default action: preserve shell, change inner content.

## unknown
Low-confidence classification. Do not auto-mutate; surface for review.
## Replacement treatment

For a `content_visual` replacement, preserve explicit source lineage:

```text
source slide / source object / source asset
        ↓
image recipe
        ↓
selected or generated raw image
        ↓
slot crop / focal placement / art-direction grading
        ↓
existing PowerPoint Picture relationship replacement
```

Do not rebuild a source Picture as a new rectangle when its existing mask, frame, crop, outline, effect or z-order can be preserved. Use the source Picture as the visual container and replace its image relationship.

`unknown` or a Recipe without a target source object must remain `REVIEW_REQUIRED`; do not guess a mutation region.



## v0.9 evidence signals

Classification combines, rather than over-trusting, the following evidence:

- repeat by identical asset hash
- repeat by stable geometry even when image bytes differ
- source shape name hints, while ignoring generic names such as `Picture 12`
- z-order and large back-layer behavior
- slide-edge placement and thin decorative raster geometry
- nearest text object and distance
- visual metrics such as transparency, saturation, edge density, and image aspect
- slide-role context, e.g. photo-led, screenshot-led, or chart-led pages

The analyzer may seed `photo`, `screenshot`, `icon`, `background_visual`, or `decorative_visual`, but low-confidence results remain `unknown` / `review_required`. Geometry repetition can identify page chrome even when each page uses different raster bytes.
