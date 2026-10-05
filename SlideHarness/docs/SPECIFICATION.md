# SlideHarness システム仕様書

## 文書情報

| 項目 | 内容 |
|---|---|
| 対象 | `nextgen/` の現行実装 |
| 基準日 | 2026年9月1日 |
| App Serverスキーマ | `0.4.0-app-server.1` |
| ラン設定スキーマ | `0.4.0` |
| Pythonパッケージ表記 | `0.3.0` |
| 既存英語仕様の表記 | v0.11 |

バージョン表記は現行ファイル間で一致していない。

この仕様書では表記を統合せず、各実装が現在出力する値をそのまま記載する。

## 実装範囲

現行コードは次の仕様を実装する。

1. スキャンPDFのローカルOCR。
2. 棒グラフ以外のPowerPointネイティブグラフ。
3. 画像要求から画像生成、登録、生成再開までの自動化。
4. 決定論的処理の優先、内容アドレスキャッシュ、差分コンテキスト、共通出力プロファイル。

ラン管理、クラウド公開、外部認証など、上記以外の機能は後回しとする。

## 生成AIの利用境界

この仕様書における**生成AI**は、サインイン済みCodex App Serverを経由する構成、文章再編集、および組み込み画像生成を指す。

ローカルOCR、構文解析、正規表現、数値処理、テンプレート解析、PowerPoint生成、レンダー、QAは生成AIを使わない処理として扱う。

生成AIを呼ぶかどうかは、処理の種類と信頼度に基づいて決める。

| 工程 | 既定の処理 | 生成AIを使う条件 |
|---|---|---|
| PDF文字取得 | ネイティブ抽出、画像前処理、ローカルOCR | OCR結果を生成AIで無断補正しない |
| 出典単位と事実抽出 | 構文規則、表解析、数値と条件の抽出 | 意味の曖昧さを解決する必要があり、出典を限定できる場合 |
| テンプレート解析 | OOXMLと図形の統計解析 | 使用しない |
| スライドレシピ選択 | データ型、件数、テンプレート証拠に基づく規則 | 複数レシピが同程度で、資料の目的に関する判断が必要な場合 |
| ネイティブグラフ選択 | 時系列、構成比、相関、カテゴリ比較の規則 | データ構造だけでは伝達意図を確定できない場合 |
| デッキ構成 | 決定論的な代替構成とキャッシュ | 新規の物語構成、要約、優先順位付けが必要な場合 |
| 画像生成 | 使用しない | 画像要求があり、ネイティブ構造では目的を満たさない場合 |
| PPTX合成とQA | ローカルの決定論的処理 | 使用しない |
| 1ページ再生成 | 既存プランの差分と対象出典の抽出 | 修正指示に文章や構成の再判断が含まれる場合 |

生成AIを使用しない経路も、生成AIを使用する経路と同じ内容、構造、パッケージ、出典、レンダー、視覚QAを通過しなければならない。

高速化とトークン削減を理由にQAを省略しない。

## システム構成

```text
ブラウザ
  │ HTTP / Server-Sent Events
  ▼
Node.js App Server
  ├─ ラン状態とファイルの管理
  ├─ サインイン済みCodex App Serverとの接続
  │    ├─ デッキ構成と1ページ再生成
  │    └─ 組み込み画像生成と完了項目の受信
  └─ Python CLIの起動
       ├─ 原稿取り込み
       ├─ テンプレート解析
       ├─ 構成検証とスライド計画
       ├─ PPTX合成
       ├─ 1ページ差替え
       └─ 各種QAとレンダー
```

| 構成要素 | 実装場所 | 責務 |
|---|---|---|
| App Server | `nextgen/app-server.mjs` | HTTP、SSE、Codex連携、ラン制御、再生成制御 |
| Codexクライアント | `nextgen/app/codex-app-server-client.mjs` | App Serverの起動、能力確認、ターン、通知、画像生成完了項目の受信 |
| 画像生成アダプター | `nextgen/app/image-generator.mjs` | 画像要求の正規化、Codex画像生成ターン、`savedPath`取込、検証、キャッシュ |
| ランストア | `nextgen/app/run-store.mjs` | 状態、入力、設定、画像マニフェストの保存 |
| Pythonブリッジ | `nextgen/app/python-core.mjs` | Python CLIの起動、進行通知、結果読込 |
| ブラウザUI | `nextgen/public/` | 入力、設定、進行表示、画像登録、ダウンロード、ページ再生成 |
| Pythonコア | `nextgen/slideharness_next/` | 解析、計画、合成、出典、差替え、QA |
| Planner Skill | `nextgen/skill/SKILL.md` | Codexが構成ファイルを作成するときの制約 |

