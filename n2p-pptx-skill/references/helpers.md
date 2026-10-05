# n2p-pptx ヘルパー関数仕様書

このドキュメントは `slide-patterns.md` 全体で繰り返し呼び出されるヘルパー関数の **完全仕様** を定義する。  
実装者はこのファイルを一次参照とし、各関数の挙動・座標・依存定数を確認すること。

---

## 依存定数

すべてのヘルパー関数はこれらの定数を前提とする。ファイル先頭で一度だけ宣言すること。

```js
// ===== アセットパス =====
const LOGO_BLACK_PATH = 'assets/symbol_black.png'; // 白・明背景用
const LOGO_WHITE_PATH = 'assets/symbol_white.png'; // 暗・グレー背景用

// ===== カラーパレット（VI準拠） =====
const N2P_COLORS = {
  black:       '111111', // 主見出し・フッター線・ロゴ黒（VI最優先）
  white:       'FCFCFC', // 背景白（純白#FFFFFFは使わない）
  darkGray:    '676A6D', // サブテキスト・強めアクセント
  midGray:     '929699', // 中位アクセント
  liteGray:    'E6EBED', // 薄背景・差し色（表紙・中表紙）
  coverBg:     'D7DEE2', // 表紙・中表紙背景グレー
  bodyText:    '434343', // 本文テキスト（テンプレ実装慣習）
  footerText:  '999999', // フッター文字
  divider:     'CCCCCC', // フッター軸線・区切り線
  yellowDark:  'E8E800', // 小面積強調（文字ハイライト等）
  yellowLight: 'F4F400', // 大面積強調（マーカー等）
  linkBlue:    '4285F4', // リンク色
  teal:        '0097A7', // ハイパーリンク色
};

// ===== スライドサイズ定数 =====
const SLIDE_W = 10.0;    // inch
const SLIDE_H = 5.625;   // inch

// ===== マージン（0.5cm ≈ 0.197in） =====
const MARGIN = 0.197;

// ===== フッター座標（導出式付き） =====
// 軸線X開始 = マージン左(0.197) + 補正(0.083) = 0.28
// 軸線X終了 = SLIDE_W - 0.28 = 9.72 → 幅 = 9.72 - 0.28 = 9.44
const FOOTER = {
  lineX:       0.28,
  lineY:       5.28,
  lineW:       9.44,
  copyrightX:  0.28,
  copyrightY:  5.30,
  pageNumX:    9.20,
  pageNumY:    5.30,
  pageNumW:    0.5,
};
```

---

## 1. `addLogoBlack(slide)`

### 用途
白背景・明るいグレー背景のスライド右上にロゴ（黒版）を配置する。  
本文スライド・目次スライドで使用する。

### シグネチャ
```js
function addLogoBlack(slide)
```

| パラメータ | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `slide` | PptxGenJS Slide | ✅ | 対象スライドオブジェクト |

**戻り値**: なし（void）

### 内部実装
```js
function addLogoBlack(slide) {
  slide.addImage({
    path: LOGO_BLACK_PATH,
    x: 8.9,
    y: 0.15,
    w: 0.9,
    h: 0.30,
  });
}
```

### 座標の根拠
- `x: 8.9` = スライド幅10.0 - ロゴ幅0.9 - 右マージン調整0.2 = 8.9
- `y: 0.15` = 上マージン（0.197in）より若干内側で上寄せ
- `w: 0.9, h: 0.30` = アスペクト比3:1（横長ロゴの標準比率）

### 使用例
```js
const slide = pptx.addSlide();
slide.background = { color: N2P_COLORS.white };
addLogoBlack(slide);
```

### 注意点
- 座標はすべて固定値。パラメータ化は**禁止**（全スライドで位置を統一するため）
- 暗背景・グレー背景では `addLogoWhite` を使うこと
- 写真上に配置する場合は明度 `#CCCCCC` 以上のエリアにのみ配置可

