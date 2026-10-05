# Slide QA rules

Blocking failures:
- missing text/content
- text overflow
- unintended object overlap
- object outside slide bounds
- image aspect distortion
- changed numeric fact
- lost required condition
- mutation of locked element
- `LAYOUT_FIT_TO_INTENT` failure
  - missing semantic items
  - content cluster too small to create a credible focal point
  - extreme optical imbalance
  - unexplained empty quadrant/edge void on `content_filled` pages

Intentional whitespace is not a failure by itself. For `intentional_whitespace` and `preserve_source`, edge void may be large when the message cluster has sufficient scale and focus.

Review-level failures:
- awkward Japanese line breaks, including kinsoku, particle-start, bracket-orphan, number/unit split, and abnormally short final-line issues
- layout density imbalance that still passes policy thresholds
- low-resolution image
- too many repeated layout families
- low-confidence template/content image classification

## Continuity QA
- `SOURCE_CONTINUITY`: RECOMPOSE must retain traceable macro/component/micro lineage when available.
- `IMAGE_ASSET_READY`: every active Image Recipe must have a selected, readable asset.
- `IMAGE_SOURCE_LINEAGE`: the replacement must identify its source slide/object and source visual treatment reference.
- `IMAGE_TREATMENT_APPLIED`: crop and deck-art-direction grading must be recorded.
- `IMAGE_SLOT_ASPECT`: the processed asset must match the source slot aspect without distortion.
- `IMAGE_EFFECTIVE_RESOLUTION`: low effective PPI is review-level unless it becomes visibly unusable.
- `IMAGE_TEMPLATE_HARMONY`: brightness, saturation, contrast, warmth and visual detail must remain within the source-deck tolerance; severe drift is blocking.
- `IMAGE_NEGATIVE_SPACE`: when copy needs a quiet side, the selected crop should provide it.
- `IMAGE_FRAME_APPLICATION`: the selected asset must be connected to the declared source Picture mutation.
- `IMAGE_RENDERED_IN_TARGET_SLOT`: the actual rendered target region must materially differ from the source image.
- `DECK_IMAGE_COHERENCE`: image tone must not drift arbitrarily across slides. Exact repeated imagery and near-duplicates across slides are warnings. A deliberate same-slide series may share composition and grading without being treated as a duplicate.

The Image Pipeline must not compensate for missing assets by adding unrelated filler, stretching an image, or broadening Pixel Diff masks without a semantic reason.


## Structured layout editability

- `EDITABLE_TIMELINE`: timeline labels, nodes, and connectors remain native PowerPoint objects.
- `EDITABLE_KPI`: KPI values, labels, notes, and panels remain editable.
- `EDITABLE_CHART_DATA`: chart categories and series must be readable from the output PPTX.
- `MESSAGE_LED_WHITESPACE`: cover/section/closing pages may have low occupied area when the focal cluster is sufficiently large and optically balanced.