## 起動仕様

### App Server

```bash
npm start
```

- 既定の待受アドレスは `127.0.0.1` である。
- 既定のポートは `4318` である。
- `NEXTGEN_PORT` でポートを変更できる。
- `NEXTGEN_WORKSPACE` でラン保存先を変更できる。
- `CODEX_BIN` でCodex実行ファイルを変更できる。
- `NEXTGEN_CODEX_MODEL` でCodex画像生成ターンの既定モデルを変更できる。
- `NEXTGEN_IMAGE_EFFORT` で画像生成ターンの推論量を変更できる。既定は `low` である。
- `NEXTGEN_CACHE` で構成、OCR、生成画像キャッシュの保存先を変更できる。
- `NEXTGEN_PYTHON` でPython実行ファイルを変更できる。

### 環境確認

```bash
npm run check:next-app
```

環境確認はPythonから `pptx`、`PIL`、`docx`、`pypdf` をインポートできるかを検査する。

LibreOfficeとPoppler系コマンドの有無は生成時のレンダーQAで判定する。

## 入力仕様

| 役割 | 拡張子 | 件数 | 1ファイル上限 | 保存先 |
|---|---|---:|---:|---|
| テンプレート | `.pptx`、`.potx` | 1 | 50MB | `inputs/template.<ext>` |
| 原稿 | `.md`、`.txt`、`.docx`、`.pdf`、`.pptx` | 1以上 | 25MB | `inputs/sources/` |
| デザイン指示書 | `.md`、`.txt`、`.docx`、`.pdf`、`.pptx` | 0または1 | 25MB | `inputs/design-guide.<ext>` |
| 生成画像と外部画像 | `.png`、`.jpg`、`.jpeg`、`.webp` | 0以上 | 25MB | `inputs/assets/` |

ファイル名はUnicode NFKCで正規化し、ディレクトリ成分を除去する。

ファイル名に使用できない文字はハイフンへ置換する。

同じ保存先への上書きは行わない。

### スキャンPDFのOCR

PDFは最初に既存のテキスト抽出を実行する。

ページ内の抽出文字数が設定値を下回る場合だけOCRを実行する。

既定値は24文字であり、CLIから変更できる。

OCR前処理は、指定DPIでのページ画像化、Exif回転の反映、グレースケール化、オートコントラストをローカルで実行する。

OCRエンジンは交換可能な `OCRBackend` とし、特定ベンダーを原稿取り込み処理へ直接結合しない。

OCR結果はページ単位で次の情報を保存する。

| 項目 | 内容 |
|---|---|
| `page_number` | 元PDFの1始まりページ番号 |
| `text` | 読取文字列 |
| `blocks` | 行ごとの文字列と座標 |
| `confidence` | エンジンが返す信頼度と集計値 |
| `language` | 使用した認識言語 |
| `preprocessing` | 適用した画像前処理 |
| `source_sha256` | 元PDFのハッシュ |
| `page_image_sha256` | OCR対象ページ画像のハッシュ |
| `backend` | OCRエンジンとバージョン |

元PDFは変更しない。

OCR結果から作る `SourceUnit` は、`metadata` に `extraction: "ocr"`、元ページ、座標、信頼度を保持する。

低信頼度の文字列は生成AIで自動補正せず、`review` または `blocking` として利用者へ提示する。

同じページ画像、前処理、言語、OCRエンジンバージョンの組合せはキャッシュを再利用する。

### 生成設定