---

## 2. `addLogoWhite(slide)`

### 用途
暗背景・グレー背景のスライド右上にロゴ（白版）を配置する。  
中表紙・グレー背景スライドで使用する。

### シグネチャ
```js
function addLogoWhite(slide)
```

| パラメータ | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `slide` | PptxGenJS Slide | ✅ | 対象スライドオブジェクト |

**戻り値**: なし（void）

### 内部実装
```js
function addLogoWhite(slide) {
  slide.addImage({
    path: LOGO_WHITE_PATH,
    x: 8.9,
    y: 0.15,
    w: 0.9,
    h: 0.30,
  });
}
```

### 使用例
```js
const slide = pptx.addSlide();
slide.background = { color: N2P_COLORS.coverBg }; // #D7DEE2
addLogoWhite(slide); // グレー背景なので白ロゴ
```

### 注意点
- 座標は `addLogoBlack` と完全に同一（右上位置の統一）
- 写真上に配置する場合は暗度 `#959595` 以下のエリアにのみ配置可
- 明るい白背景への白ロゴ配置は視認性ゼロになるため**厳禁**

---

## 3. `addLogoCoverWatermark(slide)`

### 用途
表紙スライド右下に、半透明の透かしロゴ（白版・大サイズ）を配置する。  
表紙専用。本文スライドには使用しない。

### シグネチャ
```js
function addLogoCoverWatermark(slide)
```

| パラメータ | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `slide` | PptxGenJS Slide | ✅ | 対象スライドオブジェクト |

**戻り値**: なし（void）

### 内部実装
```js
function addLogoCoverWatermark(slide) {
  slide.addImage({
    path: LOGO_WHITE_PATH,
    x: 6.2,
    y: 4.0,
    w: 3.8,
    h: 1.25,
    transparency: 70, // 70%透明 = 30%不透明で透かし効果
  });
}
```

### 座標の根拠
- `x: 6.2` = 右下エリア。スライド幅10.0 - ロゴ幅3.8 = 6.2
- `y: 4.0` = スライド高5.625 - ロゴ高1.25 - 下余白0.375 ≈ 4.0
- `transparency: 70` = VIガイドライン推奨の透かし効果。ロゴの透明度変更は規定値のみ許可

### 使用例
```js
function createCoverSlide(pptx, { clientName, title, date }) {
  const slide = pptx.addSlide();
  slide.background = { color: N2P_COLORS.coverBg };
  // テキスト追加...
  addLogoCoverWatermark(slide); // 右下に透かしロゴ
  // フッターなし・ページ番号なし
}
```

### 注意点
- `transparency: 70` は固定値。変更しないこと（VIガイドライン規定）
- 表紙以外でのロゴ透明度変更は**禁止**
- フッター・ページ番号は表紙には**追加しない**

---

## 4. `addFooter(slide, pageNum)`

### 用途
本文スライドの下部に「軸線 + コピーライト + ページ番号」の3要素を配置する。  
表紙・中表紙・エンドスライドには**呼び出してはいけない**。

### シグネチャ
```js
function addFooter(slide, pageNum)
```

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|---|------|----------|------|
| `slide` | PptxGenJS Slide | ✅ | - | 対象スライドオブジェクト |
| `pageNum` | number | ✅ | - | ページ番号（半角数字。1から始まる整数） |

**戻り値**: なし（void）

