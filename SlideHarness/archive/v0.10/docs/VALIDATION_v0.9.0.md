# Validation v0.9.0

## 1. Aha! Receipt Lite Golden Sample

```text
Slides                       9
Output QA blocking           0
Output QA warning            0
Image Harmony blocking       0
Image Harmony warning        0
Deck Harmony warning         0
```

Outputs:

- `examples/aha-receipt-full-deck/aha-receipt-lite-full-deck-v0.9.0.pptx`
- `examples/aha-receipt-full-deck/aha-receipt-lite-full-deck-v0.9.0-montage.png`

The Golden Sample was rebuilt after the Japanese typography, image classification, and selective source-render changes.

## 2. Independent real-PPT full generation

```text
Templates                    5
Total source slides         90
Generated slides            25
PASS                         5
FAIL                         0
```

| Fixture | Source slides | Generated | Rendered | Blocking | Warning |
|---|---:|---:|---:|---:|---:|
| MIRI template | 17 | 5 | 5 | 0 | 0 |
| 長楽館 editorial deck | 50 | 5 | 5 | 0 | 0 |
| UTokyo leaflet deck | 3 | 5 | 5 | 0 | 0 |
| minimal sample template | 6 | 5 | 5 | 0 | 0 |
| Agent Skills promotion | 14 | 5 | 5 | 0 | 0 |

Generated families per fixture:

```text
cover
timeline
kpi
chart
closing
```

Report:

- `examples/external-template-diversity/summary.json`
- `examples/external-template-diversity/external-diversity-montage.png`

The source templates are runtime inputs and are intentionally excluded from the release ZIP. The five runs were executed in isolated child processes; release status is based on the individual result files and actual-render QA rather than one long chat-container process.

## 3. v0.9 structured-family PoC

```text
Slides                       6
Families                     cover / section / timeline / kpi / chart / closing
Output QA blocking           0
Output QA warning            0
```

Fit scores:

```text
cover       0.931
section     0.907
timeline    1.000
kpi         1.000
chart       1.000
closing     0.904
```

Outputs:

- `examples/layout-family-v090/layout-family-v0.9.0.pptx`
- `examples/layout-family-v090/layout-family-v0.9.0-montage.png`

## 4. Japanese typography tests

```text
title fit within role minimum                         PASS
close-bracket line-start avoidance                    PASS
number + unit / kinsoku diagnostics                   PASS
particle-start noun rebalancing                       PASS
short-last-line title rebalancing                     PASS
fit/display render-safety alignment                   PASS
```

## 5. Asset classification benchmark

```text
Total picture assets       182
Template chrome             48
Content visual              92
Unknown                     42
Unknown rate             0.2308
Geometry repeated           28
Acceptance threshold      <= 0.30
Result                      PASS
```

## 6. Regression checks executed

```text
Codex App Server fake-protocol client                 PASS
Compose editable text / table / chart                 PASS
Layout new-family unit tests                          PASS
Selective source rendering                            PASS
Removed-text Pixel Diff overflow halo                 PASS
Image pipeline tests                                  PASS
Feedback / STALE / source-semantic-render split       PASS
Aha! full-deck actual-render gate                     PASS
External-template actual-render gates                 PASS
```

Render-heavy tests are deliberately sharded in constrained chat containers. An aggregate command timing out is not treated as a product failure when the isolated test and actual-render gates complete successfully.

## Deferred live tests

Not executed in v0.9.0:

- real Codex CLI / App Server + Sol turn
- real OpenAI image-generation request
