# PPT自動生成Skill / Codex App Server 仕様書

**Version 0.10.0 — Simplification Addendum適用版**

## v0.10 Simplification Addendum

この仕様書に残る詳細な内部フェーズは設計履歴として保持する。実装上のAI判断フローは`docs/SIMPLIFICATION_v0.10.0.md`を優先し、`Input Analysis → Deck Plan → Slide Plan → Compose → Validate`の5段階とする。`visual_plan.json`、`slide_matching.json`等はSlide Planから派生する互換ビューであり、独立したモデル呼び出しを行わない。通常の意味判断は2回、ページ再提案は最大1回とする。

---

## 1. 目的

既存のPowerPointテンプレート、原稿、`design.md`を入力すると、原稿内容をプレゼンテーションとして再構成し、既存PPTのデザイン文法を活かした編集可能なPPTXを生成する。

単純な「文章の流し込み」ではなく、以下を自動的に行う。

- 原稿から最適なスライド構成を設計する
- 1スライド1メッセージを原則として各ページの主張を決める
- 写真、グラフ、表、フロー図、インフォグラフィックなどから適切な表現形式を選ぶ
- 元PPTの各ページの用途を解析する
- 今回のスライド用途と元PPTをマッチングする
- 元PPTのレイアウト・ブランド要素を可能な限り維持する
- 内容量に応じてレイアウトを適応させる
- 不自然な折り返し、重なり、はみ出し、画像比率崩れを防止する
- ページ単位・全体単位で品質検査する
- 各工程でAIが行った判断を記録する
- 完成後も、他ページを不用意に変更せず部分修正できる

初期はCodex Skillとして実装し、将来的に同一のコアエンジンをCodex App Serverから操作できる構成とする。

---

# 2. 今回のテストケース

## 2.1 元PPT

今回のテストでは、MIRI Companyの汎用プレゼンテーションテンプレートを利用する。表紙には所属機関・部署・氏名などを入れる構造が存在する。

テンプレートには、例えば以下のレイアウト資産が存在する。

- 3項目説明
- 写真＋テキスト4項目
- KPI・業績ハイライト
- タイムライン
- 4項目レイアウト

PowerPoint内部のレイアウト名だけではなく、実際のオブジェクト配置・画像・テキスト容量・反復装飾などから「何に使えるページか」を解析する。

## 2.2 原稿

テスト原稿は「Aha! レシート Lite セールスシート」とする。

主な訴求は、

- 公開準備から抽選までを一元化
- 導入しやすい価格
- 条件が揃えば最短即日
- 管理画面から主要設定を変更可能

である。

原稿にはGoogleフォーム・Lite・フル版の機能比較データも含まれる。

また、完成原稿だけでなく、制作指示や省略指示も混在している。たとえば「8.9.10 は省略可能」という指示が存在する。

このため、原稿をそのままスライド本文として扱わず、内容分類を行う。

---

# 3. システム基本原則

## 3.1 Source of Truth

情報の優先順位を以下とする。

1. ユーザーが明示した指示
2. 原稿・支給データ
3. `design.md`
4. 構成設計
5. ページ表現設計
6. レイアウト判断
7. QAによる微調整

下位工程が上位工程の意味を勝手に変更してはならない。

最終PPTXは成果物であり、原則としてSource of Truthにはしない。

---

## 3.2 下流成果物を上流へ自動昇格させない

例：

原稿：

> 素材が揃えば、最短即日でキャンペーン開始可能。

レイアウト調整後：

> 素材が揃えば、最短即日で開始。

この場合、

- 原稿
- 意味を整理した文章
- 実際に表示する文章

を別々に保存する。

```
source_text:
  素材が揃えば、最短即日でキャンペーン開始可能。

semantic_text:
  素材が揃えば最短即日で開始可能

render_text:
  素材が揃えば、最短即日で開始。

render_adjustment:
  shorten_for_fit

```

後からレイアウトを変更する際は、`render_text`をさらに編集するのではなく、`source_text`または`semantic_text`から再生成する。

ユーザーが明示的に「この完成版の文章を正式文言にする」と指定した場合のみ上位データへ昇格できる。

---

# 4. ユーザーから見える処理フロー

GUIは内部処理をすべて露出させない。

基本フローは以下の3段階とする。

```
1. 構成を決める
      ↓
2. スライドを作る
      ↓
3. 確認・修正する

```

通常はこの3段階だけを見せる。

内部では詳細なフェーズを実行し、必要な場合のみ判断理由や詳細設定を展開する。

## 4.1 GUIと内部フェーズの関係

GUIの画面数と内部フェーズ数は1対1に対応させない。

GUIは原則として3画面に固定し、内部フェーズの進行に応じて同一画面内の状態を切り替える。

特に画面2「構成・制作」は、内部的に以下の状態を持つ。

```
structure_review
      ↓
sample_generation
      ↓
sample_review
      ↓
deck_generation
      ↓
page_review
```

ユーザーにPhase番号、JSON、依存グラフ、座標、マッチング計算式などを常時見せない。

必要な場合のみ「判断理由」「変更内容」「別候補」などを開いて詳細を確認できる段階的開示とする。

---

# 5. 内部処理フロー

```
入力
 ↓
Phase 0  制作条件整理
 ↓
Phase 1  原稿解析
 ↓
Phase 2  PPT解析
 ↓
Phase 3  スライド構成設計
 ↓
Phase 4  ページ表現設計
 ↓
Phase 5  元PPTマッチング
 ↓
Phase 6  コンテンツ編集
 ↓
Phase 7  レイアウト生成
 ↓
Phase 8  ページ単位QA
 ↓
Phase 9  全体調和QA
 ↓
PPTX出力

```

---

# 6. Phase 0：制作条件整理

## 入力

- 元PPTX
- 原稿
- `design.md`
- 任意の画像
- CSV・表データ
- ロゴ・ブランド素材
- ユーザー追加指示

## 判断項目

- プレゼンテーションの目的
- 想定する閲覧者
- 営業資料・説明資料・報告資料などの用途
- ページ数目安
- 必須内容
- 任意内容
- 削除可能内容
- 原文固定箇所
- PPT変更許可範囲
- 画像生成可否

推測した条件にはconfidenceを付与する。

---

# 7. Phase 1：原稿解析

原稿を意味単位に分割する。

## 分類

