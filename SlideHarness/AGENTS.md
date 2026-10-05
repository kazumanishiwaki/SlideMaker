# SlideHarness current implementation instructions

## Source of truth

- App Server: `nextgen/app-server.mjs`
- browser UI: `nextgen/public/`
- deterministic PowerPoint core: `nextgen/slideharness_next/`
- Codex planning workflow: `nextgen/skill/`
- tests: `nextgen/tests/`
- run state: `nextgen/workspace/<run-id>/`

`archive/v0.10/` is read-only history. Do not import it from active code, add
active npm scripts for it, or patch it for new features.

## Invariants

1. Never mutate uploaded inputs or prepared evidence.
2. User settings override automatic choices.
3. Keep design/image-generation guidance separate from factual source content.
4. Drop shadows are disabled unless explicitly requested.
5. PowerPoint tables keep explicit cell margins and semantic alignment.
6. `native` graph/flow mode uses editable PowerPoint charts and shapes.
7. `generated-image` graph/flow mode uses `generated_visual` and a target-owned
   host image request; retain the factual conclusion in editable slide text.
8. Page regeneration may change only the selected slide. Reject stale
   revisions, shared-dependency mutations, and any non-target fingerprint change.
   Remove dependencies that were private to the replaced slide and are no longer
   reachable; keep content-type registrations synchronized.
9. Preserve the previous valid plan and PPTX on every failed build or revision.
10. Final slides must not retain empty template placeholders or silently shrink
    generated text. Missing or wrapped rendered text is a blocking defect.
11. Every source-backed slide carries a `[Sources]` speaker-note block, and a
    resolved image path is used only once unless reuse is explicitly requested.
12. Preserve exact source URLs in speaker notes. Externally sourced images must
    declare `source_url` (or `source_urls`) and a stable `asset_id` in the plan.
13. Render process connectors before nodes, and reject unreachable slide-owned
    package payloads such as orphan media, charts, or slide parts.

## Verification

Run `npm test`, `npm run check:next-app`, and the Skill validator after changing
the planning contract. A deck is complete only when content, structural,
package, render, visual, provenance, template-fidelity, and applicable
page-isolation QA pass. Package QA must compare the final deck with the original
template, including after isolated regeneration.
Render `SKIP` is a final-build failure; `--allow-render-skip` is an explicit
draft-only escape hatch.
