# n2p ロゴ運用ルール

## 1. ロゴファイル2種類

| ファイル名 | 用途 | 使用背景 |
|---|---|---|
| `symbol_black.png` | 明るい背景上でのロゴ配置 | 白・ライトグレー背景（明度 `#CCCCCC` 以上） |
| `symbol_white.png` | 暗い背景上・写真上でのロゴ配置 | 黒・濃グレー背景・写真（暗度 `#959595` 以下） |

### アセットパス
```
n2p-pptx-skill/assets/symbol_black.png
n2p-pptx-skill/assets/symbol_white.png
```

---

## 2. アイソレーション領域（隔離エリア）

ロゴの四方に、**ロゴ高さの50%以上**の余白（隔離エリア）を確保すること。

```
  ┌──────────────────────────┐
  │    ← h×50% →            │
  │  ↑                       │
  │ h×50%  [ LOGO ]  h×50%  │
  │  ↓                       │
  │    ← h×50% →            │
  └──────────────────────────┘
```

- `h` = ロゴの高さ
- 隔離エリア内にテキスト・図形・他のロゴを配置しない

---

## 3. 最小サイズ基準

| 媒体 | 最小サイズ |
|---|---|
| Web / スクリーン | **32px**（高さ） |
| 印刷物 | **10mm**（高さ） |

最小サイズ未満での使用は禁止。視認性が損なわれるため。

---

## 4. 配置5シーン詳細仕様

### シーン1: 本文スライド（右上）

```
ファイル: symbol_black.png
位置: x=8.9, y=0.15, w=0.9, h=0.30
背景: 白（#FCFCFC） → 黒ロゴ使用
```

```javascript
slide.addImage({
  path: './assets/symbol_black.png',
  x: 8.9, y: 0.15, w: 0.9, h: 0.30,
});
```

### シーン2: 中表紙スライド（右上）

```
ファイル: symbol_white.png
位置: x=8.9, y=0.15, w=0.9, h=0.30
背景: ライトグレー（#E6EBED）または黒帯 → 白ロゴ使用
```

```javascript
slide.addImage({
  path: './assets/symbol_white.png',
  x: 8.9, y: 0.15, w: 0.9, h: 0.30,
});
```

> 注意: 中表紙の背景色が明るい（`#E6EBED`）場合、黒ロゴ（`symbol_black.png`）を使用する。デザイン判断で背景が暗ければ白ロゴを選択。

### シーン3: 表紙（右下透かし）

```
ファイル: symbol_white.png
位置: x=6.2, y=4.0, w=3.8, h=1.25
透明度: 70%（transparency=70）
背景: 表紙は全面ダーク or 写真 → 白ロゴ使用
```

```javascript
slide.addImage({
  path: './assets/symbol_white.png',
  x: 6.2, y: 4.0, w: 3.8, h: 1.25,
  transparency: 70,  // 0〜100 (100=完全透明)
});
```

> 重要: この透かしロゴは `transparency: 70` のみ許可。他のシーンで透明度変更は禁止。

### シーン4: 会社概要スライド（ヘッダー内右側）

```
ファイル: symbol_white.png
位置: ヘッダー帯の内部右側（実装時に帯の高さに合わせて調整）
背景: ヘッダー帯（黒 #111111 など） → 白ロゴ使用
参考位置: x=8.5〜9.0, y=0.1〜0.3 （帯の高さによる）
```

```javascript
// 会社概要ヘッダー帯（例: 高さ0.7inch）
slide.addShape(pptx.ShapeType.rect, {
  x: 0, y: 0, w: 10, h: 0.7,
  fill: { color: '111111' },
});
// 白ロゴ右寄せ配置
slide.addImage({
  path: './assets/symbol_white.png',
  x: 8.8, y: 0.12, w: 0.9, h: 0.30,
});
```

### シーン5: エンドスライド（中央）

```
ファイル: symbol_black.png
位置: x=3.5, y=2.0, w=3.0, h=0.99
背景: 白（#FCFCFC） → 黒ロゴ使用
```

```javascript
slide.addImage({
  path: './assets/symbol_black.png',
  x: 3.5, y: 2.0, w: 3.0, h: 0.99,
});
// ロゴ下テキスト（「NONAME Produce」固定）
slide.addText('NONAME Produce', {
  x: 3.5, y: 3.05, w: 3.0, h: 0.4,
  fontFace: 'Helvetica Neue',
  fontSize: 13,
  color: '111111',
  align: 'center',
});
```

---

## 5. 写真上へのロゴ配置ルール

写真背景や画像上にロゴを配置する場合、コントラストを必ず確認する。

