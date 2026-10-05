#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d /tmp/ppt-slide-builder-poc.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
PROJECT="$TMP/project"

python3 "$ROOT/engine/cli.py" init \
  --project "$PROJECT" \
  --ppt "$ROOT/examples/test-case/inputs/source.pptx" \
  --manuscript "$ROOT/examples/test-case/inputs/manuscript.docx" \
  --design "$ROOT/examples/test-case/design.md" >/dev/null
python3 "$ROOT/engine/cli.py" analyze --project "$PROJECT" >/dev/null
cp "$ROOT/examples/representative-poc/planning/deck_plan.json" "$PROJECT/planning/deck_plan.json"
cp "$ROOT/examples/representative-poc/planning/visual_plan.json" "$PROJECT/planning/visual_plan.json"
cp "$ROOT/examples/representative-poc/planning/slide_matching.json" "$PROJECT/planning/slide_matching.json"
cp "$ROOT/examples/representative-poc/planning/slide_plans/"*.json "$PROJECT/planning/slide_plans/"
python3 "$ROOT/engine/cli.py" compose --project "$PROJECT" --output representative.pptx >/dev/null
python3 "$ROOT/engine/cli.py" validate --project "$PROJECT" --pptx output/representative.pptx --kind golden >/dev/null
python3 "$ROOT/engine/cli.py" validate-deck --project "$PROJECT" >/dev/null
python3 - "$PROJECT" <<'PY'
import json,sys,pathlib
p=pathlib.Path(sys.argv[1])
qa=json.load(open(p/'qa/representative_qa.json'))
h=json.load(open(p/'qa/deck_harmony.json'))
assert qa['status']=='pass' and qa['blocking_count']==0 and qa['warning_count']==0, qa
assert h['status']=='pass' and h['blocking_count']==0, h
print(f"representative PoC PASS: blocking={qa['blocking_count']} warning={qa['warning_count']} harmony_warning={h['warning_count']}")
PY
