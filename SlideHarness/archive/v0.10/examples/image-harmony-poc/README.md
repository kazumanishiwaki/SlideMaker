# Image Harmony Pipeline PoC

元PPT 8ページの4つの写真Shape・枠・罫線・ロゴを保持し、登録画像を各スロットの意味・比率・余白方向に合わせて自動選定し、デック共通の色調へ整える決定論的PoCです。

```bash
npm run demo:image-harmony
```

## 処理

1. 元PPTのcontent visualから4つのImage Recipeを作成
2. 各Recipeに用途、意味ラベル、target slot、余白方向を付与
3. `inputs/assets/` の候補を意味・比率・解像度・調和度でranking
4. `provider=auto` が登録候補を優先して自動選定
5. target slot比率、focal point、negative spaceを考慮してcrop
6. 元PPTとDeck Art Directionに合わせ、明度・彩度・コントラスト・色温度・detailを共通補正
7. 元のPowerPoint Picture relationshipだけをin-place交換し、Shape ID・位置・枠・効果・回転・z-orderを保持
8. Image Harmony、Deck Image Coherence、actual-render、Pixel Diffを実行

## 比較用成果物

- `source-page-8.png` — 差し替え前の元PPT 8ページ
- `image-harmony-poc.png` — 差し替え・文章適応後の実レンダリング
- `source-reference-*.png` — 元PPTの各写真スロットの参照画像
- `image-candidate-*.jpg` — 登録候補画像
- `processed-image-*.png` — crop・grading後に実際に配置した画像

## 設計・判断データ

- `image-recipes.json` — スロットごとの意味、比率、焦点、余白方向、選定結果
- `image-asset-manifest.json` — 候補・生成・加工画像の系譜とバージョン
- `deck-art-direction.json` — デック全体の画像トーン
- `design-fingerprint.json` — 元PPTから抽出した画像処理・色・構造の基準

## QA

- `image-harmony-qa.json` — スロット単位の画像調和検査
- `deck-image-coherence.json` — デック全体の画像トーン・重複検査
- `output-qa.json` — 実レンダリング、Pixel Diff、PPT構造を含む最終検査
- `summary.json` — PoC結果の要約

## 期待値

```text
selection provider          auto -> local
prepared assets             4
image harmony               blocking 0 / warning 0
deck image coherence        warning 0
output QA                   blocking 0 / warning 0
```

候補画像はPillowで生成した、文字を含まない技術検証用ビジュアルです。画像生成APIの意味品質を検証するものではありません。本番の`auto`は、支給・アップロード画像を優先し、利用可能な候補がなくOpenAI画像生成が設定されている場合にAPIへ進みます。どちらも利用できない場合は、ダミー画像へ自動フォールバックせず`REVIEW_REQUIRED`で停止します。