| 設定 | 値 | 既定値 |
|---|---|---|
| `composition_mode` | `auto`、`reconstruct`、`source-slides` | `auto` |
| `information_density` | `low`、`medium`、`high` | `medium` |
| `decorativeness` | `low`、`medium`、`high` | `medium` |
| `structured_visual_mode` | `auto`、`native`、`generated-image` | `native` |
| `allow_shadows` | `true`、`false` | `false` |

案件名は120文字まで保存する。

追加指示は20,000文字まで保存する。

ページ再生成のフィードバックは12,000文字まで保存する。

## ランディレクトリ

```text
workspace/run-<uuid>/
  state.json
  run_config.json
  usage.json
  PLAN_TASK.md
  inputs/
    template.<ext>
    sources/
    design-guide.<ext>
    assets/
    asset_manifest.json
  prepared/
  plan/
    deck_spec.json
  output/
  regeneration/
  versions/
```

`state.json` はランの進行状態、設定、ファイル記録、Codexのスレッド情報、成果物、エラー、リビジョンを保持する。

状態更新は一時JSONを書いた後にリネームして確定する。

## 状態遷移

```text
created
  → uploading
  → preparing
  → prepared
  → planning
  → plan_ready
  → building
  ├→ awaiting_images → building
  ├→ completed
  └→ failed

completed
  → regenerating
  ├→ regeneration_awaiting_images → completed
  ├→ completed
  └→ completed（再生成失敗、直前成果物を維持）
```

| 状態 | stage | 意味 |
|---|---|---|
| `created` | `upload` | ランを作成した |
| `uploading` | `upload` | 入力を登録中である |
| `preparing` | `prepare` | 原稿とテンプレートを解析中である |
| `prepared` | `codex_planning` | 構成に必要な証拠を作成した |
| `planning` | `codex_planning` | Codexが初期構成を作成中である |
| `plan_ready` | `compose_and_qa` | 初期構成が完成し、生成へ移る |
| `building` | `compose_and_qa` | PPTX生成とQAを実行中である |
| `awaiting_images` | `image_resolution` | 初期生成に必要な画像を待っている |
| `completed` | `completed` | 必須QAに合格した成果物がある |
| `failed` | 直前のstage | 初期生成または準備に失敗した |
| `regenerating` | `codex_regeneration` | Codexが対象ページの再構成案を作成中である |
| `regeneration_awaiting_images` | `image_resolution` | ページ再生成に必要な画像を待っている |

画像生成の自動実行を追加した後は、`generating_images` を画像生成中の状態として追加する。

自動生成が成功した場合は同じランを `building` または `regenerating` から再開し、失敗した場合は既存の画像待ち状態へ移す。

## 生成処理

### 原稿取り込み

原稿ごとにSHA-256を計算し、`SourceFile` を作成する。

本文は `SourceUnit` へ分割し、次の情報を保持する。

| 項目 | 内容 |
|---|---|
| `unit_id` | 出典単位の安定ID |
| `source_id` | 元ファイルID |
| `order` | ファイル内の順序 |
| `kind` | 見出し、本文、表などの種類 |
| `section_path` | 文書内の階層 |
| `source_text` | 変更しない原文 |
| `semantic_text` | 構成処理向けの正規化文 |
| `classification` | 単位の分類 |
| `facts` | 抽出した数値、日付、条件 |
| `required` | 必須採用対象かどうか |

PDFはテキスト抽出を前提とし、画像OCRは行わない。

### テンプレート解析

テンプレートから次の情報を抽出する。

- スライドの幅、高さ、枚数。
- テーマ色と主要フォント。
- レイアウト別の図形数、プレースホルダー数、タイトル枠数、本文枠数。
- 複数ページに反復する端部装飾と背景要素。
- ネイティブ表、グラフ、数値アンカー、グリッド構成などのパターン証拠。
- 完成スライド偏重リスクと推奨合成モード。

### 合成モード

#### `reconstruct`

テーマ、反復装飾、レイアウト証拠を使い、新しいスライドへPowerPoint要素を配置する。

#### `source-slides`

レシピごとに参照元スライドを選び、スライドXMLと関連を複製して意味のあるテキスト枠を置換する。

写真らしい高エントロピー画像は置換対象とし、低エントロピーの装飾画像とベクター風要素は保持する。