- customer\_copy
- heading
- supporting\_copy
- numerical\_evidence
- comparison\_data
- conditional\_claim
- note
- editorial\_instruction
- visual\_instruction
- optional\_section

今回の原稿では、例えば「最短即日」は訴求である一方、キャンペーン素材・規約・実施条件の確定など条件付きである。

条件部分を削除して「必ず即日」と誤認させる表現には変更しない。

---

# 8. Phase 2：元PPT解析

PPTの各ページを「Visual Grammar」として解析する。

## ページごとの解析項目

- ページ用途
- タイトル領域
- 本文領域
- 画像領域
- 表・グラフ領域
- レイアウト構造
- グリッド
- 余白
- テキスト容量
- 画像の推奨縦横比
- 固定装飾
- 可変コンテンツ
- レイアウト変更可能範囲

## ページ用途例

```
cover
section
statement
overview
comparison
three_items
four_items
process
timeline
chart
kpi
table
photo_grid
organization
summary
cta
closing

```

複数用途を持つことを許可する。

---

# 9. PPT内画像の分類

PPT上の画像をすべて一括して「差し替え画像」と扱わない。

内部的に以下へ分類する。

## 9.1 template\_chrome

マスター寄りの装飾。

例：

- ロゴ
- 上部ライン
- 背景
- コーナー装飾
- 反復するブランドモチーフ
- ページ番号周辺装飾

### 基本処理

**保持する。**

---

## 9.2 content\_visual

本文内容を説明する画像。

例：

- 写真
- グラフ
- インフォグラフィック
- 図解
- フロー図
- 人物画像
- 説明用アイコン
- スクリーンショット

### 基本処理

**今回の原稿に応じて差し替える。**

PPT 5ページ目のグラフ類は本文データに依存するため、この分類となる。

---

## 9.3 container\_or\_frame

本文コンテンツを収めるデザイン上の器。

例：

- 写真枠
- カード
- 図版台座
- モックアップ枠
- 背景パネル

### 基本処理

**外形・意匠は保持し、中身だけ変更する。**

---

## 9.4 unknown

自動分類の確信度が低いもの。

### 基本処理

自動変更せず、必要に応じてユーザーへ確認する。

---

# 10. 画像分類のGUI

通常はオブジェクト単位の分類をすべて表示しない。

表示：

```
画像：自動処理済み

```

問題がある場合のみ、

```
画像について1件確認が必要です

```

と表示する。

ユーザーへの質問は最小限とする。

```
この画像をどう扱いますか？

○ デザイン要素として残す
○ 内容画像として差し替える

```

詳細分類・confidence・判定ログは内部に保持する。

---

# 11. Phase 3：スライド構成設計

原稿から最適なプレゼンテーション構成を作る。

## 基本原則

- 1ページ1メッセージ
- 原稿順を機械的に踏襲しない
- 重複内容は統合
- 情報量が多い場合は分割
- 主ストーリーに不要な情報はAppendix候補へ
- 重要な条件・注意書きを削除しない

## 出力例

```
slide_id: S06

role:
  process

message:
  公開から抽選までを一つの管理画面で

source_units:
  - manuscript_06

importance:
  primary

```

今回の原稿では、「公開する → 受け付ける → 見届ける → 抽選する」という明確な4工程が存在する。

---

# 12. ユーザー確認ポイント1：構成確認

GUIでは以下だけを見せる。

```
S01　メインメッセージ
S02　導入しやすい理由
S03　機能比較
S04　価格の仕組み
...

```

可能な操作：

- OK
- ページ追加
- ページ削除
- 順序変更
- メッセージ変更
- 統合
- 分割
- 指示して構成を作り直す

この段階ではデザイン詳細を見せない。

---

# 13. Phase 4：ページ表現設計

各スライドのメッセージに対して最適な情報表現を決定する。

## 選択可能な表現

- text\_statement
- photo
- photo\_grid
- illustration
- table
- comparison\_table
- bar\_chart
- line\_chart
- pie\_chart
- KPI
- flow
- timeline
- relationship\_diagram
- architecture\_diagram
- infographic
- screenshot
- no\_visual

## 基本判断例

```
時系列 → timeline
工程 → flow
数値比較 → bar_chart
推移 → line_chart
機能差 → comparison_table
関係性 → relationship_diagram
世界観 → photo

```

数値データが存在しない場合は、意味のある数値グラフを捏造しない。

---

# 14. Phase 5：元PPTマッチング

各出力スライドと元PPTのページを比較する。

## 評価軸

- 用途適合度
- 項目数
- 情報量
- Visual Type適合度
- テキスト容量
- 画像領域
- 元デザイン維持度
- 変更コスト

## 出力

第1候補だけでなく複数候補を保持する。

```
slide_id: S06

candidate_1:
  source_slide: 14
  score: 0.91

candidate_2:
  source_slide: 15
  score: 0.78

```

ユーザーには原則として第1候補のみ見せる。

---

# 15. 元PPTの変更レベル

## DIRECT

- テキスト差し替え
- 本文画像差し替え

だけで成立する。

## ADAPT

基本構造を残し、

- 列幅変更
- 画像サイズ変更
- テキスト領域変更

などを行う。

## RECOMPOSE

元ページの、

- 色
- タイポグラフィ
- グリッド
- 装飾
- 見出し構造

を継承しながら内容部分を再構成する。

## NEW

元PPT内に適切なページが存在しない場合のみ新規生成する。

NEWでも元PPTのVisual Grammarを使用する。

---

# 16. Phase 6：コンテンツ編集

原稿をスライド用コピーへ変換する。

## 原則

意味を変えずに、

- 短くする
- 結論化する
- 箇条書き化する
- 見出し・補足へ分ける
- 図表ラベルへ変換する

ことを許可する。

## 情報が収まらない場合の優先順位

```
1. 冗長表現削除
2. 情報構造整理
3. 補足情報圧縮
4. テキスト領域変更
5. レイアウト変更
6. 元PPT候補変更
7. ページ分割
8. フォント縮小

```

フォントサイズ縮小を第一選択にしない。

---

# 17. Phase 7：レイアウト生成

LLMに最終座標を直接決定させない。

LLMが決めるのは、

```
layout_family:
  image_left_text_right

ratio:
  visual: 0.58
  text: 0.42

visual_priority:
  high

```

までとする。

実座標はレイアウトエンジンが、

