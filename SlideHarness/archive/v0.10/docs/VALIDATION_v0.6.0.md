# Validation Report v0.6.0

**Date:** 2026-08-17  
**Scope:** deterministic/local implementation before live Codex/OpenAI E2E

## Environment validation

- Python syntax check: PASS
- Node syntax check: PASS
- `scripts/doctor.sh`: deterministic dependencies available
- NumPy import: PASS

## Automated tests

```text
npm test
11 / 11 test groups PASS
```

主なgroup:

- node / App Server protocol
- state / STALE / LOCK
- deck QA
- skeleton / source analysis
- design continuity
- compose / editability
- repeated render
- image pipeline
- intentional whitespace
- pixel diff
- layout engine

Layout Engine Python tests:

```text
16 / 16 PASS
```

## Official Golden Sample

Path:

```text
examples/photo-layout-poc/
```

Pages:

| Slide | Family | Fill policy | Fit score | Image lineage |
|---|---|---|---:|---|
| OUT-S001 | two_column | content_filled | 0.892 | — |
| OUT-S002 | photo_text | balanced | 0.983 | source frame reused |
| OUT-S003 | full_bleed | full_bleed | 1.000 | source frame reused |
| OUT-S004 | comparison_matrix | content_filled | 1.000 | — |
| OUT-S005 | relationship | content_filled | 1.000 | — |

QA:

```text
actual-render blocking         0
actual-render warning          0
image harmony blocking         0
image harmony warning          0
deck image coherence blocking  0
deck image coherence warning   0
```

## Visual checks

- two-column: 情報量に合わせてcard heightを縮め、short content clusterを両カードの中央へ配置
- two-column / matrix / relationship: source component typographyを継承し、26.67-inch source canvasでも可読サイズを維持
- photo-text: negative-space intentとtext sideが一致
- full-bleed: visualがslideを覆い、template chromeが前面
- comparison matrix: native editable table
- relationship: native editable nodes / connectors
- source Picture lineage:保持

## Pixel Diff performance

mutation mask外Pixel DiffはNumPy配列で計算する。scalar fallbackは互換用のみ。これによりactual-render QAのページ数増加時に、Pythonのper-pixel二重ループが主要ボトルネックになることを避ける。

## Deferred live validation

次は意図的に未実施。

- 実Codex CLI + App Server + Sol
- 実OpenAI画像生成

ユーザー方針に従い、決定論的機能の追加と全ページPoCの後にまとめて行う。

## Source typography scale checks

元PPTは26.67 × 15 inchで、本文・コンポーネント文字も標準的な13.33 × 7.5 inch資料より大きい。v0.6のstructured familyは、固定的な小さい既定値ではなく、継承元Shapeのfont sizeを上限付きで再利用する。

- two-column card title/body: source item-title / item-body scaleを継承
- comparison matrix: source header/body scaleからtable用サイズへ正規化
- relationship nodes: node box内に収まる範囲でsource scaleを継承

Golden Sampleのactual renderで、Blocking 0 / Warning 0を確認した。