| ロゴ種 | 使用条件 | 背景の明度基準 |
|---|---|---|
| `symbol_black.png` | 明るい写真エリアに配置 | 配置箇所の平均明度が `#CCCCCC` 以上 |
| `symbol_white.png` | 暗い写真エリアに配置 | 配置箇所の平均明度が `#959595` 以下 |

- 写真の明暗が混在する箇所へのロゴ配置は避ける
- やむを得ず混在箇所に配置する場合は、ロゴ背景に単色オーバーレイを敷く

---

## 6. 禁止操作 10+ 項目

以下の操作はすべて禁止。VIガイドライン違反となる。

| # | 禁止操作 | 理由 |
|---|---|---|
| 1 | **回転** | ロゴの向きを変えない。常に正立で使用 |
| 2 | **縦横比変更（歪み）** | ロゴのアスペクト比を維持。拡縮は等倍のみ |
| 3 | **色の改変** | symbol_black / symbol_white の2種以外の着色禁止 |
| 4 | **透明度変更（規定外）** | 表紙透かし（70%）以外の透明度変更禁止 |
| 5 | **装飾の追加** | ロゴに影・光彩・境界線・エンボス等を追加しない |
| 6 | **分解・再配置** | ロゴを構成要素に分解して別々に配置しない |
| 7 | **アウトライン化・変形** | ロゴをアウトライン化して変形・編集しない |
| 8 | **複合テキスト** | ロゴ画像とテキストを重ねて一体化させない |
| 9 | **パターン背景上への配置** | 複雑なパターン・テクスチャ背景上への配置禁止 |
| 10 | **最小サイズ未満での使用** | Web 32px / Print 10mm 未満での使用禁止 |
| 11 | **隔離エリアへの侵入** | ロゴ高さ50%の隔離エリアに他要素を配置しない |
| 12 | **コントラスト基準外配置** | 明度基準（#CCCCCC/#959595）を満たさない背景への配置禁止 |

---

## 7. pptxgenjs での addImage 実装まとめ

```javascript
/**
 * n2p ロゴを指定シーンに追加するヘルパー
 * @param {object} slide - pptxgenjs のスライドオブジェクト
 * @param {string} scene - 'body' | 'divider' | 'cover' | 'company' | 'end'
 * @param {string} assetsDir - assets ディレクトリのパス
 */
function addN2pLogo(slide, scene, assetsDir = './assets') {
  const logoConfig = {
    body: {
      file: `${assetsDir}/symbol_black.png`,
      x: 8.9, y: 0.15, w: 0.9, h: 0.30,
    },
    divider: {
      file: `${assetsDir}/symbol_white.png`,
      x: 8.9, y: 0.15, w: 0.9, h: 0.30,
    },
    cover: {
      file: `${assetsDir}/symbol_white.png`,
      x: 6.2, y: 4.0, w: 3.8, h: 1.25,
      transparency: 70,
    },
    company: {
      file: `${assetsDir}/symbol_white.png`,
      x: 8.8, y: 0.12, w: 0.9, h: 0.30,
    },
    end: {
      file: `${assetsDir}/symbol_black.png`,
      x: 3.5, y: 2.0, w: 3.0, h: 0.99,
    },
  };

  const config = logoConfig[scene];
  if (!config) throw new Error(`Unknown logo scene: ${scene}`);

  const { file, transparency, ...pos } = config;
  const imageOpts = { path: file, ...pos };
  if (transparency !== undefined) imageOpts.transparency = transparency;

  slide.addImage(imageOpts);
}

// 使用例
addN2pLogo(slide, 'body');    // 本文スライド右上（黒ロゴ）
addN2pLogo(slide, 'cover');   // 表紙右下透かし（白ロゴ, 70%透明）
addN2pLogo(slide, 'end');     // エンドスライド中央（黒ロゴ）
```

---

## 8. ロゴ使用チェックリスト

- [ ] 使用ロゴは `symbol_black.png` または `symbol_white.png` のどちらかか
- [ ] ロゴの縦横比が変更されていないか（等倍拡縮のみ）
- [ ] ロゴが回転していないか（常に正立）
- [ ] 隔離エリア（ロゴ高さ×50%）が確保されているか
- [ ] 表紙透かしロゴの透明度が70%に設定されているか
- [ ] 最小サイズ（Web 32px / Print 10mm）を下回っていないか
- [ ] 写真上配置時にコントラスト基準（#CCCCCC/#959595）を満たしているか
- [ ] ロゴに色改変・装飾・影が追加されていないか
- [ ] エンドスライドのロゴ下テキストが「NONAME Produce」になっているか

<!-- DONE: 2891 -->
