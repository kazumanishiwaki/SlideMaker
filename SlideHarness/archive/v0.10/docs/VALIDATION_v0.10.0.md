# Validation v0.10.0

## Aha! Receipt Lite Golden Sample

```text
Slides                         9
Output QA blocking             0
Output QA warning              0
Technical failures             0
Content failures               0
Design failures                0
Image Harmony blocking         0
Image Harmony warning          0
Deck Harmony warning           0
```

Layout sequence:

```text
full_bleed
photo_text
comparison_matrix
process
statement
process
photo_text
process
closing
```

Renderer groups:

```text
media / media / grid / flow / statement / flow / media / flow / statement
```

## Human-feedback checks

- exact title break: PASS
- ordinary page title size raised: PASS
- CTA card text visibility: PASS
- cause-effect meaning on slide 4: PASS
- sequence meaning on slide 6: PASS
- containment/expansion meaning on slide 8: PASS
- no filler imagery added only for occupancy: PASS

## Automated regression executed

```text
Planning / compact schema                         4 PASS
Feedback / minimum STALE                         4 PASS
State migration / compact phases                 2 PASS
Japanese typography                              6 PASS
Layout Engine                                   16 PASS
Deck validation                                  2 PASS
Compose                                          4 PASS
Image pipeline                                   9 PASS
Codex App Server fake protocol                   1 PASS
```

The Aha actual-render validation completed in approximately 12 seconds after composition in the current container. Render-heavy aggregate test commands remain sharded because the chat container can terminate long parent processes even when isolated gates pass.

## Not executed

- real Codex App Server + Sol
- real OpenAI image generation
- full aggregate render suite as one command