### 内部実装
```js
function addFooter(slide, pageNum) {
  // 軸線（水平線 #CCCCCC 0.5pt）
  slide.addShape('line', {
    x: FOOTER.lineX,   // 0.28
    y: FOOTER.lineY,   // 5.28
    w: FOOTER.lineW,   // 9.44
    h: 0.0,
    line: { color: N2P_COLORS.divider, width: 0.5 },
  });

  // コピーライト（左寄せ）
  slide.addText('© NONAME Produce Inc.', {
    x: FOOTER.copyrightX,  // 0.28
    y: FOOTER.copyrightY,  // 5.30
    w: 3.0,
    h: 0.25,
    fontSize: 8,
    color: N2P_COLORS.footerText,  // '999999'
    fontFace: 'Noto Sans JP',
  });

  // ページ番号（右寄せ、半角数字）
  slide.addText(String(pageNum), {
    x: FOOTER.pageNumX,  // 9.20
    y: FOOTER.pageNumY,  // 5.30
    w: FOOTER.pageNumW,  // 0.5
    h: 0.25,
    fontSize: 9,
    color: N2P_COLORS.footerText,  // '999999'
    fontFace: 'Noto Sans JP',
    align: 'right',
  });
}
```

### 使用例
```js
// 本文スライド（例: 3枚目のスライド = ページ番号3）
const slide = pptx.addSlide();
addH1(slide, '要件のご確認');
addLogoBlack(slide);
addBody(slide, '本文テキスト...', 0.48, 0.7, 8.8, 4.2);
addFooter(slide, 3); // ←最後に呼び出す
```

### 注意点
- ページ番号は**半角数字**のみ。全角数字（３）は**禁止**
- 表紙・中表紙・エンドスライドでは呼び出し**禁止**
- コピーライト文字列は `© NONAME Produce Inc.` で固定。変更不可
- 軸線の幅・色・太さはすべて固定値

---

## 5. `addH1(slide, text)`

### 用途
本文スライドの大見出し（タイトル）を追加する。  
見出しテキストの左側に短い水平ダッシュ線を描画し、n2p提案資料の特徴的なデザインを実現する。

### シグネチャ
```js
function addH1(slide, text)
```

| パラメータ | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `slide` | PptxGenJS Slide | ✅ | 対象スライドオブジェクト |
| `text` | string | ✅ | 見出しテキスト（最大40文字程度を推奨） |

**戻り値**: なし（void）

### 内部実装
```js
function addH1(slide, text) {
  // 左ダッシュ線（水平線 #111111 1pt 0.45in）
  slide.addShape('line', {
    x: 0.05,
    y: 0.35,
    w: 0.45,
    h: 0.0,
    line: { color: N2P_COLORS.black, width: 1 }, // #111111
  });

  // 見出しテキスト（16pt Bold #111111）
  slide.addText(text, {
    x: 0.55,
    y: 0.14,
    w: 7.5,
    h: 0.42,
    fontSize: 16,
    bold: true,
    color: N2P_COLORS.black, // '111111'
    fontFace: 'Noto Sans JP',
    valign: 'middle',
  });
}
```

### 座標の根拠
- 線 `x: 0.05` = 左マージン(0.197in)より内側で始まる短い線
- 線 `w: 0.45` = ロゴの「隔離エリア」感を演出する適切な長さ
- テキスト `x: 0.55` = 線の終点(0.05+0.45=0.50)から 0.05in の余白
- テキスト `y: 0.14` = 上部から0.14inで、線の中心(y=0.35)とvisually整合

### 使用例
```js
addH1(slide, '01. 要件のご確認');
addH1(slide, 'キャンペーン概要');
addH1(slide, '事例紹介');
```

### 注意点
- 左ダッシュ線は**省略禁止**。n2p提案資料の必須要素
- 線の色は `#111111`（VIブラック）のみ。`#000000` や他のグレーは使わない
- 見出しテキストの色も同じく `#111111`
- 本文スライド1枚に `addH1` は1回のみ呼び出す（複数の大見出しは禁止）

---

## 6. `addH2Dark(slide, text, x, y, w)`

### 用途
中見出しバリエーション1: ダーク帯（#434343背景 + 白文字）。  
メリハリを強く出したいセクション見出しに使用する。

