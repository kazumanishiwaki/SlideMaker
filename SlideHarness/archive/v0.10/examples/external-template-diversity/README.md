# Independent real-PPT diversity gate

Third-party/user PPT files are not bundled. Pass independent templates at runtime:

```bash
python examples/external-template-diversity/build.py \
  --template brand=/absolute/path/brand.pptx \
  --template editorial=/absolute/path/editorial.pptx
```

Each template executes in an isolated child process and runs:

1. PPT analysis / Design Fingerprint
2. source-slide selection
3. 5-slide RECOMPOSE plan
4. cover / timeline / KPI / native chart / closing
5. selective source-slide rendering
6. editable PPTX composition
7. actual-render QA

Source PPT bytes are excluded from the release archive. `summary.json` stores filename/hash/results; generated outputs are local validation artifacts.