```
Design Token
 ↓
Grid
 ↓
Layout Family
 ↓
Slots
 ↓
Constraint
 ↓
Coordinates

```

の順に計算する。

## 17.1 ページ単位のレイアウト方針

「画面を埋める」を全ページ共通の目的にしない。各Slide Planは、ページ意図に応じて以下の`fill_policy`を持つ。

```text
preserve_source
intentional_whitespace
balanced
content_filled
full_bleed
```

### preserve_source

元PPTの意味のある空白とコンテンツ領域を維持する。明示的に再構築対象とした元オブジェクト領域を優先する。

### intentional_whitespace

表紙、セクション、ステートメント、引用、単一KPI、クロージングなどで、余白により一つの焦点を強調する。

### balanced

概要、写真＋説明、ケース紹介などで、情報と余白を中間的に配置する。

### content_filled

比較、工程、表、タイムライン、複数項目など、一覧性が必要なページでコンテンツキャンバスを広く使う。

### full_bleed

実在する写真・ビジュアルが主役の場合に限り、ビジュアル領域を全面的に利用する。

`full_bleed`はv0.6で実行可能とする。ただし、`full_bleed` Layout Familyと、実在するselected / processed visual assetが揃う場合だけ使用する。テキストのみのページ、未解決Image Recipe、弱いビジュアルの単純拡大では実行しない。未対応familyや未解決画像を完成したように偽装してはならない。

余白を埋める目的だけで、原稿にない文章、意味のない写真、アイコン、装飾を追加してはならない。

## 17.2 LAYOUT_FIT_TO_INTENT

レイアウトQAは単純な占有率ではなく、ページ意図への適合を判定する。

記録項目：

```text
fill_policy
content_extent_width_ratio
content_extent_height_ratio
occupied_area_ratio
left/right/top/bottom_void_ratio
center_offset_x/y_ratio
expected/rendered_item_count
intentional_whitespace
accidental_dead_space
reason_codes
score
status
```

`intentional_whitespace`と`preserve_source`では、大きな端部余白だけを理由に失敗させない。ただし、コンテンツが小さすぎる、semantic itemが欠落している、焦点が極端に偏っている場合はblockingとする。

`content_filled`では、比較・工程・複数項目の一部が小さく固まり、説明できない空白が残る場合をblockingとする。

単一の短い主張を`content_filled`へ強制し、文字を拡大するだけで占有率を上げることはsemantic policy mismatchとしてblockingにする。

Layout Engineが解決した実効fill policyは、選定理由・confidence・fit-to-intent結果・再実行範囲とともにDecision Traceへ追記する。同一判断での再composeは重複記録しない。

---

# 18. `design.md`

`design.md`は色指定だけでなく、制作ルールを定義する。

## Hard Constraint

例：

```
image:
  preserve_aspect_ratio: true
  distortion: forbidden

layout:
  overlap: forbidden
  out_of_bounds: forbidden

text:
  unnatural_japanese_wrap: forbidden

brand:
  template_chrome_removal: forbidden

```

## Soft Constraint

例：

```
density:
  medium_low

whitespace:
  generous

visual_variety:
  moderate

template_reuse:
  preferred

layout:
  default_fill_policy: balanced

whitespace:
  allow_intentional_whitespace: true
  preserve_source_whitespace: true
  forbid_filler_content: true

fill_policy_by_role:
  cover: intentional_whitespace
  section: intentional_whitespace
  statement: intentional_whitespace
  comparison: content_filled
  process: content_filled
  table: content_filled
  closing: intentional_whitespace

```

色・フォント・ブランド意匠については、原則元PPTから抽出する。

---

# 19. 代表ページ試作

全ページ生成前に、性質の異なる2〜3ページを試作する。

今回のテスト候補：

- 比較表ページ
- 4ステップページ
- 4項目ページ

これにより、

- 元PPTらしさ
- 文章量
- 画像差し替え方法
- レイアウト変更量
- タイポグラフィ
- 余白
- QAルール

を先に確定する。

---

# 20. ユーザー確認ポイント2：代表ページ確認

GUIでは大きなスライドプレビューを中心にする。

表示情報は最小限とする。

```
メッセージ：
公開から抽選までを一元管理

表現：
4ステップフロー

元PPT：
14ページをベースに作成

```

操作は原則、

- OK
- 別案
- 指示してやり直す

の3種類とする。

必要な場合のみ「判断理由を見る」を開ける。

---

# 21. 判断理由

通常は折りたたむ。

例：

```
4ステップフローを選んだ理由

・原稿に4つの連続工程がある
・元PPT 14ページの構造が近い
・写真より工程図の方が内容理解に適している

```

内部ではより詳細な判断ログを保存する。

---

# 22. Phase 8：ページ単位QA

各ページを生成した直後に品質検査する。

全ページ完成後まで問題を持ち越さない。

## 物理QA

- テキストはみ出し
- オブジェクト重複
- スライド外配置
- 画像アスペクト比
- グリッド違反
- 最小余白
- フォント問題

## 日本語QA

- 助詞だけ次行
- 数字と単位分離
- 括弧孤立
- 固有名詞途中改行
- 1〜3文字だけ最終行
- 極端に短い最終行
- 意味の切れ目と改行の不一致

---

## 22.1 レンダリングプロセスの分離

App Serverでは複数ページの生成・QAが連続または並行して実行されるため、LibreOfficeの共有ユーザープロファイルを使用しない。変換ごとに一時プロファイルを作成し、profile lockや別リクエストへの接続を防ぐ。

PDF画像化は`pdftocairo`を優先し、利用できない環境では`pdftoppm`へフォールバックする。LibreOffice、PDF画像化、PDFテキスト抽出にはtimeoutを設け、外部プロセスが停止した場合はQAエラーとして扱い、処理全体を無期限に待機させない。

---

# 23. ページQAのフィードバックループ

```
生成
 ↓
Render
 ↓
QA
 ↓
PASS → LOCK
 ↓
FAIL
 ↓
文章調整
 ↓
レイアウト調整
 ↓
別レイアウト
 ↓
別元PPT
 ↓
必要ならページ分割提案

```

上位構成を変更する必要がある場合は、自動で勝手に変更せず、上位フェーズへ変更要求を返す。

---

# 24. Phase 9：全体調和QA

全ページ完成後に以下を確認する。

- 同一レイアウトの連続
- 情報密度の偏り
- 写真・図解・グラフの偏り
- 余白リズム
- タイトル位置
- アクセント色量
- セクション切り替え
- 全体ストーリー