未使用の構造プレースホルダーとダミーテキストは削除またはクリアする。

#### `auto`

テンプレートが完成スライド偏重かつリスク `high` の場合に `source-slides` を選び、それ以外は `reconstruct` を選ぶ。

## 構成ファイル仕様

### `deck_spec.json`

```json
{
  "title": "資料タイトル",
  "metadata": {
    "planner": "codex_app_server",
    "information_density": "medium",
    "decorativeness": "medium",
    "structured_visual_mode": "native",
    "slide_policies": {}
  },
  "slides": [
    {
      "slide_id": "S001",
      "title": "ページタイトル",
      "message": "このページの結論",
      "recipe": "title_body",
      "source_unit_ids": ["U-01-0001"],
      "content": {
        "bullets": ["項目"]
      }
    }
  ]
}
```

最低1ページを必要とする。

各ページは `slide_id`、`title`、`message`、`recipe`、`source_unit_ids`、`content` を持つ。

初期構成では全必須出典単位を採用し、原稿にない事実を追加しない。

### レシピ別制約

| Recipe | 必須または上限制約 |
|---|---|
| `card_grid_2x2` | `cards` を3件から4件持つ |
| `two_column_equal` | `columns` を2件持つ |
| `three_column` | `columns` を3件持つ |
| `process` | `steps` を2件から5件持つ |
| `table` | 空でない `columns` と `rows` を持つ |
| `native_bar_chart` | 1件以上のカテゴリと系列を持ち、各系列の値数がカテゴリ数と一致する |
| `generated_visual` | `visual.type` が `chart` または `flow` で、具体的な `prompt` を持つ |

全レシピの一覧と用途は [機能一覧](FUNCTIONS.md) に記載する。

## 構造図の表現仕様

### `native`

- 棒グラフはPowerPointグラフとして生成する。
- フローは個別の図形、テキスト、接続線として生成する。
- 表は常にPowerPoint表として生成する。
- `generated_visual` を使用したページは構造QAで失敗する。

### `generated-image`

- グラフまたはフローを `generated_visual` として構成する。
- 対象ページ専用の画像要求を1件作成する。
- タイトルとメッセージに編集可能な結論を残す。
- プロンプトに必要なラベル、値、関係、読み順、デザイン制約を含める。
- `native_bar_chart` または `process` を使用したページは構造QAで失敗する。

### `auto`

正確な数値表示と後編集が優先される場合はネイティブ構造を選ぶ。

生成画像が理解を改善すると構成段階で判断した場合だけ `generated_visual` を許可する。

ページ別の `metadata.slide_policies[slide_id].structured_visual_mode` は全体設定より優先する。

### ネイティブグラフ

現行の `native_bar_chart` は互換性のため維持する。

グラフは `native_chart` レシピへ集約し、`content.chart.chart_type` で種類を指定する。

初期対応範囲は次のとおりとする。

| `chart_type` | PowerPoint表現 | 選択条件 |
|---|---|---|
| `bar` | 集合横棒 | 項目名が長いカテゴリ間の量を比較する |
| `column` | 集合縦棒 | 少数カテゴリ間の量を比較する |
| `stacked-bar` | 積み上げ横棒 | カテゴリごとの合計と内訳を比較する |
| `stacked-column` | 積み上げ縦棒 | 時点またはカテゴリごとの合計と内訳を比較する |
| `line` | マーカー付き折れ線 | 順序のある時系列の変化を示す |
| `area` | 面グラフ | 時系列の量と累積傾向を示す |
| `pie` | 円グラフ | 一系列の少数カテゴリによる構成比を示す |
| `doughnut` | ドーナツグラフ | 一系列の少数カテゴリによる構成比と中央注記を示す |
| `scatter` | 散布図 | 数値型の2変数の関係と分布を示す |

グラフ種類の自動選択は、データ型、系列数、カテゴリ数、時間軸、構成比、欠損値の有無から決定論的に行う。

規則で一意に選べない場合だけ、用途を限定した選択要求をCodexへ渡す。

すべてのネイティブグラフは次の共通プロファイルを使用する。

