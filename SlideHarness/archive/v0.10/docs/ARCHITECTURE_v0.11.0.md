# SlideHarness Next v0.11 — Greenfield Architecture

## 0. 文書情報

- 状態: Draft
- 対象仕様: [SPEC_v0.11.0.md](SPEC_v0.11.0.md)
- 方針: 既存2実装のコード引用を前提としないGreenfield設計

---

## 1. アーキテクチャ目標

次の責務を分離する。

```text
原稿理解
  ↓
情報網羅性の管理
  ↓
スライド構成
  ↓
具体的な版面レシピ
  ↓
テンプレートのデザイン適用
  ↓
画像・図表の解決
  ↓
PPTX合成
  ↓
実レンダーQA
```

テンプレート解析とレイアウト生成を同じ責務にしない。
意味構造と描画座標を同じデータに混在させない。

---

## 2. コンポーネント

### 2.1 Ingestor

責務:

- 入力ファイルの検証
- 原稿テキスト・表・画像の抽出
- ファイルハッシュ
- 入力の不変保存
- 機密データ境界の管理

出力:

- `source_manifest.json`
- `source_units.json`
- `source_assets.json`

### 2.2 Content Modeler

責務:

- 原稿の情報単位化
- 事実、条件、数値、主張、根拠、例、注意事項の分類
- 重複検出
- 必須保持情報の指定
- 不足情報の明示

出力:

- `content_model.json`
- `coverage_requirements.json`

### 2.3 Template Compiler

責務:

- マスター、レイアウト、完成スライドの解析
- Tokens / Chrome / Components / Pattern Evidenceの抽出
- 代表スライドのレンダー解析
- テンプレート適応可能性の判定

出力:

- `template_system.json`
- `template_evidence.json`
- `template_risk_report.json`

### 2.4 Deck Architect

責務:

- ストーリー構造
- ページ順
- Primary Message
- Supporting Unit
- 原稿Coverage
- Appendix判断

出力:

- `deck_outline.json`
- `coverage_map.json`

### 2.5 Slide Recipe Planner

責務:

- 意味構造の判定
- 具体的なSlide Recipe選択
- スロットと情報量の割り当て
- 予測占有率と文字サイズの評価
- 代替レシピの指定

出力:

- `slide_specs.json`

### 2.6 Visual Director

責務:

- テンプレート由来のアートディレクション
- 画像の必要性判断
- 装飾画像の役割判断
- 画像スロット、構図、余白、比率の指定
- デッキ全体の画風統一

出力:

- `visual_direction.json`
- `asset_requests.json`

### 2.7 Asset Resolver

責務:

- ユーザー画像の選択
- テンプレート画像の再利用判断
- 画像生成
- クロップ・色調・解像度処理
- 画像QA

出力:

- `asset_manifest.json`
- 処理済み画像
- `asset_qa.json`

### 2.8 Layout Engine

責務:

- Slide Recipeから領域グラフを作る
- テンプレートのspacing / grid / typographyを適用する
- 制約を解く
- 座標を確定する
- オーバーフロー時に代替Variantを選ぶ

入力:

- `slide_specs.json`
- `template_system.json`
- `asset_manifest.json`

出力:

- `layout_plans.json`

### 2.9 Native Diagram Composer

責務:

- 表
- グラフ
- KPI
- フロー
- タイムライン
- 関係図
- 組織図

すべて編集可能なPowerPoint要素として生成する。

### 2.10 PPTX Composer

責務:

- PPTXパッケージ生成
- テンプレートChrome適用
- テキスト、画像、図表の配置
- 編集可能性の維持
- リレーションとメディア管理

### 2.11 Render QA

責務:

- PPTX構造検査
- PDF・画像レンダー
- はみ出し・重なり・空白・整列・コントラスト検査
- Content Coverage検査
- テンプレート忠実度検査
- ページ間調和検査

出力:

- `technical_qa.json`
- `content_qa.json`
- `design_qa.json`
- `deck_qa.json`

### 2.12 Revision Manager

責務:

- ユーザー修正
- ページLOCK
- 依存関係
- 最小再生成
- Revision conflict
- 履歴とロールバック

---

## 3. Canonical Data Model

### 3.1 Source of Truth

上流から下流へ次の順で扱う。

```text
immutable inputs
  ↓
content model / template system
  ↓
deck outline / coverage map
  ↓
slide specs / visual direction
  ↓
asset manifest / layout plans
  ↓
PPTX / render / QA
```

出力PPTXを上流データとして自動的に読み戻さない。

### 3.2 Slide Spec例

```yaml
slide_id: S-006
role: comparison
primary_message: 3つのプランは対象規模と運用範囲が異なる
source_unit_ids:
  - U-021
  - U-022
  - U-023
supporting_units:
  - id: SU-01
    kind: comparison_item
    source_unit_ids: [U-021]
  - id: SU-02
    kind: comparison_item
    source_unit_ids: [U-022]
  - id: SU-03
    kind: comparison_item
    source_unit_ids: [U-023]
recipe:
  id: comparison_3col
  variant: highlighted_center
density:
  target: compact
  predicted_occupancy: 0.72
visual:
  mode: native_shapes
  generated_image: none
template:
  chrome_policy: preserve
  component_style: comparison_card
```

### 3.3 Text layers

各テキストは次を分離する。

- `source_text`: 原稿そのもの
- `semantic_text`: 意味を保った構造化テキスト
- `display_text`: スライドに表示する文章
- `render_text`: 改行と最終フィットを反映した文字列

`render_text`から`source_text`を上書きしない。

---

## 4. Slide Recipe Engine

