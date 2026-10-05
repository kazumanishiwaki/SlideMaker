# Verification — v0.3.1

実施日: 2026-08-16

## 自動テスト

```text
Node App Server protocol: 1 / 1 PASS
Python unit/integration: 18 / 18 PASS
Representative PoC: PASS
  blocking: 0
  warning: 0
  deck harmony warning: 0
```

## Layout intent PoC

`examples/layout-intent-poc/layout-intent-poc.pptx`

### OUT-S001 — statement / intentional_whitespace

```text
fit-to-intent: PASS
score: 0.907
occupied_area_ratio: 0.301
content_extent_width_ratio: 0.680
content_extent_height_ratio: 0.480
accidental_dead_space: false
```

一つの主張と条件注記だけを表示し、空白を埋めるための写真・アイコン・説明文は追加していない。

### OUT-S002 — grid / content_filled

```text
fit-to-intent: PASS
score: 0.964
occupied_area_ratio: 0.825
content_extent_width_ratio: 1.000
content_extent_height_ratio: 0.941
rendered_item_count: 4 / 4
accidental_dead_space: false
```

4項目を2×2で配置し、3+1による説明不能な空白象限を回避している。

### Actual-render QA

```text
blocking: 0
warning: 0
```

## Failure guards

以下もテスト済み。

- `intentional_whitespace`でも小さすぎるcontent islandはFAIL
- 単一statementを`content_filled`へ強制すると`POLICY_SEMANTIC_MISMATCH`でFAIL
- 現行`grid / process / statement`で`full_bleed`を指定するとFAIL
- failed Layout Planはレビュー用に保存されるがFinal Exportはblocking
- 同一の実効fill policyを再composeしてもDecision Traceを重複追加しない
- 余白ページのPixel Diff許可領域は生成メッセージ群に限定され、意図的な空白自体は保護される