- テンプレート由来の色とフォント。
- タイトル、軸、凡例、データラベルの表示規則。
- 単位、小数、桁区切り、割合の数値書式。
- 系列数と背景色に応じたコントラスト。
- 元データ、出典単位、選択規則を記録するグラフメタデータ。

グラフQAは、PowerPointグラフとしての編集可能性、カテゴリと系列の長さ、軸参照、キャッシュ値、表示ラベル、数値書式、出典を検査する。

円とドーナツは、値が非負、一系列、構成比として解釈できる場合だけ自動選択する。

散布図はX値とY値がともに数値で、同じ件数を持つ場合だけ自動選択する。

## 画像要求

画像を必要とするレシピは `asset_requests.json` を出力する。

| 項目 | 内容 |
|---|---|
| `asset_id` | 構成内で安定した画像要求ID |
| `slide_id` | 所有ページID |
| `kind` | `generated_image` |
| `prompt` | 生成または選定の指示 |
| `aspect_ratio` | `3:2` または `16:9` |
| `required_text` | 構造図に正確に含めるラベルと値 |
| `resolved_path` | 解決済み画像パス |
| `source_url`、`source_urls` | 外部画像の正確な出典URL |
| `source_note` | 出典に関する補足 |

同じ解決済み画像パスは初期状態で一つの `asset_id` にだけ割り当てる。

再利用が必要な場合、要求単位で `allow_reuse: true` を指定する。

未解決要求が残る場合、ランは `awaiting_images` または `regeneration_awaiting_images` へ移る。

### 画像生成の自動実行

`asset_requests.json` に未解決の生成画像要求がある場合、Node.js App Serverは、資料構成と同じサインイン済みCodex App Serverへ画像生成ターンを開始する。

画像生成アダプターは、プロンプト、アスペクト比、用途、対象ページ、`asset_id` を受け取り、組み込み `image_gen` を使う `imagegen` Skill入力へ正規化する。

画像生成の前に `modelProvider/capabilities/read` を呼び出し、`imageGeneration: true` を確認する。

画像生成は入力干渉と履歴トークンの増加を避けるため、要求ごとに独立したCodexスレッドで実行する。

画像生成ターンは `effort: low`、`approvalPolicy: never` を既定とし、APIキー、外部CLI、シェルコピーを使用しない。

App Serverは `item/completed` の `imageGeneration` 項目を待ち、`savedPath` の画像を検証後にランのアセット領域へコピーする。

生成直後に、生成とは独立した画像入力付きCodexターンで、要求適合、構図、視覚的整合性、スライド利用性、破綻の少なさを各5段階で審査する。

全項目4以上かつ `blocking_issues` が空の場合だけ自動採用する。不合格の場合は `improvement_instruction` を元の要求へ追加し、元の要件を変えずに1回だけ再生成する。

画像と要求ハッシュのほかに品質審査PASSのサイドカーJSONが一致する場合だけキャッシュを再利用する。旧キャッシュや審査記録のない画像は再利用しない。

画像生成の具体的なモデルや接続方法をPPTXコアへ直接結合しない。

自動処理は次の順序で実行する。

1. 未解決要求の入力契約を検証する。
2. 同じ要求ハッシュの画像キャッシュを検索する。
3. キャッシュがなければCodex App Serverの画像生成能力を確認する。
4. 独立スレッドで `imagegen` Skill付きターンを開始する。
5. `item/completed` と `turn/completed` を待ち、`imageGeneration.savedPath` を読み込む。
6. 画像入力付きCodexターンで5項目を評価する。
7. 不合格の場合は具体的な修正指示を付け、既定で1回だけ再生成する。
8. 合格画像と品質審査JSONを内容アドレスキャッシュへ保存する。
9. 合格画像をランの `inputs/assets/` へ保存する。
10. `asset_id` を維持してアセットマニフェストへ登録する。
11. ローカル画像QAを実行する。
12. QAに合格した場合、待機中の初期生成またはページ再生成を再開する。
13. 能力不足、利用上限、タイムアウト、生成失敗、再生成後の審査不合格、ローカルQA不合格の場合、理由を記録して既存の手動アップロード待ちへ移る。

