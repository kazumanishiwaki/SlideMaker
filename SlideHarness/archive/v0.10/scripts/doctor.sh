#!/usr/bin/env bash
set -u
fail=0
check_cmd(){ if command -v "$1" >/dev/null 2>&1; then printf '✓ %-14s %s\n' "$1" "$(command -v "$1")"; else printf '✗ %-14s missing\n' "$1"; fail=1; fi; }
check_optional(){ if command -v "$1" >/dev/null 2>&1; then printf '✓ %-14s %s\n' "$1" "$(command -v "$1")"; else printf '! %-14s missing (live Codex App Server disabled)\n' "$1"; fi; }
check_pdf_renderer(){
  if command -v pdftocairo >/dev/null 2>&1; then
    printf '✓ %-14s %s (preferred)\n' pdftocairo "$(command -v pdftocairo)"
  elif command -v pdftoppm >/dev/null 2>&1; then
    printf '✓ %-14s %s (fallback)\n' pdftoppm "$(command -v pdftoppm)"
  else
    printf '✗ %-14s missing (pdftocairo or pdftoppm required)\n' poppler-render
    fail=1
  fi
}
echo 'PPT Slide Builder — environment check'
check_cmd node
check_cmd npm
check_cmd python3
check_cmd libreoffice
check_pdf_renderer
check_cmd pdftotext
check_optional codex
if [ -n "${OPENAI_API_KEY:-}" ]; then
  printf '✓ %-14s configured (live image generation enabled)
' OPENAI_API_KEY
else
  printf '! %-14s not configured (manual/local images only)
' OPENAI_API_KEY
fi
python3 - <<'PY' || fail=1
from importlib.metadata import version, PackageNotFoundError
mods=[('pptx','python-pptx'),('docx','python-docx'),('PIL','Pillow'),('jsonschema','jsonschema'),('numpy','numpy')]
for mod_name,pkg_name in mods:
    try:
        __import__(mod_name)
        try: v=version(pkg_name)
        except PackageNotFoundError: v=''
        print(f'✓ python:{mod_name:<10} {v}')
    except Exception as e:
        print(f'✗ python:{mod_name:<10} {e}'); raise
PY
if [ "$fail" -ne 0 ]; then
  echo
  echo 'Required deterministic analysis/render dependencies are missing.'
  echo 'Install Python dependencies with: python3 -m pip install -r requirements.txt'
  exit "$fail"
fi
if ! command -v codex >/dev/null 2>&1; then
  echo
  echo 'Deterministic demo is available. Install/sign in to Codex CLI to enable live Sol turns.'
fi