### シグネチャ
```js
function addH2Dark(slide, text, x, y, w)
```

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|---|------|----------|------|
| `slide` | PptxGenJS Slide | ✅ | - | 対象スライドオブジェクト |
| `text` | string | ✅ | - | 見出しテキスト |
| `x` | number | ✅ | - | 左端座標（inch） |
| `y` | number | ✅ | - | 上端座標（inch） |
| `w` | number | ❌ | `2.5` | 幅（inch）。省略時は2.5in |

**戻り値**: なし（void）

### 内部実装
```js
function addH2Dark(slide, text, x, y, w) {
  w = w || 2.5;

  // ダーク背景（角丸長方形 #434343）
  slide.addShape('roundRect', {
    x: x, y: y, w: w, h: 0.35,
    fill: { color: N2P_COLORS.bodyText }, // '434343'
    rectRadius: 0.02,
  });

  // 白テキスト（13pt Bold）
  slide.addText(text, {
    x: x, y: y, w: w, h: 0.35,
    fontSize: 13,
    bold: true,
    color: 'FFFFFF',
    fontFace: 'Noto Sans JP',
    align: 'center',
    valign: 'middle',
  });
}
```

### 使用例
```js
// 2.5inの中見出し（デフォルト）
addH2Dark(slide, 'ターゲット設計', 0.48, 0.7);

// 幅指定あり（組織図パートナーセクション）
addH2Dark(slide, 'デザインパートナー', 6.0, 1.5, 3.5);
```

### 注意点
- 高さ `h: 0.35` は固定値。変更しないこと
- テキストカラーは `'FFFFFF'` 固定（N2P_COLORS.white ではなく純白で可視性を確保）
- 背景色は `N2P_COLORS.bodyText`（`#434343`）のみ。黒や他のダーク色は使わない

---

## 7. `addH2Light(slide, text, x, y, w)`

### 用途
中見出しバリエーション2: ライトグレー帯（#E6EBED背景）+ 左の丸ドットアクセント。  
背景が白のスライドで、柔らかいメリハリを出したい場合に使用する。

### シグネチャ
```js
function addH2Light(slide, text, x, y, w)
```

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|---|------|----------|------|
| `slide` | PptxGenJS Slide | ✅ | - | 対象スライドオブジェクト |
| `text` | string | ✅ | - | 見出しテキスト |
| `x` | number | ✅ | - | 帯の左端座標（inch） |
| `y` | number | ✅ | - | 帯の上端座標（inch） |
| `w` | number | ❌ | `2.5` | 帯の幅（inch） |

**戻り値**: なし（void）

### 内部実装
```js
function addH2Light(slide, text, x, y, w) {
  w = w || 2.5;

  // 左の丸ドット（黒 #111111）
  slide.addShape('ellipse', {
    x: x - 0.15,
    y: y + 0.12,
    w: 0.1,
    h: 0.1,
    fill: { color: N2P_COLORS.black }, // '111111'
  });

  // ライトグレー帯（角丸長方形 #E6EBED）
  slide.addShape('roundRect', {
    x: x, y: y, w: w, h: 0.35,
    fill: { color: N2P_COLORS.liteGray }, // 'E6EBED'
    rectRadius: 0.02,
  });

  // テキスト（13pt Bold #111111）
  slide.addText(text, {
    x: x, y: y, w: w, h: 0.35,
    fontSize: 13,
    bold: true,
    color: N2P_COLORS.black, // '111111'
    fontFace: 'Noto Sans JP',
    valign: 'middle',
  });
}
```

### 使用例
```js
addH2Light(slide, '課題の背景', 0.63, 0.7);
// → x=0.63 で呼ぶと、ドットは x=0.48 に配置される（0.63 - 0.15 = 0.48）
```

### 注意点
- ドットの位置は帯の `x - 0.15` に自動計算される
- ドット色は `#111111`（VIブラック）
- 帯の背景色は `#E6EBED`（VI規定のライトグレー）。`#EEEEEE` など別グレーは使わない

---