装飾画像のローカルQAは、ファイル形式、1024×576以上の寸法、破損、アスペクト比、エントロピー、輝度分散、極端な単色を検査する。要求した主題との適合と構図は前段の画像入力付きCodex審査で検査する。

グラフやフロー図を画像生成する場合は、`required_text` を必須とし、OCRで要求されたラベルと値が画像内に存在することを検査する。

関係と読み順は `review_packet.json` の人による確認項目に残す。

構造図の事実検証に失敗した画像は完成成果物へ採用しない。

生成メタデータには `asset_id`、要求ハッシュ、プロバイダー名、モデル、試行回数、5項目の得点、品質審査ファイル、キャッシュヒットを記録する。

認証情報、一時的な署名URL、Codex管理領域の一時保存パスは生成メタデータへ保存しない。

## 1ページ再生成

### 要求

```json
{
  "slideId": "S005",
  "expectedRevision": 1,
  "feedback": "結論を先に示す",
  "informationDensity": "medium",
  "decorativeness": "high",
  "structuredVisualMode": "generated-image"
}
```

完成済みランだけが要求を受け付ける。

同じランで再生成が進行中の場合、新しい要求を拒否する。

`expectedRevision` が現行リビジョンと一致しない場合、競合として拒否する。

### Codex出力

Codexは `regeneration/proposed_slide.json` に対象ページのオブジェクトを一つだけ出力する。

対象ページの `slide_id` は変更できない。

Codexは `inputs/`、`prepared/`、現行 `plan/deck_spec.json`、`output/`、`state.json` を変更しない。

### 適用処理

1. 現行プランへ提案ページをメモリ上で差し込み、候補プランを作る。
2. 一時ワークスペースへ候補PPTXを生成する。
3. 候補の全必須QAが合格したことを確認する。
4. 対象ページと対象専用の依存関係閉包だけを現行PPTXへ移す。
5. 対象外ページのフィンガープリントを比較する。
6. 元テンプレートと原稿を使って差替え後PPTXを再検証する。
7. 現行版を `versions/rev-NNNN/` へ保存する。
8. 新しい出力とプランを確定し、リビジョンを1増やす。

対象ページから到達できなくなった専用メディア、グラフ、ノート、関連パーツは削除する。

削除したパーツのコンテンツタイプ登録も同期して削除する。

共有依存物の変更、対象外フィンガープリントの不一致、最終QAの失敗がある場合は適用しない。

## 高速化とトークン節約

### 内容アドレスキャッシュ

共有キャッシュは既定で `~/.cache/slideharness-next/` を使用し、`NEXTGEN_CACHE` で保存先を変更できる。

キャッシュキーは、入力バイト列のSHA-256、設定、処理契約バージョン、使用ライブラリまたはエンジンバージョンから作る。

| キャッシュ対象 | 再利用条件 |
|---|---|
| OCR | ページ画像、前処理、言語、OCRエンジンバージョンが一致する |
| 生成画像 | プロンプト、用途、図種、縦横比、必須文字列、生成プロバイダーが一致する。再利用時も生成画像QAを実行する |
| 構成プラン | 出典単位、内容モデル、必須条件、テンプレート解析、ラン設定、Planner Skillが一致し、保存元の最終QAがPASSである |

不正な構成キャッシュは無効化し、Codexによる構成へ戻す。

### Codexコンテキストの削減

初期構成では、原稿ファイルそのものではなく、ローカルで作成した出典単位、必須事実、条件、章構造、テンプレート証拠を渡す。

資料の目的と構成判断に関係しない埋め込み画像、重複本文、パッケージXMLは渡さない。

ページ再生成では、対象ページ、対象ページが参照する出典単位、修正指示、変更可能な設定だけを `regeneration/context.json` へ保存して渡す。

Codex出力は自由記述ではなく、固定JSONスキーマへ限定する。

### 利用量の記録

各ランは `usage.json` を出力する。

