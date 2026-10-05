# design.md

## 基本方針
- 元PPTから抽出したフォント、色、装飾、グリッドを優先する。
- 元PPTに用途の近いページがある場合は再利用を優先する。
- 内容に適合しない場合は、元PPTのVisual Grammarを保持したままADAPT / RECOMPOSEする。
- 1スライド1メインメッセージを基本とする。
- 情報密度は medium_low、余白は generous を基準とする。

## Hard Constraints
### text
- overflow: forbidden
- unnatural_japanese_wrap: forbidden
- title_max_lines: 2
- title_min_font_pt: 22
- body_min_font_pt: 12
- shrink_font_as_last_resort: true

### layout
- overlap: forbidden
- out_of_bounds: forbidden
- preserve_grid_alignment: true
- minimum_safe_margin_pt: 10

### image
- preserve_aspect_ratio: true
- distortion: forbidden
- content_visual_must_match_message: true

### brand
- template_chrome_removal: forbidden
- locked_object_mutation: forbidden

### content
- fabricate_numbers: forbidden
- fabricate_facts: forbidden
- drop_required_conditions: forbidden
- editorial_notes_as_customer_copy: forbidden

## Soft Constraints
- whitespace: generous
- density: medium_low
- visual_variety: moderate
- template_reuse: preferred
- repeated_layout_limit: 2
- photos_only_when_semantically_useful: true

## PPT Image Classification
### template_chrome
- Keep by default.
- Logos, repeated lines, page ornaments, recurring brand motifs, background chrome.

### content_visual
- Replace according to the new manuscript.
- Photos, charts, screenshots, diagrams, infographics, explanatory icons.

### container_or_frame
- Preserve outer styling and replace only inner content where possible.

### unknown
- Do not mutate automatically when confidence is low; mark REVIEW_REQUIRED.

## QA Priorities
1. Meaning and factual conditions preserved
2. No overflow / overlap / out-of-bounds
3. Japanese line breaks look natural
4. Image aspect ratios preserved
5. Template chrome preserved
6. Deck-level rhythm and visual variety

## Layout Intent
- default_fill_policy: balanced
- allow_intentional_whitespace: true
- preserve_source_whitespace: true
- forbid_filler_content: true
- avoid_small_content_island: true
- avoid_unintentional_empty_quadrant: true
- balanced_grid_preferred: true
- fit_to_intent_quality_is_blocking: true

### fill_policy_by_role
- cover: intentional_whitespace
- section: intentional_whitespace
- statement: intentional_whitespace
- quote: intentional_whitespace
- single_kpi: intentional_whitespace
- closing: intentional_whitespace
- comparison: content_filled
- process: content_filled
- timeline: content_filled
- table: content_filled
- chart: content_filled
- three_items: content_filled
- four_items: content_filled
