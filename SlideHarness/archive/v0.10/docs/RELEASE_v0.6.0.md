# Release v0.6.0 — Photo-aware / Structured Layout Engine

## 概要

v0.5のImage Selection / Treatment / Harmonyを、Layout Engineへ接続した。画像を先に生成して空き領域へ置くのではなく、semantic layoutがprimary visual slotを先に決め、そのgeometryとnegative-space intentをImage Recipeへ同期する。

実Codex App Server + Solおよび実OpenAI画像生成のライブE2Eは、ユーザー方針により最終統合工程へ保留した。

## 新規Layout Family

- `two_column`
- `photo_text`
- `full_bleed`
- `comparison_matrix`
- `relationship`

既存:

- `grid`
- `process`
- `statement`

合計8 familyが実行可能。

## 主な変更

### Photo-aware planning

```text
Slide Plan
→ primary visual slot
→ Image Recipe target同期
→ candidate selection
→ crop / grading
→ PowerPoint配置
→ actual-render QA
```

### Source Picture reuse

- 元Picture Shapeを削除せずrelationshipを交換
- shape ID / z-order / geometry / rotation / crop-mask / outline / effectを保持
- Layout Engineが必要に応じてsemantic slotへ移動

### Editable structured visuals

- comparison matrix: native PowerPoint table
- relationship: native nodes / connectors
- two-column: native text / divider

### Fit-to-intent

- `two_column`の短い本文はcompact content cluster
- `card` variantは情報量からpanel heightを決め、巨大な空カードで占有率だけを上げない
- `open / card`とも、明示指定がなければcontent clusterを光学的中央配置
- source componentのfont scaleを継承し、26.67-inch templateでも本文が過小にならない
- comparison matrix / relationshipもsource typographyを基準に可読サイズへ正規化
- full-height body boxへの不自然な引き延ばしを回避

### QA / performance

- photo slot geometry
- negative-space direction
- source frame reuse
- full-bleed coverage / chrome z-order
- native table / node / connector editability
- Image Harmony / Deck Image Coherence
- Pixel DiffをNumPyベクトル化
- bounded LibreOffice / Poppler subprocess

## Golden Sample

`examples/photo-layout-poc/`

```text
slides                         5
actual-render blocking         0
actual-render warning          0
image harmony blocking         0
image harmony warning          0
deck image coherence blocking  0
deck image coherence warning   0
```

対象family:

- two_column
- photo_text
- full_bleed
- comparison_matrix
- relationship

## Compatibility

- Python 3.10+
- Node.js 20+
- LibreOffice
- Poppler
- `numpy>=2.0.0`を追加

## 既知の未検証

- 実Codex App Server + Sol turn
- 実OpenAI API画像生成

いずれもアダプターは存在するが、ライブ成功済みとは扱わない。