## 8. `addH2Underline(slide, text, x, y, w)`

### 用途
中見出しバリエーション3: テキスト下にグラデーション下線 + 右端に丸ドット。  
背景が白のスライドで、最もシンプルで軽いアクセントを使いたい場合に使用する。

### シグネチャ
```js
function addH2Underline(slide, text, x, y, w)
```

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|---|------|----------|------|
| `slide` | PptxGenJS Slide | ✅ | - | 対象スライドオブジェクト |
| `text` | string | ✅ | - | 見出しテキスト |
| `x` | number | ✅ | - | テキストの左端座標（inch） |
| `y` | number | ✅ | - | テキストの上端座標（inch） |
| `w` | number | ❌ | `4.0` | テキストエリアの幅（inch） |

**戻り値**: なし（void）

### 内部実装
```js
function addH2Underline(slide, text, x, y, w) {
  w = w || 4.0;

  // テキスト（13pt Bold #111111）
  slide.addText(text, {
    x: x, y: y, w: w, h: 0.35,
    fontSize: 13,
    bold: true,
    color: N2P_COLORS.black, // '111111'
    fontFace: 'Noto Sans JP',
    valign: 'middle',
  });

  // 下線（グレー #CCCCCC 1pt、幅60%）
  slide.addShape('line', {
    x: x,
    y: y + 0.38,
    w: w * 0.6,
    h: 0.0,
    line: { color: N2P_COLORS.divider, width: 1 }, // 'CCCCCC'
  });

  // 右端の丸ドット（グレー #CCCCCC）
  slide.addShape('ellipse', {
    x: x + w * 0.6,
    y: y + 0.34,
    w: 0.08,
    h: 0.08,
    fill: { color: N2P_COLORS.divider }, // 'CCCCCC'
  });
}
```

### 使用例
```js
addH2Underline(slide, '提案の方向性', 0.48, 0.7);
addH2Underline(slide, '実施スケジュール概要', 0.48, 1.5, 5.0);
```

### 注意点
- 下線の幅は `w * 0.6`（テキスト幅の60%）で固定
- 下線・ドット色は `#CCCCCC`（N2P_COLORS.divider）
- デフォルト幅は `addH2Dark/addH2Light` の 2.5in より広い 4.0in

---

## 9. `addH2OnImage(slide, text, x, y, w, imagePath)`

### 用途
中見出しバリエーション4: 画像を背景にした半透明の見出し帯。  
事例紹介・デザイン提案スライドで画像上にテキストを重ねる場合に使用する。

### シグネチャ
```js
function addH2OnImage(slide, text, x, y, w, imagePath)
```

| パラメータ | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `slide` | PptxGenJS Slide | ✅ | 対象スライドオブジェクト |
| `text` | string | ✅ | 見出しテキスト |
| `x` | number | ✅ | 左端座標（inch） |
| `y` | number | ✅ | 上端座標（inch） |
| `w` | number | ✅ | 幅（inch） |
| `imagePath` | string | ✅ | 背景画像パス |

**戻り値**: なし（void）

### 内部実装
```js
function addH2OnImage(slide, text, x, y, w, imagePath) {
  // 背景画像
  slide.addImage({
    path: imagePath,
    x: x, y: y, w: w, h: 0.35,
    sizing: { type: 'cover' },
  });

  // 半透明ダークオーバーレイ（#111111 50%透明）
  slide.addShape('rect', {
    x: x, y: y, w: w, h: 0.35,
    fill: { color: N2P_COLORS.black, transparency: 50 }, // '111111' 50%透明
  });

  // 白テキスト（13pt Bold）
  slide.addText(text, {
    x: x, y: y, w: w, h: 0.35,
    fontSize: 13,
    bold: true,
    color: 'FFFFFF',
    fontFace: 'Noto Sans JP',
    align: 'center',
    valign: 'middle',
  });
}
```

