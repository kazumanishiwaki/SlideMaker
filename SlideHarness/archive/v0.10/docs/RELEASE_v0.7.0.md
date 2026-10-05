# Release v0.7.0

## 実装範囲

今回の対象は 1 / 3 / 4 / 5。

1. 新SlideHarness v2のリポジトリ構造を確定
3. Aha! レシート Lite 実デック全9ページを生成
4. 実例からLayout / QAを調整
5. 別PPT 3種類で汎用性スモーク検証

## 主要成果

- 旧版統合ではなく完全作り直し方針へ移行
- `apps/` / `packages/` 構造を追加
- Aha! レシート Lite 全9ページのGolden Sampleを追加
- 実レンダリングQA / Image Harmony / Deck Harmony: blocking 0
- 3テンプレートの解析・レンダリング・Design Fingerprint抽出スモークテストを追加

## 未実施

- 実Codex App Server + Sol ライブE2E
- OpenAI APIによる実画像生成
- UI本体の3画面実装
- packages配下への物理的なモジュール分割