| 項目 | 内容 |
|---|---|
| `stage` | 初期構成、ページ再生成、画像生成などの工程 |
| `reason` | 生成AIを呼び出した理由 |
| `model` | 使用モデル |
| `input_tokens` | ホストが返した場合の入力トークン数。未提供時は `null` |
| `output_tokens` | ホストが返した場合の出力トークン数。未提供時は `null` |
| `cache_hit` | ローカルまたはホストキャッシュの利用有無 |
| `duration_ms` | 工程の処理時間 |

数値目標は代表コーパスの現行値を測定してから決める。

処理時間またはトークンが減っても、共通QAの合格率、編集性、出典完全性、目視品質が下がる変更は採用しない。

## 出力の標準化

AI経路と非AI経路は次の契約を共有する。

契約は `output_profile.json` へ出力し、`qa-output-contract.json` でページID、レシピ、レイアウト計画、要素名を検査する。

- `deck_spec.json` とレシピ別コンテンツスキーマ。
- 連番の `slide_id` と意味役割を表す図形名。
- テンプレート由来の色、フォント、余白、数値書式。
- `[Sources]` ノートと外部画像の出典形式。
- `asset_id` の所有ページと一回利用の原則。
- QAファイル名、所見カテゴリ、`blocking` と `review` の区分。
- 完成、画像待ち、失敗、ページ再生成の状態遷移。

決定論的処理で同じ入力、設定、処理バージョンを使った場合、構成JSONと生成要素の命名を安定させる。

画像生成の画素差、レンダーエンジンの差など、完全なバイト一致を保証できない成果物は、構造と品質指標の一致で判定する。

## 出典仕様

原稿に基づく各ページのスピーカーノートへ `[Sources]` ブロックを付与する。

ノートには使用した出典単位IDを記録する。

採用した原稿単位にURLが含まれる場合は、そのURLを正確に保持する。

外部画像を利用する場合は `asset_id` と出典URLを記録する。

ローカル絶対パスは最終ノートに記録しない。

## QA仕様

OCR、ネイティブグラフ、生成画像、共通出力契約は個別のQA成果物を持つ。

| ファイル | 検査対象 | 合格条件の概要 |
|---|---|---|
| `qa-content.json` | 出典単位、必須事実、未裏付け事実 | 必須欠落と未裏付け事実がない |
| `qa-structural.json` | 境界、密度、空白、フォント、影、未解決画像、構造図方式 | ブロッキング所見がない |
| `qa-package.json` | ZIP、XML、関連、コンテンツタイプ、グラフ、テーマ、孤立パーツ | 出力起因の破損と回帰がない |
| `qa-provenance.json` | `[Sources]`、出典ID、URL、外部画像 | 必要な出典記録がすべてある |
| `qa-template-fidelity.json` | 元スライドの構成要素と装飾 | `source-slides` 使用時に必要要素を保持する |
| `qa-render.json` | LibreOffice PDF変換、PNG化、空レンダー | レンダーが実行され、全ページを画像化できる |
| `qa-visual.json` | 衝突、空白、テキスト欠落、タイトル折返し、文字サイズ、フォント証拠 | ブロッキング所見がない |
| `qa-page-isolation.json` | 再生成対象、依存差分、対象外ページの前後フィンガープリント | 対象外ページがすべて不変である |
| `review_packet.json` | 人による確認項目 | 自動承認せず、レビュー待ちとして記録する |
| `summary.json` | 全体結果 | 必須QAがPASSで、未解決画像がない |
| `qa-ocr.json` | OCR対象ページ、信頼度、文字量、表候補、レビュー対象 | 低信頼度の未確認文字列が採用されていない |
| `qa-native-chart.json` | グラフ種類、元データ、系列、軸、ラベル、数値書式、編集性 | データと表示の対応が正しく、PowerPointグラフとして編集できる |
| `qa-generated-image.json` | 生成要求、画像品質、必須ラベル、値 | 必須文字列がOCRで確認でき、形式、寸法、単色状態に不合格がない |
| `qa-output-contract.json` | ページID、レシピ、レイアウト計画、要素名 | AI経路と非AI経路が共通出力プロファイルに従う |

レンダーが `SKIP` の場合、最終生成は失敗する。

CLIで `--allow-render-skip` を明示した草稿だけは例外とし、`render_policy: skip_allowed` を記録する。

