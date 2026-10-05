# SlideHarness

The source of truth is the greenfield implementation under `nextgen/`.

It provides a loopback-only Codex App Server for arbitrary PowerPoint
templates, separately registered manuscripts and design/image-generation
instructions, editable native PowerPoint structures, host-generated visual
assets produced through the same signed-in Codex connection, deterministic QA,
and isolated one-page regeneration.

## Start

```bash
npm start
```

Open `http://127.0.0.1:4318`. No provider API key is accepted or required.

## Current controls

- information density: `low` / `medium` / `high`
- decorativeness: `low` / `medium` / `high`
- graph and flow rendering: editable PowerPoint native (default) / rich generated image / `auto`
- drop shadows: disabled unless explicitly enabled
- page regeneration: one selected slide only, with non-target OOXML fingerprints
- final verification: package/theme integrity, per-slide source notes, an actual
  LibreOffice render, and rendered visual QA are required

## Verify

```bash
npm run check:next-app
npm test
```

Implementation and contracts are documented in [nextgen/README.md](nextgen/README.md)
and [nextgen/SPEC.md](nextgen/SPEC.md).

Japanese product and system documents:

- [Function list](docs/FUNCTIONS.md)
- [Requirements definition](docs/REQUIREMENTS.md)
- [System specification](docs/SPECIFICATION.md)

The retired v0.10 implementation is preserved read-only under
[`archive/v0.10/`](archive/v0.10/README.md). It is not referenced by the active
server, tests, or npm scripts.
