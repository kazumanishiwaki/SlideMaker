# Release v0.10.0 — Simplification

## Summary

v0.10 reduces overlapping planning phases and repair loops. It also rebuilds the Aha! Receipt Lite sample after human feedback about title wrapping, type size, image use, and semantic layout meaning.

## Changes

- Pipeline reduced to five stages
- Deck Plan + one compact Slide Plan bundle are the AI-authored planning surface
- Visual / matching views are derived, not separately authored
- Layout implementations grouped into five renderer families
- Model-call contract: two normal calls, maximum one repair proposal per slide
- Japanese explicit semantic chunks override line-length balancing
- Design issues no longer automatically cause unbounded repair loops
- PDF word matching prefilters words to the relevant shape region
- CTA card text color no longer inherits an invisible source white style
- Short process copy uses content-fitted card height

## Golden Sample corrections

- `必要な機能を標準化するから、 / 導入しやすい` is fixed as an explicit two-line title
- normal titles are generally 42–52pt
- card titles are at least 22pt and body copy at least 17pt in the calibrated sample
- source screenshots/conceptual product imagery are used on slides 1, 2, and 7
- slide 4 uses cause-effect flow rather than a generic relationship diagram
- slide 6 uses a directional process
- slide 8 expresses staged expansion/containment rather than two equal choices
- slide 9 CTA cards render visible dark text

## Deferred live integration

No real Codex CLI / App Server + Sol turn or real OpenAI image request was executed in this release.
