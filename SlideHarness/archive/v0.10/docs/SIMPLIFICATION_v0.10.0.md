# Simplification design — v0.10.0

## 目的

v0.9までに増えた個別フェーズ、重複判断、多段自動修復を整理し、品質を保ちながら実行時間・モデル呼び出し・バグ面積を抑える。

## 5段階へ統合

```text
Input Analysis
→ Deck Plan
→ Slide Plan
→ Compose
→ Validate
```

### Deck Plan

保持する情報：

- ページ順
- ページの役割
- Primary Message
- 使用する原稿単位

### Slide Plan

次の判断を1ページ1レコードへ統合する。

- semantic relation
- visual type
- source slide / adaptation mode
- semantic chunks / render text
- image requirement
- layout family / density / fill policy
- composer runtime payload

以下は別のAIフェーズにしない。

- Visual Plan
- Source Match
- Continuity Plan
- Fill Policy
- Image Plan

既存コード向けの`visual_plan.json`、`slide_matching.json`はSlide Planから決定論的に生成する。

## 5 Renderer群

公開Layout Familyは残すが、内部ジオメトリエンジンは5群にまとめる。

| Renderer | Family |
|---|---|
| statement | cover / section / statement / closing |
| grid | grid / two_column / comparison_matrix |
| media | photo_text / full_bleed / photo_grid / screenshot |
| flow | process / timeline / relationship / cause_effect / containment |
| data | kpi / chart / table |

## Semantic compatibility

別の推論エンジンを作らず、薄いallowlistで検証する。

例：

- sequence → process / timeline
- cause_effect → process / timeline / cause_effect
- comparison → two_column / comparison_matrix / chart / table
- containment → containment / process / comparison_matrix
- evidence → photo_text / screenshot / chart / table

明らかに意味が異なる組み合わせだけBlockingにする。

## 改行

優先順位：

1. ユーザーまたはSlide Planの明示改行
2. semantic chunks
3. 読点・句点
4. 実フォントフィット

Rendererは意味チャンクを行長均等化のために壊さない。

## QA

```text
Technical QA
Content QA
Design Review
```

Design Reviewを無制限な自動修正ループへ接続しない。決定論的修正、1つの別Variantを試した後は`REVIEW_REQUIRED`とする。

## 画像処理

全画像を高コスト解析しない。

```text
全PPT              軽量分類
採用候補ページ      詳細分類
実際に変更する画像  必要時のみVision
```

## Decision Log

記録対象を次へ限定する。

- Deck構成
- Primary Message
- semantic relation / visual type
- source slide / layout family
- user override
- 意味変更を伴う修正
- Blocking QA修正

座標微調整や軽微なフォント調整は通常ログへ残さない。

## Render cadence

```text
構成確認
→ 代表ページRender
→ 全ページ生成
→ 変更ページのみRender
→ 最終全体Render
```

フェーズごとの全ページRenderは行わない。
