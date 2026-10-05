# Image Pipeline v0.5.0 — 実装仕様

## 目的

元PPTの本文画像を単純に差し替えるのではなく、各画像を元スライドの意味・写真枠・デック全体のアートディレクションへ適応させる。

処理対象は `content_visual` と判定された写真・イラスト・スクリーンショット等である。`template_chrome` は保持し、`container_or_frame` は外形を保持して内側だけを変更する。

## 処理フロー

```text
source content visual
      ↓
image recipe
      ↓
uploaded asset / local selection / OpenAI generation
      ↓
focal-point and slot-aware crop
      ↓
deck-wide brightness / saturation / contrast grading
      ↓
source picture shape relationship replacement
      ↓
actual slide render
      ↓
IMAGE_TEMPLATE_HARMONY
      ↓
DECK_IMAGE_COHERENCE
```

## 入力候補の優先順位

`provider=auto` は次の順で利用可能な画像を探す。

1. ユーザーが当該Recipeへ明示指定した画像
2. `inputs/assets/` 内の支給画像
3. `OPENAI_API_KEY` が存在する場合の画像生成
4. いずれも存在しない場合は `REVIEW_REQUIRED`

テスト用の決定論的Mockは、`provider=mock` または `--allow-mock` が明示された場合だけ利用する。通常の自動処理でMock画像を完成素材として採用せず、Mockが選択されたRecipeはFinal Export Gateで必ず拒否する。

## Local asset ranking

支給画像は以下をスコアリングする。

- target slotとの縦横比適合
- 実効解像度
- source-deck target metricsとの近さ
- ファイル名とページメッセージの簡易意味適合
- 文字を置く側のnegative space
- 同一画像の再利用ペナルティ

候補とスコアはManifestへ残し、ユーザーは別候補を選び直せる。

## Image Recipe

各Recipeは最低限以下を持つ。

```yaml
recipe_id: IMG-OUT-S004-01
slide_id: OUT-S004
purpose: communicate_mobile_optimization
medium: editorial_photo

target:
  source_slide_id: SRC-S008
  source_object_id: SRC-S008-O010
  source_asset_id: AST-00082
  bbox: {x: 18.125, y: 3.139, w: 4.333, h: 2.389}
  aspect_ratio: 1.814
  frame_asset_ids: []

composition:
  focal_point: auto
  negative_space: left
  background_complexity: low_to_medium

treatment:
  preset: match_source_slot_and_deck_art_direction
```

Recipeは単なる画像プロンプトではなく、どの元オブジェクトへ、どの構図・比率・処理で配置するかという契約である。

## OpenAI provider

画像生成は `POST /v1/images/generations` を利用するProviderを実装する。

環境変数:

```text
OPENAI_API_KEY
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_ENDPOINT=https://api.openai.com/v1/images/generations
```

APIキーがない場合はライブ生成を行わず、エラー内容をUIへ返す。

## Crop / focal placement

- target slotの縦横比へcover cropする
- Recipeのfocal pointを可能な限り保持する
- focal pointが未指定ならエッジ分布から決定論的に推定する
- `negative_space` が指定された場合、複数のcrop候補を比較し、文字を置く側のedge densityが低いものを選ぶ
- crop結果と選定理由をAsset Manifestへ記録する

## Deck-wide grading

元PPTのContent Visual群から抽出したtarget metricsへ、過剰にならない範囲で補正する。

- brightness
- saturation
- contrast
- warmth
- edge/detail density

各補正係数と補正前後のmetricsをManifestへ保存する。

## Source frame application

既存の写真枠は作り直さない。

`fit_mode=preserve_format` では、PowerPoint内部の既存 `p:pic` の画像Relationshipだけを交換する。以下を保持する。

- shape id
- z-order
- geometry
- rotation
- crop / mask
- outline / effects
- surrounding template chrome

これにより、元PPTのデザイナーが同じ枠へ別素材を入れたような連続性を作る。

## QA

### Slide-level

- `IMAGE_ASSET_READY`
- `IMAGE_SOURCE_LINEAGE`
- `IMAGE_TREATMENT_APPLIED`
- `IMAGE_SLOT_ASPECT`
- `IMAGE_EFFECTIVE_RESOLUTION`
- `IMAGE_TEMPLATE_HARMONY`
- `IMAGE_NEGATIVE_SPACE`
- `IMAGE_FRAME_APPLICATION`
- `IMAGE_RENDERED_IN_TARGET_SLOT`

Blockingが残る画像Recipeを持つページはFinal Exportできない。

Final Exportではさらに、Recipeの`selected_asset_id`とManifestの`selected_by_recipe`が一致し、Manifest上に処理済み画像・lineage・treatment情報が存在し、providerがtest-only `mock`ではないことを検査する。

### Deck-level

- brightness / saturation / contrast / edge density / warmthのrange
- 別ページ間のnear-duplicate visual
- 同一ページ内の画像シリーズは、完全重複でない限り共有スタイルとして扱う
- 自動的に全画像を再生成せず、警告と対象Recipeを提示する

## UI

ページ右パネルで以下を行える。

- Recipeとtarget slotの確認
- 複数支給画像の一括アップロード
- 解析後の未解決Recipeへ登録画像を自動選定
- Recipe prompt / focal point / negative-spaceの更新
- 別案のAI生成
- candidate rankingと候補画像の選択
- source / processed画像の比較
- Harmony QAの確認

ユーザーには内部metricsを常時見せず、通常は次のように要約する。

```text
画像：準備済み
元PPTの写真枠：保持
色調：元PPTに合わせて調整
画像調和：適正
```

## STALE範囲

画像選択・生成・差し替えを変更した場合:

```text
image   MODIFIED / APPROVED
render  STALE
qa      STALE
deck_harmony STALE
```

Deck Plan、Primary Message、Visual Plan、Source Match、他ページは変更しない。

## 実装済みProviderと検証範囲

- `manual`: 実装・自動テスト済み
- `local`: 実装・自動テスト済み
- `auto`: 実装・自動テスト済み
- `mock`: テスト専用として実装
- `openai`: APIクライアント実装済み。APIキーを持たない当コンテナではライブ呼び出し未実行

## PoC

`examples/image-harmony-poc/` は、元PPT 8ページの4つの写真Shapeを保持し、4つの新しいローカル候補をcrop・grading後に差し替える。

確認項目:

- Picture Shape ID維持
- 元の写真枠・罫線・ロゴ保持
- 4枚共通のArt Direction
- Image Harmony blocking 0
- Deck Image Coherence warning 0
- actual-render QA blocking 0 / warning 0
