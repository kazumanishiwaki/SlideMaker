# SlideHarness Next — Codex App Server

`npm start` now launches the greenfield `nextgen` implementation at
`http://127.0.0.1:4318`. It uses the signed-in Codex App Server for deck
planning and the local Python core for deterministic PowerPoint generation and
QA. It does not require an API key.

The previous v0.10 UI remains available during migration through
`npm run start:legacy`.

## Legacy v0.10 documentation

既存PowerPoint、雑な原稿、`design.md`から、元PPTのデザイン文法を継承した編集可能なPowerPointを生成するCodex App Server / Skill向けコアです。

v0.10は機能追加版ではなく、判断フェーズ・中間データ・再試行回数を減らす整理版です。

## 次期仕様（Draft）

次期版は、現行コードの改修を前提にせず、「任意テンプレート対応の提案資料生成 + 画像生成」としてゼロベースで設計しています。

- [製品・品質仕様](docs/SPEC_v0.11.0.md)
- [Greenfield Architecture](docs/ARCHITECTURE_v0.11.0.md)
- [Greenfield MVP 実装](nextgen/README.md)

仕様はDraft、`nextgen/`はその最初の独立MVPです。以下に記載するv0.10の実装状態とは分離されています。

## 生成フロー

```text
1. Input Analysis
2. Deck Plan
3. Slide Plan
4. Compose
5. Validate
```

AIが通常作る計画は次の2つだけです。

- `planning/deck_plan.json`：ページ順と1ページ1メッセージ
- `planning/slide_plans.json`：全ページの表現・元PPT・文章・画像・レイアウト

`visual_plan.json` と `slide_matching.json` は、既存ランタイムとの互換性のためSlide Planから機械的に派生させます。独立したAI判断フェーズではありません。

## モデル呼び出し上限

```text
通常生成              2回
1ページの再提案       最大1回
```

1ページにつき無制限の自動修復ループは行いません。

## 内部Renderer

公開上のLayout Familyを次の5系統へ統合しています。

```text
statement  cover / section / statement / closing
grid       grid / two_column / comparison_matrix
media      photo_text / full_bleed / photo_grid / screenshot
flow       process / timeline / relationship / cause_effect / containment
data       kpi / chart / table
```

モデルは絶対座標を出しません。実座標は`engine/layout_engine.py`が決定します。

## QA

QAは次の3分類です。

- Technical：はみ出し、重なり、PPTX破損、画像比率、変更許可領域外Pixel Diff
- Content：数値・条件・Primary Message・制作メモ混入
- Design：文字サイズ、改行、画像・余白・レイアウト意図

Technical / ContentのBlockingは出力を停止します。Designは原則レビュー対象とし、同じページを何周も自動修正しません。

## Aha! レシートLite Golden Sample

```bash
python examples/aha-receipt-full-deck/build.py
```

主な出力：

- `examples/aha-receipt-full-deck/aha-receipt-lite-golden-v0.10.0.pptx`
- `examples/aha-receipt-full-deck/aha-receipt-lite-golden-v0.10.0-montage.png`
- `examples/aha-receipt-full-deck/slide-plans.json`
- `examples/aha-receipt-full-deck/output-qa.json`

タイトル改行は意味チャンクを優先します。

```text
必要な機能を標準化するから、
導入しやすい
```

## セットアップ

```bash
python -m pip install -r requirements.txt
npm install
```

## Quick tests

```bash
python -m unittest \
  tests.test_planning \
  tests.test_feedback \
  tests.test_state \
  tests.test_japanese_typography \
  tests.test_layout_engine \
  tests.test_validate_deck

node --test tests/app-server-client.test.mjs
```

レンダリングを伴うテストは負荷が高いため、CIでは分割実行を推奨します。

## 重要原則

- 出力PPTXはSource of Truthではない
- `source_text / semantic_text / render_text`を分離
- ユーザー指定の意味改行は固定
- 上流変更時は依存する下流だけSTALE
- LOCKEDページと無関係なページを変更しない
- `template_chrome`を保持し、本文画像だけを差し替える
- 空白を埋めるための文章・画像・装飾を追加しない

詳細は`docs/SIMPLIFICATION_v0.10.0.md`、`docs/RELEASE_v0.10.0.md`、`docs/VALIDATION_v0.10.0.md`を参照してください。