### 使用例
```js
addH2OnImage(slide, '事例：ECサイトリニューアル', 0.48, 0.7, 4.5, 'assets/case_ec.jpg');
```

### 注意点
- 画像上のテキストは**視認性の確保が必須**。明るすぎる画像には使用しない
- オーバーレイ透明度 `50` は固定値。変更しないこと
- テキスト色は `'FFFFFF'`（白）固定

---

## 10. `addBody(slide, text, x, y, w, h, options)`

### 用途
本文テキストを追加する汎用関数。  
本文テキストに必要なスタイル（11pt / #434343 / 行間1.15）をデフォルト値として持ち、オプションで上書き可能。

### シグネチャ
```js
function addBody(slide, text, x, y, w, h, options)
```

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|---|------|----------|------|
| `slide` | PptxGenJS Slide | ✅ | - | 対象スライドオブジェクト |
| `text` | string \| Array | ✅ | - | 本文テキスト。pptxgenjs の rich-text 配列も可 |
| `x` | number | ✅ | - | 左端座標（inch） |
| `y` | number | ✅ | - | 上端座標（inch） |
| `w` | number | ✅ | - | 幅（inch） |
| `h` | number | ✅ | - | 高さ（inch） |
| `options` | object | ❌ | `{}` | pptxgenjs テキストオプション。デフォルトを上書きしたい項目のみ指定 |

**戻り値**: なし（void）

### デフォルトオプション（全項目）
| プロパティ | デフォルト値 | 意味 |
|-----------|------------|------|
| `fontSize` | `11` | 本文標準サイズ |
| `color` | `'434343'` | 本文標準色 |
| `fontFace` | `'Noto Sans JP'` | 標準フォント |
| `lineSpacingMultiple` | `1.15` | 行間（1.0や1.5は禁止） |
| `valign` | `'top'` | 縦位置（デフォルト上揃え） |
| `paraSpaceAfter` | `4` | 段落後スペース（pt） |

### 内部実装
```js
function addBody(slide, text, x, y, w, h, options) {
  const defaults = {
    x: x, y: y, w: w, h: h,
    fontSize: 11,
    color: N2P_COLORS.bodyText, // '434343'
    fontFace: 'Noto Sans JP',
    lineSpacingMultiple: 1.15,
    valign: 'top',
    paraSpaceAfter: 4,
  };
  const opts = Object.assign(defaults, options || {});
  slide.addText(text, opts);
}
```

### 使用例
```js
// 基本的な本文
addBody(slide, '本文テキストです。', 0.48, 0.7, 8.8, 4.2);

// フォントサイズだけ変更（9pt注釈）
addBody(slide, '※注釈テキスト', 0.48, 4.8, 8.8, 0.3, { fontSize: 9, color: N2P_COLORS.footerText });

// 中央配置
addBody(slide, 'キャンペーン名', 0.48, 2.0, 9.0, 0.5, { align: 'center', fontSize: 13, bold: true });
```

### 注意点
- `lineSpacingMultiple: 1.15` は変更禁止。1.0や1.5は使わない
- `color` のデフォルト `#434343` を別のグレーに変更しないこと
- 本文左端 `x` は `0.48` 以上を確保すること（マージン遵守）

---

## 11. `addPageBreakSection(slide, sectionNum, title)`

### 用途
中表紙（セクション区切り）スライドのコンテンツを追加する。  
`slide` 自体は呼び出し元で生成・背景色設定済みであること。

### シグネチャ
```js
function addPageBreakSection(slide, sectionNum, title)
```

| パラメータ | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `slide` | PptxGenJS Slide | ✅ | `D7DEE2` 背景設定済みのスライドオブジェクト |
| `sectionNum` | number | ✅ | セクション番号（1, 2, 3 ...） |
| `title` | string | ✅ | セクションタイトル（28pt Boldで表示） |

**戻り値**: なし（void）