### 4.1 Recipe Contract

```yaml
recipe_id: card_grid_2x2
semantic_relations:
  - grouping
  - feature_set
supporting_units:
  min: 3
  max: 4
slots:
  - title
  - subtitle_optional
  - cards_3_to_4
  - takeaway_optional
density:
  min_occupancy: 0.58
  max_occupancy: 0.86
typography:
  body_min_pt: 9.5
fallbacks:
  overflow: split_or_card_grid_3x2
  underfill: title_body_callout
```

### 4.2 Geometry

- レシピは正規化座標と制約で定義する
- Template Compilerのマージンとグリッドへ変換する
- 固定ピクセル値だけに依存しない
- Optical alignment補正を持つ
- 文字実寸を測定して最終座標を決める

### 4.3 Underfill処理

1. 内容量に合う小さいレシピへ変更
2. Supporting Unitを意味的に再編成
3. 有用な図解・画像がある場合のみ追加
4. 意図的なstatementページへ変更

空のカード、巨大な空枠、無関係な装飾で埋めない。

### 4.4 Overflow処理

1. 重複削除
2. 表現圧縮
3. スロット配分変更
4. 高密度Variant
5. ページ分割
6. 下限内の文字縮小

---

## 5. テンプレート適用順序

```text
Slide Recipeの構造
  ↓
Template Grid
  ↓
Component Style
  ↓
Typography
  ↓
Color / Stroke / Radius / Effect
  ↓
Chrome
  ↓
Image Treatment
```

テンプレートに該当コンポーネントがない場合は、Tokensから新しいコンポーネントを組み立てる。

テンプレートの完成スライドを参照する場合も、内容や座標を無条件にコピーしない。

---

## 6. 画像生成境界

画像生成はホスト側の画像生成機能を利用する。
ローカルコアが秘密情報を保持したり、未承認の外部Providerへ接続したりしない。

各Asset Requestは次を持つ。

```yaml
request_id: AR-S006-01
slide_id: S-006
role: decorative_support
slot:
  aspect_ratio: 1.8
  subject_placement: right
  text_safe_area: left
art_direction:
  palette: template
  lighting: soft
  texture: restrained
  exclusions:
    - embedded text
    - watermark
```

生成結果はrequest_idへ固定し、別ページへ暗黙流用しない。

---

## 7. QA Architecture

### 7.1 Structural metrics

- meaningful occupancy
- largest unexplained void
- alignment deviation
- inter-block gap consistency
- text overflow
- text size floor
- item count rendered / expected
- empty container count
- page balance

### 7.2 Template metrics

- palette distance
- typography hierarchy distance
- grid alignment
- chrome preservation
- component-style consistency
- image-treatment consistency

### 7.3 Content metrics

- required fact coverage
- number/date/currency exact match
- source-to-slide traceability
- unsupported claim detection
- chart-data consistency

### 7.4 Human gate

自動QA合格だけで完成としない。

次の2回は人間確認を必須とする。

1. 代表3ページ
2. 最終全体モンタージュ

---

## 8. State Model

主要状態:

- DRAFT
- READY_FOR_SAMPLE
- SAMPLE_REVIEW
- APPROVED_FOR_FULL_BUILD
- BUILDING
- REVIEW_REQUIRED
- APPROVED
- LOCKED
- STALE

ページ単位の状態とデッキ全体の状態を分離する。

---

## 9. Technology Selection Gate

実装言語とPPTXライブラリはGreenfield評価で決める。

最低限、次のSpikeを同一Golden Pageで比較する。

- テンプレートChrome保持
- 日本語テキスト計測
- 編集可能な表
- 編集可能なグラフ
- 編集可能なフロー図
- 画像クロップとマスク
- レンダー再現性
- パッケージ修復性
- 処理速度

評価候補には、少なくとも次を含める。

- PptxGenJS
- python-pptx + OOXML拡張
- 既存PPTXのOOXML直接操作を組み合わせた方式

現行コードがPythonまたはJavaScriptであることを採用理由にしない。

---

## 10. 実装フェーズ

### Phase 0 — Golden Corpus

- 同一原稿
- 3テンプレート
- 人手による理想スライド
- 評価基準

### Phase 1 — Template Compiler

- Tokens
- Chrome
- Components
- Pattern Evidence
- 忠実度レポート

### Phase 2 — Core Proposal Engine

- Content Model
- Coverage Map
- Deck Outline
- 主要Slide Recipe
- PPTX Compose
- 基本QA

対象レシピ:

- cover
- title_body_callout
- two_column
- card_grid_2x2
- three_column
- comparison
- table
- process
- closing_cta

### Phase 3 — Native Visuals

- グラフ
- タイムライン
- 関係図
- 組織図
- 高度な表

### Phase 4 — Image Generation

- Art Direction
- Asset Request
- 生成画像適用
- Image Harmony QA

### Phase 5 — Revision UX

- ページ修正
- 画像のみ差し替え
- LOCK
- 履歴
- 最小再生成

---

## 11. 既存実装との境界

- 現行v0.10を上流仕様として扱わない
- 現行データモデルへの互換性を初期要件にしない
- n2p-pptxの関数・座標・定数を直接コピーしない
- 現行SlideHarnessのRendererやState実装を直接コピーしない
- 既存Golden Sampleは比較対象であり、合格基準ではない

既存機能を再利用する場合は、Phaseごとに次を文書化する。

- 再利用対象
- 再利用理由
- 新仕様への適合確認
- 代替案との比較
- ライセンスと出典
- 置き換え可能性

「すでにあるから」は再利用理由にならない。
