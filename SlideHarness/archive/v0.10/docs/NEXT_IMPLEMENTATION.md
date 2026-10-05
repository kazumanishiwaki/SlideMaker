# 次の実装マイルストーン — v0.6以降

## 方針

実Codex App Server + Solおよび実OpenAI画像生成のライブE2Eは最後にまとめて行う。それまでは、認証・ネットワーク・モデル応答へ依存しない決定論的機能と回帰テストを優先する。

## Milestone 1 — 実テストケースの全ページ生成

今回のMIRI Company PPTとAha! レシート Lite原稿を使い、代表ページだけでなくメインデック全体を生成する。

- 原稿分類を正式Content Unitへ確定
- 8〜10ページ程度のDeck Plan
- 全ページのVisual Plan / Source Match / Slide Plan
- current 8 familyで成立するページをcompose
- unsupported pageは明示的に停止
- ページ単位QA
- Deck Harmony
- 途中で1ページを変更し、無関係ページが不変であることを確認

## Milestone 2 — Deterministic Layout Family拡張

優先順:

1. `timeline`
2. `kpi`
3. `chart`
4. `photo_grid`
5. `section / cover / closing`
6. `hierarchy / organization`

要件:

- PowerPointで編集可能
- 元PPTのComponent Catalogを使用
- 画像化で逃げない
- `LAYOUT_FIT_TO_INTENT`
- familyごとのactual-render QA

## Milestone 3 — Screenshot / document excerpt

- Web / application screenshotのcropとframe適応
- PDF / DOCXのページ・範囲lineage
- embedded textの解像度・可読性QA
- mockup frameを`container_or_frame`として再利用
- screenshotを写真と同じgradingで過度に加工しない

## Milestone 4 — Asset classification / semantic ranking

外部Visionを使う前に、deterministic seedを強化する。

- source slide render + object crop manifest
- embedded text有無
- portrait / screenshot / chart / diagram seed
- template chromeの反復位置・hash・z-order
- candidate imageの構図・余白・解像度ranking
- confidenceが低いものだけ`REVIEW_REQUIRED`

将来Visionを接続する場合も、Vision結果はSource of TruthではなくDecision候補として保存する。

## Milestone 5 — Safe feedback loop v0.2

```text
rewrite
→ region resize
→ layout variant
→ source rematch
→ split escalation
```

- 毎回`semantic_text`から再生成
- 短縮済み`render_text`を再入力にしない
- 意味変更の可能性があれば自動確定しない
- split / mergeは上位Gateへ提案
- retry上限と停止理由をDecision Traceへ保存
- mutation mask外Pixel Diffを維持
- 無関係なSlide Planを変更しない

## Milestone 6 — Typography / Deck Harmony

### 日本語組版

- 禁則処理
- 固有名詞辞書
- 数字・単位・記号の分離
- 行長・最終行バランス
- 英数字混在
- 括弧・句読点の光学調整

### Deck Harmony

- actual-render density
- whitespace rhythm
- title position rhythm
- accent color usage
- image temperature / detail sequence
- similar composition repetition
- 問題ページだけを改善候補として提示
- 全体を自動再生成しない

## Final Milestone — Live Codex / OpenAI E2E

決定論的実装が安定した最後に実施する。

1. 実Codex CLIでApp Serverへ接続
2. SolでGate C構成を精査
3. 代表ページPlanを生成
4. actual-render QA修正turn
5. 全ページPlan
6. 1ページLOCK後、無関係ページが不変であることを確認
7. OpenAI画像生成を1 Recipeだけ実行
8. lineage / crop / grading / Image QA / Final Exportまで完走
9. live結果とGolden Sampleを比較
10. Solから低コストモデルへ移せる低リスク処理をEval