このフェーズでは、問題を検出しても全ページを自動再生成しない。

該当ページだけ修正候補として提示する。

---

# 25. ユーザー確認ポイント3：最終確認

全ページを一覧表示する。

通常ページ：

```
✓

```

問題候補：

```
!

```

例：

```
3ページ確認してください。

S03　タイトル折り返し
S06　前後ページとレイアウトが類似
S08　情報密度が高い

```

ユーザーは問題ページだけ修正する。

---

# 26. 完成後の修正

完成後はスライドを選択し、自然言語で指示する。

例：

```
もっとシンプルに

写真ではなく図解に

文章を半分に

元PPT 15ページを使って

このページで伝えるメッセージ自体を変えたい

```

システムが変更内容を解析し、必要な再実行範囲を判断する。

ユーザーに内部フェーズ番号を意識させない。

---

# 27. 修正範囲

## オブジェクト変更

例：

> 写真だけ変える

処理：

```
画像差し替え
 ↓
該当ページQA

```

他ページは変更しない。

## ページ変更

例：

> このページを写真ではなく図解にする

処理：

```
Visual Plan
 ↓
Layout
 ↓
Render
 ↓
QA

```

該当ページのみ再生成する。

## ページ設計変更

例：

> このページで伝える内容を変える

処理：

```
Page Plan
 ↓
Visual Plan
 ↓
Source Match
 ↓
Layout
 ↓
QA

```

## 全体構成変更

例：

> このページを削除して、前ページに統合する

構成以降を必要範囲だけ再評価する。

---

# 28. STALE管理

上流データが変更された場合、影響を受ける下流データを`STALE`にする。

例：

```
S06 Message       MODIFIED
S06 Visual Plan   STALE
S06 Source Match  STALE
S06 Layout        STALE
S06 PPT           STALE
S06 QA            STALE

S01〜S05          KEEP
S07〜S09          KEEP

Deck Harmony      STALE

```

---

# 29. 状態

各成果物は以下の状態を持つ。

```
DRAFT
生成途中

APPROVED
現在の案として承認

LOCKED
自動変更禁止

STALE
上流変更により再生成が必要

REVIEW_REQUIRED
ユーザー確認が必要

```

---

# 30. バージョン管理

再生成時に旧結果を破棄しない。

```
S06 v1
元PPT 14ベース

S06 v2
元PPT 15ベース

S06 v3
v1をベースに文章だけ調整

```

以下を可能にする。

- 前バージョンへ戻す
- 2案比較
- 現バージョンを正式版にする

---

# 31. 判断ログ

各判断には以下を保存する。

```
decision_id:
  S06_visual_type

selected:
  four_step_flow

alternatives:
  - timeline
  - four_cards

reason:
  - 4工程が明確
  - 工程間の連続性が重要

confidence:
  0.94

user_override:
  null

rerun_scope:
  - S06_layout
  - S06_render
  - S06_qa
  - deck_harmony

```

---

# 32. GUI方針

## 原則

**内部処理は細かく、GUIは粗くする。**

ユーザーに、

- 画像分類一覧
- 座標
- JSON
- マッチング計算式
- phase番号

を常時見せない。

---

# 33. GUI画面構成

基本3画面とする。

## 33.1 画面1：入力

### 表示

```
元PPT
原稿
design.md
その他素材
```

### 主要操作

```
生成を開始
```

高度な条件は「詳細設定」に格納する。

詳細設定では、必要に応じて以下を指定できる。

- プレゼンテーション用途
- 想定閲覧者
- ページ数目安
- 原文固定
- 画像生成可否
- 元PPTの変更許容度
- Review Mode / Standard Mode / Automatic Mode

---

## 33.2 画面2：構成・制作

画面2はURLや大枠を変えず、内部状態に応じて表示内容を切り替える。

### State A：structure_review

スライド構成を確認する状態。まだ完成スライドの生成を前提としない。

左：

```
S01
S02
S03
...
```

中央：

```
スライド構成一覧
ページごとのメインメッセージ
```

右：

```
このページの役割
採用した原稿範囲
省略・統合判断
判断理由 ▼
```

操作：

```
構成を承認
ページ追加
ページ削除
順序変更
統合
分割
メッセージ変更
指示して構成を作り直す
```

この状態ではデザイン詳細を前面に出さない。

### State B：sample_generation / sample_review

代表2〜3ページを生成し、デザインルールを確定する状態。

左：

```
代表ページ一覧
生成中 / 完了 / 要確認
```

中央：

```
大きなスライドプレビュー
```

右：

```
メッセージ
表現形式
流用した元PPT
変更方式 DIRECT / ADAPT / RECOMPOSE / NEW
元PPTから何を残したか
判断理由 ▼
変更内容 ▼
```

主要操作：

```
OK
別案
指示してやり直す
```

代表ページでの修正にはScopeを持たせる。

```
このページだけに適用
全体ルールとして適用
```

例：

- 「S06だけタイトルを小さく」→ Local Change
- 「全ページでタイトルを少し小さく」→ Rule Change

### State C：deck_generation / page_review

全ページ生成・ページ別修正状態。

左：スライド一覧・状態バッジ

```
S01  ✓ 完了
S02  ✓ 完了
S03  ! 要確認
S04  ● 修正中
S05  🔒 固定
```

中央：

```
選択中スライドのプレビュー
```

右：

```
このページのメッセージ
表現形式
流用した元PPT
変更方式
判断理由 ▼
変更内容 ▼
別候補 ▼
```

画面下部または右パネルに自然言語入力を置く。

```
このページへの指示...                         [送信]
```

ページメニュー：

```
このページを固定
変更履歴
前の案に戻す
設計から見直す
```

---

## 33.3 「変更内容」の表示

PPT内画像・装飾の詳細分類を通常は露出しない。

通常表示：

```
元PPTから
✓ ブランド装飾：保持
✓ 写真：差し替え
✓ 写真枠：保持

変更内容を見る ▼
```

展開時：

```
上部ライン      保持
ロゴ            保持
写真01          差し替え
カード枠        保持
グラフ          再構築
```

これにより、テンプレートの何を維持し、何を変更したかをユーザーが追跡できる。

---

## 33.4 「別案」の仕様

「別案」は、同一の上位意図を保ったまま別の表現案を生成する操作とする。

