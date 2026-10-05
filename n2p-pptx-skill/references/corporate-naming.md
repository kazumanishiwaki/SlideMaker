# n2p 企業名表記ルール

## 1. 正式表記3パターン

| # | 表記 | 使用場面 |
|---|---|---|
| 1 | `株式会社 NONAME Produce` | 法人名が必要な正式文書・契約関連・初出箇所（法人名明記が必要な場合） |
| 2 | `NONAME Produce` | 一般的な資料・提案書・スライド内での社名表記 |
| 3 | `n2p` | 略称・カジュアルな文脈・ロゴ下テキスト以外の略称表記 |

> 「NONAME」はすべて大文字、「Produce」は頭文字のみ大文字。「n2p」はすべて小文字。この大小文字のルールは絶対に変更しない。

---

## 2. 初出時の表記パターン

文書・資料の中で社名を最初に記載する際は、以下のいずれかのパターンを使用する。

| パターン | 記法 | 推奨度 |
|---|---|---|
| A | `NONAME Produce(以下 n2p)` | 推奨（法人名不要の場合） |
| B | `NONAME Produce(n2p)` | 可（括弧内に略称のみ） |
| C | `株式会社 NONAME Produce(以下 n2p)` | 推奨（法人名明記が必要な場合） |
| D | `株式会社 NONAME Produce(n2p)` | 可（括弧内に略称のみ） |

- 初出以降は `n2p` または `NONAME Produce` のいずれかに統一
- 同一文書内で `n2p` と `NONAME Produce` を混在させない（どちらかに統一）

---

## 3. NG表記5パターン（絶対禁止）

以下の表記は VIガイドライン違反であり、スライド本文・コード例・コメント・フッターを含むあらゆる箇所で使用を禁止する。

| # | NG表記 | 理由 | 正しい表記 |
|---|---|---|---|
| 1 | `N2P` | 大文字混在（N・Pを大文字にしてはならない） | `n2p` |
| 2 | `株式会社 n2p` | 小文字の `n2p` は法人名として使用不可 | `株式会社 NONAME Produce` |
| 3 | `nonameproduce` | 全小文字・スペースなし（ロゴ下テキストにも使用不可） | `NONAME Produce` |
| 4 | `noname produce` | 全小文字・スペースあり | `NONAME Produce` |
| 5 | `株式会社 N2P` | 大文字N2Pは法人名・略称どちらにもNG | `株式会社 NONAME Produce` |

---

## 4. スライド特定箇所の固定表記

### フッター（全スライド共通）
```
© NONAME Produce Inc.
```
- `Inc.` はドット込みで固定
- `©` の後にスペース1つ
- 変形例（`© n2p Inc.` / `© N2P Inc.`）は不可

### エンドスライドのロゴ下テキスト
```
NONAME Produce
```
- `nonameproduce`（全小文字・スペースなし）は絶対NG
- `n2p` もエンドスライドロゴ下テキストには使用しない
- `NONAME Produce` に固定

---

## 5. pptxgenjs コード例

### 正しい表記でのコード例

```javascript
// フッター（正しい表記）
slide.addText('© NONAME Produce Inc.', {
  x: 0.28, y: 5.30, w: 4.0, h: 0.25,
  fontFace: 'Noto Sans JP',
  fontSize: 8,
  color: '999999',
});

// エンドスライドのロゴ下テキスト（正しい表記）
slide.addText('NONAME Produce', {
  x: 3.5, y: 3.05, w: 3.0, h: 0.4,
  fontFace: 'Helvetica Neue',
  fontSize: 13,
  color: '111111',
  align: 'center',
});

// 初出時の表記（法人名不要）
slide.addText('NONAME Produce(以下 n2p)', {
  x: 0.5, y: 1.0, w: 5.0, h: 0.4,
  fontFace: 'Noto Sans JP',
  fontSize: 11,
  color: '434343',
});

// 初出時の表記（法人名明記が必要）
slide.addText('株式会社 NONAME Produce(以下 n2p)', {
  x: 0.5, y: 1.0, w: 6.0, h: 0.4,
  fontFace: 'Noto Sans JP',
  fontSize: 11,
  color: '434343',
});

// 略称（2回目以降）
slide.addText('n2p が提供するサービスについて', {
  x: 0.5, y: 1.5, w: 9.0, h: 0.4,
  fontFace: 'Noto Sans JP',
  fontSize: 11,
  color: '434343',
});

// 表紙宛名（送付先）の例
slide.addText('株式会社 NONAME Produce', {
  x: 0.5, y: 4.5, w: 5.0, h: 0.5,
  fontFace: 'Noto Sans JP',
  fontSize: 14,
  color: '111111',
});
```

### NG例（使用禁止）

```javascript
// NG: N2P（大文字混在）
// slide.addText('N2P', ...);  ← 絶対禁止

// NG: nonameproduce（全小文字スペースなし）
// slide.addText('nonameproduce', ...);  ← 絶対禁止

// NG: 株式会社 n2p（小文字n2pを法人名に使用）
// slide.addText('株式会社 n2p', ...);  ← 絶対禁止

// NG: noname produce（全小文字スペースあり）
// slide.addText('noname produce', ...);  ← 絶対禁止

// NG: 株式会社 N2P
// slide.addText('株式会社 N2P', ...);  ← 絶対禁止

// NG: エンドスライドに nonameproduce
// slide.addText('nonameproduce', { x: 3.5, y: 3.05, ... });  ← 絶対禁止
```

---

## 6. 表記確認チェックリスト

- [ ] スライド内の社名が `株式会社 NONAME Produce` / `NONAME Produce` / `n2p` のいずれかのみか
- [ ] `N2P`（大文字混在）が存在しないか
- [ ] `nonameproduce`（全小文字）が存在しないか
- [ ] `noname produce`（全小文字スペースあり）が存在しないか
- [ ] `株式会社 n2p` が存在しないか
- [ ] `株式会社 N2P` が存在しないか
- [ ] フッターが `© NONAME Produce Inc.` に固定されているか
- [ ] エンドスライドのロゴ下が `NONAME Produce` になっているか
- [ ] 初出時に `(以下 n2p)` または `(n2p)` の注記があるか（略称使用の場合）

<!-- DONE: 1821 -->
