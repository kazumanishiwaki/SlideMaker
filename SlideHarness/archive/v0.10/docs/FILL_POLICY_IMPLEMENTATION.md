# Fill Policy / Layout Fit-to-Intent 実装記録

**Implementation version:** 0.6.0  
**対象:** Layout Engine、QA、GUI、App Server状態管理

## 実装目的

レイアウトエンジンがすべてのページを一律に埋めるのではなく、ページの役割に応じて、次を使い分けます。

- 強いメッセージでは意図的な余白を残す
- 比較・工程・複数項目では画面を広く使う
- 元PPTの余白構成が有効なら維持する
- 情報不足による不自然な空白だけを検出する
- 余白を埋める目的だけの文章・写真・アイコン・装飾を追加しない

## Fill Policy

- `preserve_source`
- `intentional_whitespace`
- `balanced`
- `content_filled`
- `full_bleed`

`full_bleed`はv0.6で実行可能です。ただし、実在するselected / processed visual assetを持つ`full_bleed` familyだけに適用します。テキストだけのページや、弱い画像を引き伸ばして全面表示する用途には使いません。

## 自動判定

Slide Planに明示指定がない場合、以下の順に実効方針を決めます。

1. ユーザー指定
2. Slide Plan / Layout Requestの明示指定
3. `design.md`のページ役割別指定
4. ページ役割・Layout Familyからの自動判定
5. `design.md`のデフォルト

主な自動判定：

- `cover / section / statement / quote / closing / cta / single_kpi` → `intentional_whitespace`
- `comparison / process / timeline / table / chart / three_items / four_items / grid / organization` → `content_filled`
- その他 → `balanced`

## LAYOUT_FIT_TO_INTENT

旧来の単純な画面占有率ではなく、次を検査します。

- コンテンツの横方向・縦方向の広がり
- 占有領域率
- 上下左右の空白率
- 光学中心の偏り
- 期待項目数と描画項目数
- 小さすぎるcontent island
- ページ役割とFill Policyの意味的不一致
- 意図的な余白か、偶発的なdead spaceか

Fit-to-intentに失敗したLayout Planも保存し、UI・判断ログから原因を確認できます。ただしblockingとして扱い、Final Export Gateは通過しません。

## Pixel Diff

RECOMPOSE時の変更許可領域は、スライド全体のContent Canvasではなく、実際に生成されたsemantic content clusterへ限定します。

これにより、`intentional_whitespace`で残した空白領域も未許可変更監視の対象となり、余白部分へ不要な要素が混入した場合に検出できます。

## GUI

ページ単位で以下を選択できます。

- 自動判定へ戻す
- 元PPTの余白を維持
- 余白を活かす
- バランスよく配置
- 情報を大きく展開

変更時は該当ページの `layout / render / qa` と `deck_harmony`だけをSTALE化します。他ページは再生成しません。

## Decision Trace

実効Fill Policyについて、以下を記録します。

- 採用モード
- 採用元
- ページ役割
- 判断理由
- confidence
- QA結果
- 再実行範囲

同じ実効判断で繰り返しComposeしても、Decision Traceへ同一レコードを重複追加しません。

## PoC結果

### Statement / intentional_whitespace

- Fit score: `0.907`
- Occupied area: `0.301`
- Intentional whitespace: `true`
- Accidental dead space: `false`
- QA: PASS

### Four-items grid / content_filled

- Fit score: `0.964`
- Occupied area: `0.825`
- Expected/rendered items: `4 / 4`
- Accidental dead space: `false`
- QA: PASS

全体 actual-render QA：

- Blocking: `0`
- Warning: `0`

## テスト

```bash
npm test
npm run test:poc
npm run demo:layout-intent
```

現バージョンでは11テストグループがPASSしています。Layout Engine単体は15 tests PASSです。

## v0.6で追加済み

- `two_column`
- `photo_text`
- `full_bleed`
- `comparison_matrix`
- `relationship`
- visual slotとImage Recipeの同期
- photo negative-spaceとtext sideの同期
- full-bleed visualをtemplate chromeより背面へ配置
- native editable table / relationship nodes / connectors

## 次の拡張

- actual renderを使った視線・余白リズム評価
- 高度な日本語組版QA
- screenshot / document excerpt
- Visionによる意味・破綻評価