変更してよいもの：

- Visual Type
- 元PPT候補
- Layout Variant
- ADAPT / RECOMPOSE方式
- コピー表現
- content_visual

変更してはいけないもの：

- Primary Message
- 原稿上の事実
- 条件付き訴求の条件
- LOCKED要素
- 他ページ

Primary Message自体を変更する場合は、「このページで伝える内容を変える」「設計から見直す」等の明示操作を必要とする。

---

## 33.5 画面3：最終確認

全スライドを一覧表示する。

問題のないページ：

```
✓
```

要確認ページ：

```
!
```

例：

```
3ページ確認してください。

S03  タイトル折り返し
S06  前後ページとレイアウトが類似
S08  情報密度が高い
```

主要操作：

```
PPTXを書き出す
選択ページを修正する
全体調和の提案を適用
現在の状態で承認
```

問題があるページだけを修正し、合格済みページは不用意に再生成しない。

---

## 33.6 推奨画面レイアウト

```
┌─────────────────────────────────────────────┐
│ Project                         PPTXを書き出す │
├─────────┬───────────────────────┬───────────┤
│         │                       │           │
│ S01  ✓  │                       │ Message   │
│ S02  ✓  │     Slide Preview     │           │
│ S03  !  │                       │ Visual    │
│ S04  ●  │                       │           │
│ S05  🔒 │                       │ Source    │
│         │                       │ PPT 14    │
│         │                       │           │
│         │                       │ 判断理由 ▼ │
│         │                       │ 変更内容 ▼ │
├─────────┴───────────────────────┴───────────┤
│ このページへの指示...                [送信] │
└─────────────────────────────────────────────┘
```

---

# 34. 自然言語操作

GUI上の編集操作の中心を自然言語とする。

例：

```
写真をもっと大きく

文字を減らす

元PPTの雰囲気をもっと残す

このページだけ別案

3ページ目と4ページ目を統合

グラフではなく比較表にする

```

AI側で必要な内部処理範囲を判定する。

---

# 35. 低confidence時のUI

自動処理できる箇所はユーザーへ確認しない。

ユーザー確認が必要なのは、

- 画像分類が曖昧
- 原稿の意味が曖昧
- 元PPT候補が拮抗
- 数値の解釈が不明
- ブランド要素か本文要素か判断できない
- 原稿同士が矛盾

などの場合とする。

---

# 36. 出力

最終成果物：

```
output.pptx

```

内部成果物：

```
project.json
source_analysis.json
content_analysis.json
deck_plan.json
slide_plans.json
visual_plans.json
source_matches.json
layout_states.json
qa_results.json
decision_log.json
user_overrides.json
version_history.json

```

GUIでは内部JSONを通常表示しない。

---

# 37. PPTX要件

出力PPTXは、

- PowerPointで通常編集可能
- Google Slides等でも可能な限り編集可能
- テキストを画像化しない
- 表は可能な限り表として生成
- グラフは可能な限り編集可能な形式で生成
- 図解はPowerPoint図形を優先
- 写真は画像として配置
- 画像の縦横比を保持

する。

---

# 38. 初期Skill構成

```
slide-builder/
│
├── SKILL.md
│
├── scripts/
│   ├── analyze_source.py
│   ├── analyze_ppt.py
│   ├── classify_assets.py
│   ├── plan_deck.py
│   ├── plan_visuals.py
│   ├── match_slides.py
│   ├── fit_text.py
│   ├── compose_slide.py
│   ├── render_slide.py
│   ├── validate_slide.py
│   └── validate_deck.py
│
├── references/
│   ├── slide_taxonomy.md
│   ├── visual_taxonomy.md
│   ├── layout_rules.md
│   ├── writing_rules.md
│   └── qa_rules.md
│
└── schemas/
    ├── project.schema.json
    ├── deck_plan.schema.json
    ├── slide_plan.schema.json
    ├── decision.schema.json
    └── qa.schema.json

```

---

# 39. 将来のCodex App Server構成

ロジックをApp Server側へ埋め込まない。

```
Codex App Server UI
        ↓
Codex Agent
        ↓
Slide Engine
        ↓
PPTX

```

コア処理は独立したCLIまたはライブラリとする。

例：

```
slide-engine analyze
slide-engine plan
slide-engine build
slide-engine build --slide S06
slide-engine validate
slide-engine export

```

これにより、

- Skill
- CLI
- App Server
- 将来のAPI

から同一エンジンを使用できる。

---

# 40. v0.1の成功条件

今回のPPT・原稿を入力した際、

1. 原稿を適切なスライド構成へ変換できる
2. 元PPTから用途の近いページを選択できる
3. ブランド装飾を保持できる
4. 本文に関係する画像を正しく差し替えられる
5. 必要なら元レイアウトを適応・再構成できる
6. 文章の不自然な折り返しがない
7. オブジェクトが重ならない
8. 画像比率が崩れない
9. PowerPoint上で編集可能である
10. ユーザーがページ単位で修正できる
11. 修正時に他ページを不用意に再生成しない
12. 各判断の理由を後から確認できる
13. 上流変更によってデータが混濁しない

ことを合格条件とする。

---

# 41. v0.1で優先して検証するもの

最初から全機能を完成させない。

優先順位：

```
1. PPT解析
2. 原稿解析
3. 構成設計
4. 元PPTマッチング
5. テキストフィッティング
6. レイアウトQA
7. 部分再生成
8. 画像分類
9. Visual生成
10. Deck Harmony

```

まず、

**「画像生成を使わなくても、元PPT＋雑な原稿から、構成・文章量・レイアウトが成立したPPTが生成できる」**

状態を最初の基準とする。

その後、写真・グラフ・図解・インフォグラフィック生成を追加する。

---

# 42. 内部データモデルと再生成制御

GUIを単純に保つ一方、内部では以下を分離して保持する。

```
Source
  ↓
Analysis
  ↓
Intent
  ↓
Render
  ↓
Output
```

## 42.1 主な内部データ

```
project.json
source_manifest.json
manuscript_analysis.json
template_profile.json
source_slides.json
source_assets.json
deck_plan.json
visual_plan.json
slide_matching.json
slide_plans/
layout_plans/
qa_results.json
decision_trace.jsonl
overrides.yaml
approvals.json
project_state.json
dependency_graph.json
```

## 42.2 ページ単位のSource of Truth

