# Photo-aware Layout Engine PoC — v0.6.0

元PPTのVisual Grammarを保持しながら、以下の5つのLayout Familyを実レンダリングで検証するPoCです。

- `two_column` — 原稿量に合わせて高さを調整するeditable card / open columns
- `photo_text`
- `full_bleed`
- `comparison_matrix`
- `relationship`

`photo_text`と`full_bleed`は、Layout Engineが画像スロットを先に確定し、そのBBox・縦横比・ネガティブスペース意図をImage Recipeへ渡します。画像はその後に選定・crop・色調補正され、元PPTのPicture Shapeを再利用できる場合はShape IDと書式を保持したまま差し替えます。

実行:

```bash
python3 examples/photo-layout-poc/build.py
```

または:

```bash
npm run demo:photo-layout
```

期待値:

```text
output QA             Blocking 0 / Warning 0
image harmony         Blocking 0 / Warning 0
deck image coherence  Blocking 0 / Warning 0
```

このPoCはlocal/manual画像だけを使い、実CodexまたはOpenAI Images APIへ接続しません。ライブE2Eは最終統合工程まで意図的に保留しています。
