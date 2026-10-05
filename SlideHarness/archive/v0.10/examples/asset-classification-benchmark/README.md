# Asset classification benchmark

Runs the deterministic image-role seed against the MIRI test template and records:

- `template_chrome / content_visual / container_or_frame / unknown`
- content-role hints such as photo, screenshot, icon, and decorative visual
- geometry-based repeated decoration detection
- low-confidence review count

The benchmark does not auto-approve ambiguous images. `unknown` remains user-reviewable.