各出力ページについて `slide_plan` を持ち、PPTX自体を設計情報の正としない。

概念例：

```yaml
slide_id: OUT-S006
message:
  primary: 公開から抽選までを一つの管理画面で
visual:
  type: process
  variant: four_step
source_template:
  slide_id: SRC-S014
  adaptation_mode: ADAPT
status: approved
```

## 42.3 Decision / Override / Approval / Lock

以下を分離する。

```
AIの判断        Decision
ユーザー上書き  Override
案として採用    Approval
自動変更禁止    Lock
```

優先順位：

```
User Override
    ↓
Approved Decision
    ↓
AI Decision
    ↓
Default
```

## 42.4 STALE伝播

上流が変わった場合、影響する下流だけを `STALE` にする。

例：

```
S06 Message       MODIFIED
S06 Visual Plan   STALE
S06 Source Match  STALE
S06 Layout        STALE
S06 Render        STALE
S06 QA            STALE
Deck Harmony      STALE

他スライド        KEEP
```

Render時には依存データがCURRENTであることを検証し、STALEな設計情報を使って出力しない。

## 42.5 semantic_text / render_text

意味と表示都合による文章を分離する。

```yaml
source_text: 原稿そのもの
semantic_text: 意味を整理した正規化文章
render_text: 現在のレイアウトに合わせた表示文章
```

レイアウト変更時は `render_text` から再短縮せず、`semantic_text` または `source_text` から再生成する。

---

# 43. 実装レイヤー

```
Codex Skill
対話・意味判断・ユーザー確認
        ↓
Core Engine
State / Planning / Dependency / QA
        ↓
PPT Engine
解析 / 配置 / Render / PPTX操作
```

将来のApp Server化：

```
Web UI
  ↓
Codex App Server
  ↓
Codex Agent
  ↓
Core Engine
  ↓
PPT Engine
```

App Server側へスライド生成ロジックを埋め込まず、Core Engine以下を共通利用する。

---

# 44. AIとコードの責務分離

AIに任せる：

- 原稿の意味解析
- 重要度判断
- Deck Story設計
- 1ページ1メッセージ設計
- Visual Type選択
- 元PPT候補の意味的評価
- コピー編集
- 低confidence判断

コードで決定論的に処理する：

- PPT Shape抽出
- 座標・サイズ取得
- 画像hash
- 反復装飾判定の基礎情報
- フォント計測
- BBox / Overflow
- Overlap
- Aspect Ratio
- Grid検査
- Dependency / STALE管理
- Render
- Pixel Diff（将来）
- PPTX書き出し

LLMに不要な計算処理をさせない。

---

# 45. 初期実装モデル

初期PoCと基準品質の確立は、複雑な仕様解釈・状態管理・PPT構造判断を優先し、Solを基準モデルとして実装・評価する。

最初から複数モデルへ細かく分割せず、まずSolでGolden Sampleを作る。

安定後、以下のような低リスク処理はLuna等の軽量モデルへの置換をEvalで検討する。

- 単純な原稿ラベル分類
- 判断ログ整形
- 大量の低リスク抽出

BBox、Overlap、画像比率、STALE伝播等はモデルを使わずコードで処理する。

---

# 46. PoC実装順

最初から全ページ・全Visual生成を完成させない。

```
1. Project / State / Decision / Dependency
2. PPT Analyzer
3. Manuscript Analyzer
4. Template Asset Classification
5. Deck Plan
6. Slide Matching
7. 代表3ページ生成
8. QA
9. STALE / 部分再生成
10. 残りページへの展開
11. Visual生成拡張
12. Deck Harmony
```

代表ページでは、可能であれば以下をそれぞれ1例検証する。

```
DIRECT
ADAPT
RECOMPOSE
```

最重要テストは、

```
完成
 ↓
前フェーズ修正
 ↓
部分再生成
 ↓
別フェーズ修正
 ↓
部分再生成
```

を複数回行った後も、原稿・構成・Visual・元PPT・文章・Layout・PPTXの関係が追跡可能であることとする。

---

# 47. Codexへの実装指示上の注意

以下を実装上のHard Principleとして扱う。

1. GUIの3画面と内部Phaseを1対1対応させない。
2. 画面2は内部状態を持ち、同一画面内で構成確認からページ修正まで遷移する。
3. 「別案」はPrimary Messageを変更しない。
4. Primary Message変更は「設計から見直す」操作として扱う。
5. template_chromeは原則保持し、content_visualを原稿に応じて差し替える。
6. container_or_frameは外形を保持し、中身だけ変更する。
7. Output PPTXをSource of Truthとして再入力しない。
8. 下流生成物を上流へ自動昇格させない。
9. 上流変更時は依存する下流だけSTALEにする。
10. LOCKEDなページ・オブジェクトを自動変更しない。
11. 部分修正で無関係なページを再生成しない。
12. 全ページ完成後のDeck Harmony修正も対象ページだけを再生成する。
13. 代表ページでの修正がLocalかGlobal Ruleかを区別する。
14. 判断ログを保持するが、GUIでは段階的に開示する。
15. PPTXは可能な限りPowerPoint上で編集可能なネイティブ要素で構成する。

---

# 48. 最終的なプロダクト原則

このシステムは、

> AIが自動で全部作るシステム

ではなく、

> AIが原稿とテンプレートを理解して最適案を作り、ユーザーが必要な箇所だけ確認・修正できるシステム

を目指す。

UI上の操作は簡単にする一方、内部では、

```
Source of Truth
      ↓
Decision Graph
      ↓
Slide Plan
      ↓
Visual / Layout Plan
      ↓
Rendered PPT

```

を明確に保持する。

これにより、完成後に前工程へ戻った場合でも、既存の下流成果物が上流判断へ混ざることを防ぎ、必要な範囲だけ安全に再生成できる構造とする。
# 43. Design Continuity / Art Direction (v0.4)

## 43.1 Design Fingerprint
元PPTから色・フォントだけでなく、タイトル軸、共通整列軸、余白傾向、反復装飾、写真枠の扱い等を `analysis/design_fingerprint.json` に抽出する。

## 43.2 Component Catalog
元PPTの各レイアウトを再利用可能な構造資産として `analysis/component_catalog.json` に保持する。RECOMPOSEでは原則としてPrimary Sourceは1ページ、Supporting Component Sourceは最大2ページとし、無制限な混在を禁止する。

