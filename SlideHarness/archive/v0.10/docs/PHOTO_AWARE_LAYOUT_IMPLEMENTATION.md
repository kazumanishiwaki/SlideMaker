# Photo-aware Layout Engine v0.6 — 実装仕様

## 目的

画像を生成・選定した後で空き領域へ貼るのではなく、ページの意味と元PPTのデザイン文法から画像スロットを先に計画し、Image Recipeとレイアウトを同じ依存グラフで管理する。

```text
semantic slide intent
  ↓
layout family / fill policy
  ↓
primary visual slot / text side
  ↓
Image Recipe target同期
  ↓
image selection / treatment
  ↓
PowerPoint composition
  ↓
actual-render QA
```

## 対応family

- `photo_text`
- `full_bleed`
- `two_column`
- `comparison_matrix`
- `relationship`

既存の`grid / process / statement`と合わせ、計8familyを実行できる。

## 画像選択前のLayout Plan

`photo_text / full_bleed`は、画像asset未選択でもLayout Planを作成できる。

Layout Engineは次を決める。

- `primary_visual` slot
- bbox
- target aspect
- text side
- requested negative space
- source Picture Shapeを再利用するか
- visualとtemplate chromeのz-order方針

その後、`planning/image_recipes.json`へtargetを同期する。

```yaml
target:
  layout_slot_id: primary_visual
  bbox:
    x: 1.1
    y: 1.4
    w: 5.2
    h: 4.8
  aspect_ratio: 1.0833
  requested_negative_space: right
  source_object_id: SRC-S004-O004
```

## Recipe invalidation

以下のいずれかが変わった場合、以前の画像選択をそのまま採用しない。

- slot bbox
- target aspect
- text side / negative-space intent
- source object
- family

再実行範囲:

```text
image          STALE
render         STALE
qa             STALE
deck_harmony   STALE
```

Deck Plan、Primary Message、Visual Plan、Source Match、他ページはKEEPする。

## Source Picture Shape再利用

元PPTに利用可能なPicture Shapeがある場合、新規Pictureを重ねず、既存shapeをsemantic slotへ移動して画像relationshipを交換する。

保持対象:

- shape id
- mask / crop language
- outline / effect
- rotation
- z-order lineage
- source object lineage

`preserve_format`はrelationship交換だけに使い、Layout Engine側で新しいslot geometryが必要な場合は明示的にshape geometryを更新する。

## `photo_text`

- visualとtextを左右へ分割
- `text_side=auto`はImage Recipeのnegative-space intentで解決
- image / text boxの幅はvisual priorityとdensityから算出
- source typography、picture frame、template chromeを継承
- `PHOTO_TEXT_NEGATIVE_SPACE_DIRECTION`で方向整合を検査

## `full_bleed`

- exact PPT presentation sizeを利用
- visual slotはslide全面
- visualはtemplate chromeより背面
- overlay copy panelは任意
- real selected/processed assetがない場合はcompose / export不可
- `FULL_BLEED_COVERAGE`と`FULL_BLEED_BEHIND_TEMPLATE_CHROME`をBlocking QAとする

## Editable family

### `two_column`

- native text boxes
- native divider
- source typography
- `open / card` component variants
- `card`は原稿量からpanel heightを算出し、意味のない巨大な空カードを作らない
- content clusterは推定行数とsource font scaleから高さを算出する
- card / openとも、明示指定がなければ光学的中央配置
- balanced / intentional_whitespace / content_filled

### `comparison_matrix`

- native PowerPoint table
- editable cells
- highlight column
- header / row label hierarchy

### `relationship`

- native PowerPoint nodes
- native connectors
- center / peripheral node structure
- editable text and geometry

## Image resolution

処理画像の出力解像度はslot寸法から計算する。

- target effective PPI: 約150
- longest edge cap: 3328px
- fixed 2048pxへの一律縮小はしない
- full-bleedでもeffective resolution QAを満たす

## Renderer safety

LibreOffice / Popplerの外部processはbounded executionとする。

- independent LibreOffice user profile
- `start_new_session=True`
- timeout時はprocess group kill
- limited retry
- orphan processを残さない

## QA

追加した主なcheck:

```text
PHOTO_LAYOUT_PRIMARY_VISUAL
PHOTO_LAYOUT_SLOT_GEOMETRY
PHOTO_LAYOUT_SOURCE_FRAME_REUSED
PHOTO_TEXT_NEGATIVE_SPACE_DIRECTION
FULL_BLEED_COVERAGE
FULL_BLEED_BEHIND_TEMPLATE_CHROME
EDITABLE_LAYOUT_COMPARISON_MATRIX
EDITABLE_RELATIONSHIP_NODES
EDITABLE_RELATIONSHIP_CONNECTORS
```

画像ファイルの存在だけでなく、実際のPPT内shape、予定geometry、source lineage、z-order、actual renderを検査する。

## PoC

`examples/photo-layout-poc/`

```text
Slide 1  two_column
Slide 2  photo_text
Slide 3  full_bleed
Slide 4  comparison_matrix
Slide 5  relationship
```

検証結果:

```text
output QA             Blocking 0 / Warning 0
deck QA               Blocking 0 / Warning 0
image coherence       Blocking 0 / Warning 0
```

## Pixel Diff performance

mutation mask外Pixel DiffはNumPyでベクトル化する。NumPyがない場合のみscalar fallbackを使い、ページ画像をPythonの二重ループで走査しない。
