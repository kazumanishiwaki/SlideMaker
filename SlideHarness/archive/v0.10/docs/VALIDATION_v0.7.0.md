# Validation v0.7.0

## Aha! レシート Lite full deck

```text
Slides: 9
Output QA blocking: 0
Output QA warning: 0
Image Harmony blocking: 0
Image Harmony warning: 0
Deck Harmony warning: 0
```

Families:

```text
statement
photo_text
comparison_matrix
relationship
statement
process
grid
two_column
statement
```

## Generic template smoke

```text
Templates: 3
PASS: 3
FAIL: 0
```

Targets:

- MIRI source template
- v0.6 Golden Sample
- v0.5 Image Harmony PoC

## Notes

Full `scripts/run-tests.mjs` is not treated as the final gate in this turn because render-heavy groups can exceed the chat container timeout when run as one aggregate command. Key deterministic modules and the new Aha full-deck pipeline were executed separately.
