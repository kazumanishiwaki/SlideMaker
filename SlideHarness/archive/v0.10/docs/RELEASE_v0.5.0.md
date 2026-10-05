# Release v0.5.0 — Image Selection, Treatment and Harmony

## 概要

v0.4で定義したDesign Fingerprint / Component Catalog / Continuity Plan / Deck Art Direction / Image Recipeを、実際の画像候補選定・画像生成アダプター・crop・色調補正・PowerPoint差し替え・Render QAへ接続した。

画像は「生成できた」「アップロードされた」だけでは完成扱いにしない。元PPTのsource slotへ適応し、Picture shapeへ配置し、実レンダリング上の調和を検査して初めてCURRENTになる。

## 主な追加

### Source image extraction

- 元PPT画像blobを `analysis/source_media/` へ重複排除して抽出
- crop / rotation / slot aspect / source object lineage記録
- brightness / saturation / contrast / warmth / edge density / dominant colors / average hash抽出

### Image provider

- `manual`
- `local`
- `auto`
- OpenAI image adapter
- explicit test-only `mock`

`auto`はAcceptableなlocal候補を優先し、閾値未満ではOpenAI生成またはReview Requiredへ進む。Mockを実制作へ暗黙採用しない。

### Local candidate ranking

- target slot aspect
- effective resolution
- source/deck harmony
- filename semantics
- requested negative space
- reuse penalty

候補とスコアをmanifestへ保存し、別候補を後から採用できる。

### Image treatment

- focal point推定
- negative-space crop search
- target slot cover crop
- brightness / saturation / contrast
- warmth correction
- detail density soften / sharpen
- raw / processed version保存
- treatment前後metrics・補正係数記録

### Editable PowerPoint integration

- 既存 `p:pic` の画像relationshipをin-place交換
- shape ID / z-order / geometry / rotation / mask / outline / effects保持
- Image RecipeをSlide Planの局所 `replace_image` mutationへ変換
- rotated pictureのPixel Diff mutation mask対応

### State / partial rerun

- image phaseをdependency stateへ追加
- unresolved RecipeはFinal Export不可
- prompt / focal point / negative-space更新時:
  - selected assetを解除
  - replace-image mutationを解除
  - image / render / QA / Deck Harmonyだけを再実行対象化
- Deck Plan / Visual Plan / Source Match / 他ページはKEEP

### QA

- IMAGE_ASSET_READY
- IMAGE_SOURCE_LINEAGE
- IMAGE_TREATMENT_APPLIED
- IMAGE_SLOT_ASPECT
- IMAGE_EFFECTIVE_RESOLUTION
- IMAGE_TEMPLATE_HARMONY
- IMAGE_FRAME_APPLICATION
- IMAGE_RENDERED_IN_TARGET_SLOT
- DECK_IMAGE_SHARED_SERIES_STYLE
- DECK_IMAGE_COHERENCE

### UI

- 複数画像の一括登録
- 解析後、未解決Recipeへ登録画像を自動選定
- 元PPT参照画像と処理後画像の比較
- source lineage表示
- crop / grading要約
- candidate ranking / version選択
- Recipe prompt / text-side negative space / focal point編集
- Recipe更新時の選択解除と最小STALE
- OpenAI別案生成
- 画像QAとDeck Image Coherence表示

## Image Harmony PoC

`examples/image-harmony-poc/`

元PPT 8ページの4つの写真Shapeを保持し、4つの登録候補を `provider=auto` で自動選定する。

```text
selection provider          auto -> local
prepared assets             4
IMAGE_TEMPLATE_HARMONY      blocking 0 / warning 0
DECK_IMAGE_COHERENCE        warning 0
actual-render QA            blocking 0 / warning 0
```

PoCには `source-page-8.png`、`image-harmony-poc.png`、元画像、候補、処理後画像、Recipe、Art Direction、`image-asset-manifest.json`、QA、編集可能PPTXを同梱する。

## Final Export Gate強化

画像を持つページは以下をすべて満たす必要がある。

- Recipeに実在するsource content slotがある
- Recipeの`selected_asset_id`とManifestの選択が一致する
- Manifestに処理済み画像のpath・lineage・treatment情報がある
- image phaseがCURRENT
- 実レンダリング上でtarget slotが更新されている
- Image HarmonyのBlockingが0
- test-only `mock` providerが残っていない

未解決Recipe、Manifest不整合、処理済み画像欠落、Mock画像はFinal Exportで明示的に拒否する。

## Render安定化

- LibreOffice変換ごとに独立user profileを使用
- source render cache欠落時は一度だけ安全に再構築
- PDF画像化は`pdftocairo`を優先し、失敗時に`pdftoppm`へfallback
- LibreOffice / Poppler / PDF text extractionへtimeoutを設定
- 同一App Serverプロセス内の連続レンダリング回帰テストを追加

## Tests

```text
11 / 11 test groups PASS
```

画像回帰テスト:

- local auto selection
- candidate threshold
- explicit mock only
- crop / grading
- source lineage
- source Picture shape ID / geometry / rotation / mask保持
- processed asset bytesのPPT内一致
- rendered slot change
- mutation mask外Pixel Diff
- Recipe Overrideの最小STALE

## 未検証

- 実 `OPENAI_API_KEY` を用いたライブ画像生成
- 実Codex CLI + App Server + SolのライブE2E

アダプター実装とライブ成功は区別する。

## 次の優先実装

1. live Codex / OpenAI E2E
2. photo+text / two-column / full_bleed Layout Family
3. Vision asset classification / semantic ranking
4. editable diagram / infographic
5. Deck Harmony actual-render v0.2