## 43.3 Continuity Plan
各出力スライドに `planning/continuity_plan.json` を作成し、継承する要素を `macro / middle / micro` の3階層で記録する。大きく書き換えても、どの元PPT要素を継承したか追跡可能にする。

## 43.4 Deck Art Direction
画像をページごとに場当たり的に生成しない。`planning/deck_art_direction.json` でデック全体の明度・彩度・背景密度・ネガティブスペース・アクセント色利用方針を先に定義する。

## 43.5 Image Recipe
写真・イラスト・スクリーンショットが必要なページには `planning/image_recipes.json` を作る。画像内容だけでなく、target slot、縦横比、焦点位置、文字用余白、フレーム処理まで指定する。

## 43.6 Continuity QA
`SOURCE_CONTINUITY` を実行する。RECOMPOSEで利用可能な継承層が欠落する場合は完成扱いにしない。v0.5では `IMAGE_SOURCE_LINEAGE`、`IMAGE_TREATMENT_APPLIED`、`IMAGE_TEMPLATE_HARMONY`、`DECK_IMAGE_COHERENCE` を実画像・実レンダリングまで含めて評価する。

# 49. Image Pipeline v0.5

## 49.1 基本原則

画像は、生成・支給・選定しただけでは完成扱いにしない。元PPTのsource content slot、Deck Art Direction、Picture Frame、Render QAへ接続する。

```text
Image Recipe
  ↓
manual / local / OpenAI candidate
  ↓
slot-aware crop / focal placement
  ↓
deck-wide grading
  ↓
source Picture in-place replacement
  ↓
actual render image QA
```

余白を埋めるためだけの画像追加を禁止する。Image Recipeが存在するページだけを画像処理対象にする。

## 49.2 Provider

- `manual`: Recipeへユーザーが特定画像を指定
- `local`: `inputs/assets/`から自動選定
- `auto`: manual selection → local → OpenAIの順。未解決ならReview Required
- `openai`: Images APIから生成
- `mock`: 明示されたテスト専用。通常運用で自動採用しない

## 49.3 候補選定

Local candidateは次を評価する。

- target aspect
- effective resolution
- source-deck visual metrics
- filename semantic tokens
- negative-space fitness
- reuse penalty

複数候補とスコアをManifestへ保存し、後から別候補へ切り替え可能にする。

## 49.4 Image Treatment

- target slot比率へのcover crop
- focal point保持
- copy sideのnegative spaceを考慮したcrop候補探索
- brightness / saturation / contrast / warmth / detailをDeck Art Directionへrestrained adjustment
- 変更前後のmetricsと補正係数を保存

## 49.5 PowerPointへの適用

既存Picture Shapeが存在する場合、Relationshipだけを交換する`preserve_format`を優先する。

保持対象:

- shape id
- z-order
- x/y/w/h
- rotation
- crop / mask
- outline / effect
- surrounding template chrome

新しい矩形画像を上から重ねて元フレームを偽装しない。

## 49.6 Image QA

Slide-level:

- IMAGE_ASSET_READY
- IMAGE_SOURCE_LINEAGE
- IMAGE_TREATMENT_APPLIED
- IMAGE_SLOT_ASPECT
- IMAGE_EFFECTIVE_RESOLUTION
- IMAGE_TEMPLATE_HARMONY
- IMAGE_NEGATIVE_SPACE
- IMAGE_FRAME_APPLICATION
- IMAGE_RENDERED_IN_TARGET_SLOT

Deck-level:

- DECK_IMAGE_METRIC_RANGE
- DECK_IMAGE_NEAR_DUPLICATE
- DECK_IMAGE_SHARED_SERIES_STYLE
- DECK_IMAGE_COHERENCE

同一ページ内のシリーズは構図や色調を共有してよい。ただし完全重複は警告する。別ページでのnear duplicateは、PPTがテンプレート的に見える原因として警告する。

## 49.7 State / 再実行

Image Recipeまたは選択画像が変更された場合、再実行範囲は原則以下とする。

```text
image       MODIFIED
render      STALE
qa          STALE
deck_harmony STALE
```

Primary Message、Deck Plan、Visual Plan、Source Match、無関係なページを変更しない。

## 49.8 Final Export

Image Recipeを持つページは、以下をすべて満たす場合のみExport可能とする。

- Recipeに実在するsource content object、またはLayout Engineが生成した確定済みprimary visual slotがある
- Recipeに`selected_asset_id`がある
- Recipeの選択と`render/generated_assets/manifest.json`の`selected_by_recipe`が一致する
- Manifest内に同一asset IDの実体があり、`processed_path`、source lineage、treatment情報を持つ
- image phaseが`APPROVED`または`LOCKED`
- `IMAGE_RENDERED_IN_TARGET_SLOT`を含むImage QAのBlockingが0
- providerがtest-only `mock`ではない

未解決Recipe、Manifest不整合、処理済み画像欠落、Mock画像を検出した場合はFinal Exportを拒否し、対象slide / recipe / assetをblockerとして返す。

## 49.9 UX

通常表示では以下を要約する。

```text
元PPTの写真枠：保持
画像：準備済み
色調：元PPTへ調整
画像調和：適正
```

必要時だけRecipe、候補ランキング、source lineage、crop・grading metrics、判断理由、過去versionを開示する。ユーザーはページ単位で、登録画像からの再選定、別候補の採用、Recipe prompt / focal point / negative-spaceの更新、OpenAI別案を実行できる。

## 49.10 OpenAI Images Provider

OpenAI画像生成は外部provider adapterとして扱い、次の環境変数を利用する。

```bash
OPENAI_API_KEY=...
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_QUALITY=medium
OPENAI_IMAGE_ENDPOINT=https://api.openai.com/v1/images/generations
```

APIから返された画像も直接完成扱いにせず、必ず同一のImage Treatment、Manifest、PowerPoint配置、actual-render QAを通す。認証情報がない場合やAPIが失敗した場合、Placeholderへ暗黙fallbackしてはならない。

## 49.11 Recipe変更と最小再実行

Recipe prompt、focal point、negative-space、選択候補の変更時は、現在の選択と`replace_image` mutationを解除し、次のみをSTALEにする。

```text
image          STALE
render         STALE
qa             STALE
deck_harmony   STALE
```

