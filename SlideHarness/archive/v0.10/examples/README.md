# Examples and Golden Samples

Large user/third-party source PPT files are intentionally excluded from the release tree.

Included deterministic builders and outputs:

- `aha-receipt-full-deck/`: 9-slide Golden Sample
- `layout-family-v090/`: cover / section / timeline / KPI / native chart / closing
- `external-template-diversity/`: runtime-supplied independent real-PPT full-generation gate
- `asset-classification-benchmark/`: image-role classification benchmark
- `layout-intent-poc/`, `image-harmony-poc/`, `photo-layout-poc/`: focused engine tests

The external diversity summary stores source filenames and SHA-256 hashes, but the source PPT bytes are never bundled. Generated validation PPTX files are local artifacts and are excluded from the source release ZIP.