`review` 所見は人が確認すべき注意点であり、自動的な失敗とは限らない。

## HTTP API

すべてのAPIレスポンスはJSONを基本とし、キャッシュを禁止する。

| Method | Path | 用途 | 主な成功コード |
|---|---|---|---:|
| GET | `/api/health` | App ServerとCodex接続準備の確認 | 200 |
| GET | `/api/events` | Server-Sent Eventsの購読 | 200 |
| POST | `/api/codex/connect` | Codex起動、アカウント、モデル一覧、画像生成能力の取得 | 200 |
| GET | `/api/runs` | ラン一覧の取得 | 200 |
| POST | `/api/runs` | ラン作成 | 201 |
| GET | `/api/runs/{runId}` | ラン状態の取得 | 200 |
| PUT | `/api/runs/{runId}/files/template` | テンプレート登録 | 201 |
| PUT | `/api/runs/{runId}/files/source` | 原稿登録 | 201 |
| PUT | `/api/runs/{runId}/files/design-guide` | デザイン指示書登録 | 201 |
| POST | `/api/runs/{runId}/prepare` | 原稿とテンプレートの解析 | 200 |
| POST | `/api/runs/{runId}/plan` | Codexによる構成開始 | 202 |
| POST | `/api/runs/{runId}/build` | 既存プランからPPTX生成 | 200または422 |
| GET | `/api/runs/{runId}/slides` | ページ一覧とページ別方針の取得 | 200 |
| POST | `/api/runs/{runId}/regenerate` | 1ページ再生成の開始 | 202 |
| PUT | `/api/runs/{runId}/assets/{assetId}` | 画像要求に対応する画像の登録と再開 | 201 |
| GET | `/api/runs/{runId}/file?path=output/...` | 成果物の取得 | 200 |
| POST | `/api/approvals/{requestId}` | Codex承認要求への回答 | 200 |

存在しないAPIは404を返す。

存在しないパス以外の入力エラーと状態エラーは400を返す。

## CLI

| コマンド | 用途 |
|---|---|
| `compile-template` | PPTXを解析してテンプレートシステムを出力する |
| `ingest` | 原稿を取り込み、出典単位を出力する |
| `plan-source` | 原稿を取り込み、指定プランを検証するか代替構成を作る |
| `build` | テンプレートと既存構成から生成とQAを実行する |
| `build-source` | 原稿取り込み、構成、生成、QAを連続実行する |
| `isolate-slide` | 候補PPTXの1ページを基底PPTXへ隔離差替えする |
| `verify-existing` | 既存PPTXへ最終QAを実行する |

Python CLIは正常終了で終了コード0、QA不合格で終了コード2、実行エラーで終了コード1を返す。

## エラー処理

- 初期生成の失敗はランを `failed` にし、エラーを `state.json` へ記録する。
- 画像不足は失敗にせず、画像待ち状態として画像要求を提示する。
- ページ再生成の失敗はラン全体を `failed` にせず、直前の完成状態へ戻す。
- Codexターンが正常完了しなかった場合は生成または再生成を適用しない。
- Pythonコマンドは既定で180秒を超えると終了要求を送り、タイムアウトとして扱う。
- 出力ディレクトリ切替中に失敗した場合は直前の出力を復元する。

## セキュリティ仕様

- サーバーはループバックアドレスにだけバインドする。
- プロバイダーAPIキーを受け付けない。
- ランIDは `run-` とUUID形式の組合せだけを許可する。
- ラン内パスは解決後にルート配下であることを検証する。
- HTTP経由のダウンロードは `output/` 配下に限定する。
- アップロードは役割別の拡張子とサイズ上限を検証する。
- Codexが操作承認を要求した場合は、利用者が明示的に許可または拒否する。

## 検証コマンド

```bash
npm run check:next-app
npm test
```

構成契約を変更した場合は、Planner Skillの検証も実行する。

成果物を完成扱いにするには、内容、OCR、構造、ネイティブグラフ、生成画像、共通出力契約、PPTXパッケージ、出典、レンダー、視覚、テンプレート忠実度、該当する場合はページ隔離のQAを通過させる。