Deck Plan、Primary Message、Visual Plan、Source Match、無関係なslideは変更しない。LOCKED slideとの衝突時は自動解除せず、`STALE_LOCKED`相当としてユーザー確認へ送る。

# 50. Photo-aware Layout Engine v0.6

## 50.1 実行可能Layout Family

v0.6では、次のfamilyを決定論的Layout Engineで実行できる。

```text
grid
process
statement
two_column
photo_text
full_bleed
comparison_matrix
relationship
```

モデルは最終座標を直接出さない。モデルが選ぶのは、family、semantic content、density、fill policy、画像・文字の優先関係、継承元オブジェクトまでとする。

## 50.2 Photo-aware planning order

写真系ページは、画像を先に生成してから空いた場所へ置かない。

```text
Slide Plan / visual intent
  ↓
Layout Engineがprimary visual slotを計画
  ↓
slot bbox / aspect / text side / requested negative spaceをImage Recipeへ同期
  ↓
local / manual / OpenAI candidateを選定
  ↓
slot-aware crop / grading
  ↓
PowerPointへ配置
  ↓
actual-render QA
```

この順序により、画像の構図、文字用余白、レイアウト、元PPTのフレームを一つの判断系として扱う。

## 50.3 `photo_text`

- visualとtextを左右に分ける
- `text_side: auto`の場合、Image Recipeの`requested_negative_space`から文字側を解決する
- source Picture Shapeが利用可能なら、shapeを削除せずsemantic image slotへ移動・再利用する
- visualとtextは同程度の幅を基本とするが、visual priorityとdensityで比率を調整できる
- `PHOTO_TEXT_NEGATIVE_SPACE_DIRECTION`でRecipeと配置方向の一致を検査する

## 50.4 `full_bleed`

- exact presentation sizeを利用して全面visual slotを生成する
- rounded template profile値だけでslide sizeを推測しない
- visual assetが未選択ならcompose / Final Exportを拒否する
- full-bleed visualはtemplate chromeより背面へ配置する
- 必要なcopy panelはvisual上に生成できるが、元PPTのロゴ・罫線・ブランド装飾を覆わない
- `FULL_BLEED_COVERAGE`と`FULL_BLEED_BEHIND_TEMPLATE_CHROME`をBlocking QAとして実行する

## 50.5 Image Recipe synchronization

Layout Engineは`planning/image_recipes.json`へ次を同期する。

```yaml
target:
  layout_slot_id: primary_visual
  bbox: {x, y, w, h}
  aspect_ratio: 1.5
  requested_negative_space: right
  source_object_id: SRC-S004-O004  # 再利用できる場合
```

slot geometry、aspect、source object、negative-space intentが変化した場合、既存`selected_asset_id`をそのまま流用しない。Recipe selectionを無効化し、image / render / qa / deck_harmonyをSTALEにする。Deck Plan、Primary Message、Visual Plan、Source Match、無関係なページは維持する。

## 50.6 Source Picture reuse

source Picture Shapeが利用可能な場合は、画像relationshipだけでなくshape identityを継承する。

保持・追跡対象:

- shape id
- mask / crop
- outline / effect
- rotation
- z-order lineage
- source object id

Layout Engineは必要に応じてgeometryをsemantic slotへ移動するが、新しいPictureを上から重ねて元フレームを残したように偽装しない。

## 50.7 Editable structured families

### `two_column`

- native text box
- native divider
- source typographyを継承
- `open / card` variantを持つ
- `card`は原稿量に応じてpanel heightを決め、巨大な空panelで画面を埋めたように見せない
- 短い本文は巨大なbody boxへ引き延ばさず、推定行数とsource font scaleからcompact content clusterを作る
- card / openいずれも明示指定がなければclusterを光学的に中央配置する
- intentional whitespace / balanced / content_filledに対応

### `comparison_matrix`

- native PowerPoint table
- header、row labels、highlight columnを編集可能なセルとして生成
- `EDITABLE_LAYOUT_COMPARISON_MATRIX`でtable存在と編集可能性を検査

### `relationship`

- native PowerPoint shapes
- native connectors
- center node / peripheral nodesをsemantic構造から配置
- `EDITABLE_RELATIONSHIP_NODES`と`EDITABLE_RELATIONSHIP_CONNECTORS`で検査

## 50.8 Photo-aware QA

v0.6では次を追加する。

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

画像ファイルが存在するだけではPASSにしない。予定slotと実Picture geometry、source lineage、z-order、render結果まで検査する。

## 50.9 Image output resolution

処理画像の解像度は固定2048pxではなく、presentation上のslot寸法と目標effective PPIから算出する。

- 基準effective PPI: 約150
- 最長辺上限: 3328px
- full-bleedでも最低解像度QAを満たすこと
- 不必要に巨大な画像を生成せず、App Server上の処理時間とPPTX容量を抑える

## 50.10 Renderer process safety

LibreOffice / Poppler等の外部変換はbounded subprocessとして実行する。

- `start_new_session=true`
- timeout時にprocess group全体をkill
- orphan `oosplash / soffice.bin`を残さない
- LibreOfficeは独立user profileで最大2回まで限定retry
- PDF変換、text抽出、bbox抽出にもtimeoutを設定

外部processを放置してApp Serverの次turnを停止させない。

## 50.11 Golden Sample

`examples/photo-layout-poc/`で以下5ページを検証する。

```text
photo_text
full_bleed
two_column
comparison_matrix
relationship
```

合格条件:

- output actual-render Blocking 0 / Warning 0
- Deck QA Blocking 0 / Warning 0
- Deck Image Coherence Blocking 0 / Warning 0
- source Picture Shape再利用
- template chrome保持
- native table / relationship nodes / connectors

## 50.12 Pixel Diff performance

mutation mask外Pixel DiffはNumPy配列でベクトル化して計算する。全画素をPythonの二重ループで走査しない。NumPyが利用できない場合のみ互換用scalar fallbackを使う。これにより、複数ページのactual-render QAをApp Server内で連続実行しても、Pixel Diffが主要な待ち時間になりにくい構造とする。

## 50.13 ライブE2Eの実施順

実Codex App Server + Solおよび実OpenAI画像生成のライブE2Eは、ユーザー方針により最終統合工程でまとめて実施する。v0.6時点では、外部認証へ依存しない決定論的実装、fake App Server、local/manual image pipeline、actual-render Golden Sampleを先に通す。

adapterの実装済みと、ライブE2E成功済みを混同してはならない。