### 内部実装
```js
function addPageBreakSection(slide, sectionNum, title) {
  const numStr = String(sectionNum).padStart(2, '0') + '.';

  slide.addText(
    [
      { text: numStr, options: { fontSize: 16, color: N2P_COLORS.black, fontFace: 'Noto Sans JP' } },
      { text: ' ' + title, options: { fontSize: 28, bold: true, color: N2P_COLORS.black, fontFace: 'Noto Sans JP' } },
    ],
    {
      x: 0.5, y: 2.0, w: 8.0, h: 0.8,
      valign: 'middle',
    }
  );
}
```

### 使用例
```js
function createSectionSlide(pptx, { sectionNum, title, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: N2P_COLORS.coverBg }; // 'D7DEE2'

  addPageBreakSection(slide, sectionNum, title);
  addLogoWhite(slide);
  addFooter(slide, pageNum);
}

// 呼び出し例
createSectionSlide(pptx, { sectionNum: 1, title: '要件のご確認', pageNum: 3 });
createSectionSlide(pptx, { sectionNum: 2, title: 'キャンペーンご提案', pageNum: 8 });
```

### 注意点
- セクション番号は `01.` `02.` の形式（先頭ゼロ付き）で自動フォーマットされる
- テキスト配置は**左寄せ**（表紙と異なり `align: 'center'` ではない）
- 背景色 `D7DEE2` の設定は呼び出し元で行うこと（この関数では行わない）

---

## 12. `defineN2pColors()`

### 用途
N2P_COLORS 定数オブジェクトを返す純粋関数。  
モジュール分割時など、定数を外部から注入したい場合に使用する。

### シグネチャ
```js
function defineN2pColors()
```

**パラメータ**: なし  
**戻り値**: `object` — N2P_COLORS と同一のキー・値のオブジェクト

### 内部実装
```js
function defineN2pColors() {
  return {
    black:       '111111',
    white:       'FCFCFC',
    darkGray:    '676A6D',
    midGray:     '929699',
    liteGray:    'E6EBED',
    coverBg:     'D7DEE2',
    bodyText:    '434343',
    footerText:  '999999',
    divider:     'CCCCCC',
    yellowDark:  'E8E800',
    yellowLight: 'F4F400',
    linkBlue:    '4285F4',
    teal:        '0097A7',
  };
}
```

### 使用例
```js
const colors = defineN2pColors();
slide.addText('テキスト', { color: colors.black }); // '111111'
```

### 注意点
- この関数はカラー定数の「単一の真実の源泉（single source of truth）」
- 返り値のキー名（`black`, `bodyText` 等）を変更しないこと
- ファイル先頭で `const N2P_COLORS = defineN2pColors();` とすることで全ファイル統一可

---

## 関数呼び出し順序の推奨パターン

本文スライドの標準的な呼び出し順序：

```js
// 1. スライド生成と背景設定
const slide = pptx.addSlide();
slide.background = { color: N2P_COLORS.white };

// 2. ロゴ（右上。必ず追加）
addLogoBlack(slide);

// 3. 大見出し（左ダッシュ線付き）
addH1(slide, '見出しテキスト');

// 4. 中見出し（任意。複数可）
addH2Dark(slide, '中見出し', 0.48, 0.7, 3.0);

// 5. 本文テキスト
addBody(slide, '本文テキスト', 0.48, 1.1, 8.8, 3.8);

// 6. フッター（最後に追加）
addFooter(slide, pageNum);
```

表紙・中表紙・エンドでの禁止事項：

| スライド種別 | addFooter | ページ番号 | addLogoBlack/White |
|------------|----------|-----------|-------------------|
| 表紙 | **禁止** | **禁止** | 禁止（代わりに透かし） |
| 中表紙 | **許可** | 許可 | addLogoWhite を使用 |
| エンドスライド | **禁止** | **禁止** | addLogoBlack（中央大） |

<!-- DONE: 3847 -->
