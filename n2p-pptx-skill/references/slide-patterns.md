# n2p提案資料 スライドパターン集

このドキュメントはn2p（NONAME Produce）提案資料で使う各スライドタイプの実装パターンを
pptxgenjsコード（v3系）で定義する。
design-rules.mdの基礎ルール（マージン、カラー、フォント、ロゴ、フッター）を前提とする。

**VI準拠カラー早見表**:
| 変数名 | HEX | 用途 |
|---|---|---|
| n2p_black | `#111111` | 主見出し・フッター線・ロゴ黒 |
| n2p_white | `#FCFCFC` | 背景白（純白#FFFFFFは使わない） |
| n2p_dark_gray | `#676A6D` | サブテキスト・強めアクセント |
| n2p_mid_gray | `#929699` | 中位アクセント |
| n2p_lite_gray | `#E6EBED` | 薄背景・差し色（表紙・中表紙背景） |
| n2p_cover_gray | `#D7DEE2` | 表紙・中表紙背景（実テンプレ値） |
| body_gray | `#434343` | 本文テキスト |
| footer_gray | `#999999` | フッター文字 |
| divider_gray | `#CCCCCC` | フッター軸線 |
| n2p_yellow_dark | `#E8E800` | 小面積文字ハイライト |
| n2p_yellow_light | `#F4F400` | 大面積背景ハイライト（≤10%） |

---

## 目次

1. [共通ヘルパー関数](#共通ヘルパー関数)
2. [表紙（プレーン）](#表紙プレーン)
3. [表紙（写真付き）](#表紙写真付き)
4. [目次スライド](#目次スライド)
5. [中表紙（セクション区切り）](#中表紙セクション区切り)
6. [本文スライド（基本）](#本文スライド基本)
7. [本文スライド（中見出しh2付き）](#本文スライド中見出しh2付き)
8. [2カラム事例（横長/縦長/上下重ね）](#2カラム事例横長縦長上下重ね)
9. [3カラム](#3カラム)
10. [非対称2カラム ★新規](#非対称2カラム)
11. [非対称3カラム ★新規](#非対称3カラム)
12. [デザイン提案_MV](#デザイン提案mv)
13. [デザイン提案_詳細説明](#デザイン提案詳細説明)
14. [デザイン提案_複数案比較](#デザイン提案複数案比較)
15. [コンセプトスライド](#コンセプトスライド)
16. [キャンペーンフロー（詳細）](#キャンペーンフロー詳細)
17. [キャンペーンフロー（全体）](#キャンペーンフロー全体)
18. [ユーザーフロー（シンプル）](#ユーザーフローシンプル)
19. [マトリックス図（2軸グリッド） ★新規](#マトリックス図2軸グリッド)
20. [タイムライン横長 ★新規](#タイムライン横長)
21. [囲みカラム（ボックスグリッド）](#囲みカラムボックスグリッド)
22. [費用・リスト](#費用リスト)
23. [スケジュール](#スケジュール)
24. [フロー図（ステップ式）](#フロー図ステップ式)
25. [LPワイヤーフレーム](#lpワイヤーフレーム)
26. [組織図](#組織図)
27. [会社概要](#会社概要)
28. [エンドスライド](#エンドスライド)
29. [標準的な資料構成](#標準的な資料構成)

---

## 共通ヘルパー関数

すべてのスライドで繰り返す要素を8つのヘルパー関数にまとめる。
各関数はVI準拠の色・座標・フォントを内包し、実装者が個別に数値を意識しなくてよい設計にする。

**フッター座標の導出根拠**:
- スライド幅: 10.0 inch / スライド高: 5.625 inch
- マージン左: 0.5cm ≈ 0.197in → 切り捨て 0.20in、実装値 0.28in（視覚余白を加味）
- マージン右端: 10.0 - 0.28 = 9.72in → 軸線終点
- 軸線 y: 5.625 - 0.345 = 5.28 / コピーライト y: 5.30

**ロゴ配置座標の導出根拠**:
- スライド幅10in、右マージン0.4in → ロゴ右端 = 9.6in
- ロゴ幅 0.9in → ロゴ左端x = 9.6 - 0.9 = 8.70in … 実装では余裕を持たせ x=8.9（ロゴ隔離エリア確保のため）
- ロゴ上端y: 0.15in（スライド上部から0.15in）

```js
// ===== パスと定数 =====
const LOGO_BLACK = 'assets/symbol_black.png'; // 白・淡色背景用
const LOGO_WHITE = 'assets/symbol_white.png'; // グレー・ダーク背景用

// VI準拠カラー定数（HEX文字列・#なし形式）
const C = {
  black:       '111111', // n2p_black: 主見出し・ロゴ黒
  white:       'FCFCFC', // n2p_white: 背景白
  cover_gray:  'D7DEE2', // 表紙・中表紙背景
  dark_gray:   '676A6D', // n2p_dark_gray: サブテキスト
  mid_gray:    '929699', // n2p_mid_gray
  lite_gray:   'E6EBED', // n2p_lite_gray
  body:        '434343', // 本文テキスト
  footer:      '999999', // フッター文字
  divider:     'CCCCCC', // フッター軸線
  yellow_d:    'E8E800', // 小面積ハイライト
  yellow_l:    'F4F400', // 大面積ハイライト
  link:        '4285F4', // リンク色
  h2_bg_dark:  '434343', // 中見出しダーク帯
};

// ===== ヘルパー1: 本文スライド右上ロゴ（白背景用）=====
// テンプレート参照: slide01〜54（本文全スライド）
function addLogoBlack(slide) {
  slide.addImage({
    path: LOGO_BLACK,
    x: 8.9, y: 0.15, w: 0.9, h: 0.30
    // 右上固定。ロゴ隔離エリア: ロゴ高さ0.30 × 0.5 = 0.15in 四方確保済
  });
}

// ===== ヘルパー2: グレー・ダーク背景用ロゴ（白ロゴ）=====
// テンプレート参照: 中表紙・表紙スライド
function addLogoWhite(slide) {
  slide.addImage({
    path: LOGO_WHITE,
    x: 8.9, y: 0.15, w: 0.9, h: 0.30
    // 写真上配置の場合: 明度#CCCCCC以上のエリアにのみ黒ロゴ、#959595以下に白ロゴ
  });
}

// ===== ヘルパー3: フッター（本文スライド用）=====
// テンプレート参照: 本文スライド全般（表紙・中表紙・エンドでは呼ばない）
// @param {object} slide - pptxgenjsスライドオブジェクト
// @param {number} pageNum - 1始まりのページ番号（整数）
// @param {string} [copyrightYear] - 省略時は現在年
function addFooter(slide, pageNum, copyrightYear) {
  const year = copyrightYear || new Date().getFullYear();
  // 軸線: x=0.28〜9.72（幅9.44）、y=5.28、0.5pt、#CCCCCC
  slide.addShape('line', {
    x: 0.28, y: 5.28,
    w: 9.44, h: 0.0,
    line: { color: C.divider, width: 0.5 }
  });
  // コピーライト: 8pt #999999 左寄せ
  slide.addText(`© ${year} NONAME Produce Inc.`, {
    x: 0.28, y: 5.30,
    w: 3.5, h: 0.25,
    fontSize: 8, color: C.footer, fontFace: 'Noto Sans JP'
  });
  // ページ番号: 9pt #999999 右寄せ
  slide.addText(String(pageNum), {
    x: 9.20, y: 5.30,
    w: 0.5, h: 0.25,
    fontSize: 9, color: C.footer, fontFace: 'Noto Sans JP',
    align: 'right'
  });
}

// ===== ヘルパー4: 大見出し（h1）＋左ダッシュ線 =====
// テンプレート参照: 本文スライド全般（slide-07〜54等）
// @param {object} slide
// @param {string} text - 見出しテキスト（推奨: 20文字以内。30文字超は fontSize を 13pt に下げる）
function addH1(slide, text) {
  // 水平ダッシュ線（左端から 0.05〜0.50in）
  slide.addShape('line', {
    x: 0.05, y: 0.35,
    w: 0.45, h: 0.0,
    line: { color: C.black, width: 1 }
  });
  // 見出しテキスト: 16pt Bold #111111
  const fs = text.length > 28 ? 13 : 16; // 長文フォールバック
  slide.addText(text, {
    x: 0.55, y: 0.14,
    w: 7.5, h: 0.42,
    fontSize: fs, bold: true, color: C.black,
    fontFace: 'Noto Sans JP',
    valign: 'middle',
    // 異常系: 長文タイトル（28文字超）→ fontSize 自動縮小で対応
    // 30文字超でも切れる場合はテキストを2行に分割して h: 0.6 に拡大すること
    shrinkText: false
  });
}

// ===== ヘルパー5: 中見出し バリエーション1（ダーク帯 #434343 + 白文字）=====
// テンプレート参照: slide-12〜20の中見出し
// @param {object} slide
// @param {string} text - 13pt Bold 白文字
// @param {number} x, y - 配置座標
// @param {number} [w=2.5] - 幅（デフォルト2.5in）
function addH2Dark(slide, text, x, y, w) {
  w = w || 2.5;
  slide.addShape('roundRect', {
    x: x, y: y, w: w, h: 0.35,
    fill: { color: C.h2_bg_dark }, // #434343
    rectRadius: 0.02
  });
  slide.addText(text, {
    x: x, y: y, w: w, h: 0.35,
    fontSize: 13, bold: true, color: C.white,
    fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
    // 異常系: 10文字超の場合は align:'left' + padding x+0.1 に変更
  });
}

// ===== ヘルパー6: 中見出し バリエーション2（ライトグレー帯 + 丸ドット）=====
// テンプレート参照: slide-22〜28の中見出し
// @param {object} slide
// @param {string} text - 13pt Bold #111111
// @param {number} x, y, [w=2.5]
function addH2Light(slide, text, x, y, w) {
  w = w || 2.5;
  // 左端ドット
  slide.addShape('ellipse', {
    x: x - 0.15, y: y + 0.12, w: 0.10, h: 0.10,
    fill: { color: C.black } // #111111
  });
  // ライトグレー帯
  slide.addShape('roundRect', {
    x: x, y: y, w: w, h: 0.35,
    fill: { color: C.lite_gray }, // #E6EBED
    rectRadius: 0.02
  });
  slide.addText(text, {
    x: x + 0.1, y: y, w: w - 0.1, h: 0.35,
    fontSize: 13, bold: true, color: C.black,
    fontFace: 'Noto Sans JP', valign: 'middle'
  });
}

// ===== ヘルパー7: 中見出し バリエーション3（グラデーション下線 + ドット）=====
// テンプレート参照: slide-30〜36の中見出し
// @param {object} slide
// @param {string} text - 13pt Bold #111111
// @param {number} x, y, [w=4.0]
function addH2Underline(slide, text, x, y, w) {
  w = w || 4.0;
  slide.addText(text, {
    x: x, y: y, w: w, h: 0.35,
    fontSize: 13, bold: true, color: C.black,
    fontFace: 'Noto Sans JP', valign: 'middle'
  });
  // 下線（左側から60%の長さ）
  slide.addShape('line', {
    x: x, y: y + 0.38,
    w: w * 0.6, h: 0.0,
    line: { color: C.divider, width: 1 } // #CCCCCC
  });
  // 右端ドット
  slide.addShape('ellipse', {
    x: x + w * 0.6, y: y + 0.34, w: 0.08, h: 0.08,
    fill: { color: C.divider } // #CCCCCC
  });
}

// ===== ヘルパー8: 本文テキスト（標準）=====
// テンプレート参照: 全本文スライド
// @param {object} slide
// @param {string|Array} text - 文字列 or pptxgenjs runs配列
// @param {number} x, y, w, h - 座標・寸法
// @param {object} [options] - 追加オプション（上書き可）
function addBody(slide, text, x, y, w, h, options) {
  const opts = Object.assign({
    x: x, y: y, w: w, h: h,
    fontSize: 11,
    color: C.body,       // #434343
    fontFace: 'Noto Sans JP',
    lineSpacingMultiple: 1.15,
    valign: 'top',
    paraSpaceAfter: 4
  }, options || {});
  slide.addText(text, opts);
  // 異常系: h に対してテキストが収まらない場合、fontSize を 10pt→9pt と段階的に縮小。
  // 最小 9pt 以下は禁止。それでも溢れる場合はテキスト自体を短縮する。
}
```

---

## 表紙（プレーン）

グレー背景（`#D7DEE2`）全面。全テキストを**水平中央・垂直中央やや上**に配置。
ロゴなし（右下に透かし）。フッターなし、ページ番号なし。

テンプレート参照: slide-03（テンプレート表紙）、TBS完成例 slide-01

```js
// @param {object} pptx - PptxGenJS インスタンス
// @param {object} params
//   clientName {string} - 宛名（例:「株式会社○○ 様」）
//   title      {string} - 提案タイトル（改行は\n）
//   date       {string} - 日付表記（例:「2026.04.30」）
//   year       {number} - コピーライト年（省略時は現在年）
function createCoverSlide(pptx, { clientName, title, date, year }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.cover_gray }; // #D7DEE2

  // ★ 全テキストは align:'center' で水平中央配置 ★

  // 宛名: 14pt Regular #111111
  slide.addText(clientName, {
    x: 1.5, y: 1.8, w: 7.0, h: 0.4,
    fontSize: 14, color: C.black,
    fontFace: 'Noto Sans JP',
    align: 'center', valign: 'middle'
    // 異常系: 宛名が20文字超の場合は fontSize: 12 に下げる
  });

  // メインタイトル: 28pt Bold #111111
  // 長文タイトル（15文字超）の場合は\nで改行し h: 1.8 に拡大
  slide.addText(title, {
    x: 0.5, y: 2.2, w: 9.0, h: 1.3,
    fontSize: 28, bold: true, color: C.black,
    fontFace: 'Noto Sans JP',
    align: 'center', valign: 'middle',
    lineSpacingMultiple: 1.2
  });

  // 日付: 11pt Regular #999999
  slide.addText(date, {
    x: 2.5, y: 3.6, w: 5.0, h: 0.35,
    fontSize: 11, color: C.footer, // #999999
    fontFace: 'Noto Sans JP',
    align: 'center'
  });

  // コピーライト: 9pt Regular #999999
  const copyrightYear = year || new Date().getFullYear();
  slide.addText(`© ${copyrightYear} NONAME Produce Inc.`, {
    x: 2.5, y: 4.0, w: 5.0, h: 0.3,
    fontSize: 9, color: C.footer,
    fontFace: 'Noto Sans JP',
    align: 'center'
  });

  // 右下透かしロゴ（symbol_white.png、透明度70%）
  slide.addImage({
    path: LOGO_WHITE,
    x: 6.2, y: 4.0, w: 3.8, h: 1.25,
    transparency: 70
  });

  // ★ フッターなし、ページ番号なし ★
  return slide;
}
```

**配置仕様まとめ**:
- 背景: `#D7DEE2` 全面
- 全テキスト: `align: 'center'`（左寄せ厳禁）
- 宛名: 14pt, #111111, y=1.8
- タイトル: 28pt Bold, #111111, y=2.2
- 日付: 11pt, #999999, y=3.6
- コピーライト: 9pt, #999999, y=4.0
- 透かしロゴ: 右下、transparency=70

---

## 表紙（写真付き）

全面写真にタイトルを重ねるバリエーション。カタログ・LPなど向き。
写真上では白ロゴを使う（明度#959595以下のエリアに配置）。

テンプレート参照: slide-04（写真付き表紙変形）

```js
// @param {object} pptx
// @param {object} params
//   title     {string} - タイトル
//   imagePath {string} - 写真パス
//   date      {string} - 日付表記
function createPhotoCoverSlide(pptx, { title, imagePath, date }) {
  const slide = pptx.addSlide();

  // 全面背景画像
  slide.addImage({
    path: imagePath,
    x: 0, y: 0, w: 10, h: 5.625,
    sizing: { type: 'cover' }
  });

  // 半透明ダークオーバーレイ（テキスト視認性確保）VI黒 #111111 を使用
  slide.addShape('rect', {
    x: 0, y: 0, w: 10, h: 5.625,
    fill: { color: '111111', transparency: 50 }
  });

  // タイトル: 28pt Bold #FCFCFC（中央配置）
  // 異常系: 長文（20文字超）は\nで2行化、h: 2.0 に拡大
  slide.addText(title, {
    x: 1.0, y: 1.8, w: 8.0, h: 1.5,
    fontSize: 28, bold: true, color: C.white, // #FCFCFC
    fontFace: 'Noto Sans JP',
    align: 'center', valign: 'middle'
  });

  // コピーライト（白）
  slide.addText(`© ${new Date().getFullYear()} NONAME Produce Inc.`, {
    x: 2.0, y: 3.5, w: 6.0, h: 0.3,
    fontSize: 9, color: C.white,
    fontFace: 'Noto Sans JP',
    align: 'center'
  });

  // 右下ロゴ（白、不透明）
  // 写真上に白ロゴ配置: 写真の暗度が#959595以下のエリアであること
  slide.addImage({
    path: LOGO_WHITE,
    x: 8.9, y: 0.15, w: 0.9, h: 0.30
  });

  return slide;
}
```

---

## 目次スライド

**左右2分割レイアウト**。左半分は白背景に「00. 目次」、右半分はライトグレー背景に番号付き項目。

テンプレート参照: slide-05（テンプレート目次）、TBS完成例 slide-02

```js
// @param {object} pptx
// @param {string[]} items - 目次項目の配列（最大8件推奨）
// @param {number} pageNum - ページ番号
function createTocSlide(pptx, items, pageNum) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white }; // #FCFCFC

  // 右半分グレー背景（x: 5.0〜10.0）VI n2p_lite_gray
  slide.addShape('rect', {
    x: 5.0, y: 0, w: 5.0, h: 5.625,
    fill: { color: 'E6EBED' }
  });

  // 右上ロゴ（グレーエリア上に黒ロゴ）
  addLogoBlack(slide);

  // 左側: 「00.」+ 「目次」を垂直中央に
  slide.addText('00.', {
    x: 0.5, y: 2.3, w: 0.6, h: 0.5,
    fontSize: 14, color: C.black,
    fontFace: 'Noto Sans JP',
    valign: 'bottom'
  });
  slide.addText('目次', {
    x: 1.1, y: 2.1, w: 3.0, h: 0.7,
    fontSize: 32, bold: true, color: C.black,
    fontFace: 'Noto Sans JP',
    valign: 'middle'
  });

  // 右側: 番号付き目次項目
  // 項目数に応じて開始Yを調整して垂直中央寄りにする
  const totalHeight = items.length * 0.55;
  const startY = Math.max(1.0, (5.625 - totalHeight) / 2 - 0.3);
  items.forEach((item, i) => {
    const num = String(i + 1).padStart(2, '0');
    slide.addText(`${num}. ${item}`, {
      x: 5.5, y: startY + i * 0.55, w: 4.0, h: 0.45,
      fontSize: 14, bold: true, color: C.black,
      fontFace: 'Noto Sans JP',
      valign: 'middle'
      // 異常系: 項目名が20文字超の場合は fontSize: 12 に下げ、h: 0.65 に拡大
    });
  });

  addFooter(slide, pageNum);
  return slide;
}
```

**配置仕様**:
- 左: 白背景、「00.」14pt + 「目次」32pt Bold 垂直中央
- 右: `#F5F5F5`背景、「01. ○○」14pt Bold 垂直中央付近
- フッター: 通常フッター付き

---

## 中表紙（セクション区切り）

グレー背景（`#D7DEE2`）全面。セクション番号+タイトルを**左寄せ・垂直中央やや下**に大きく配置。

テンプレート参照: slide-06/11/16/21/47、TBS完成例 slide-03

```js
// @param {object} pptx
// @param {object} params
//   sectionNum {number} - セクション番号（1始まり）
//   title      {string} - セクションタイトル（推奨: 15文字以内）
//   pageNum    {number}
function createSectionSlide(pptx, { sectionNum, title, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.cover_gray }; // #D7DEE2

  // セクション番号 + タイトルを左寄せ、垂直中央やや下
  // 長いタイトルは\nで2行化し y を 1.7 に上げる
  const numStr = String(sectionNum).padStart(2, '0') + '.';
  slide.addText([
    {
      text: numStr,
      options: {
        fontSize: 16, color: C.black, fontFace: 'Noto Sans JP'
      }
    },
    {
      text: ' ' + title,
      options: {
        fontSize: 28, bold: true, color: C.black, fontFace: 'Noto Sans JP'
      }
    }
  ], {
    x: 0.5, y: 2.0, w: 8.0, h: 0.8,
    valign: 'middle'
    // 異常系: タイトルが20文字超の場合は fontSize: 22 に下げ h: 1.2 に拡大
  });

  // グレー背景なので白ロゴ
  addLogoWhite(slide);

  // フッター（軸線+コピーライト+ページ番号あり）
  addFooter(slide, pageNum);

  return slide;
}
```

---

## 本文スライド（基本）

白背景。大見出し（左線付き）＋本文。最も頻出するパターン。

テンプレート参照: slide-07〜10（基本本文スライド群）

```js
// @param {object} pptx
// @param {object} params
//   heading    {string} - 大見出し（推奨: 20文字以内）
//   subHeading {string} - 小見出し（任意）
//   bodyText   {string} - 本文テキスト（11pt, #434343, 行間1.15）
//   pageNum    {number}
function createContentSlide(pptx, { heading, subHeading, bodyText, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  let contentY = 0.7;
  if (subHeading) {
    slide.addText(subHeading, {
      x: 0.48, y: contentY, w: 8.5, h: 0.35,
      fontSize: 11, color: C.body, // #434343
      fontFace: 'Noto Sans JP'
    });
    contentY += 0.4;
  }

  // 本文: 11pt #434343 行間1.15
  addBody(slide, bodyText, 0.48, contentY, 8.8, 4.2 - contentY);

  addFooter(slide, pageNum);
  return slide;
}
```

---

## 本文スライド（中見出しh2付き）

白背景。大見出し(h1) + 複数の中見出し(h2) + 本文。
h2はバリエーション1〜3から選択する。

テンプレート参照: slide-12〜36（h2バリエーション使用スライド）

```js
// @param {object} pptx
// @param {object} params
//   heading  {string}  - 大見出し
//   sections {Array}   - [{ h2Style, title, body }]
//     h2Style: 'dark'|'light'|'underline'（省略時は'dark'）
//   pageNum  {number}
function createContentWithH2(pptx, { heading, sections, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  let y = 0.7;
  sections.forEach(section => {
    // 中見出し（バリエーション選択）
    if (section.h2Style === 'light') {
      addH2Light(slide, section.title, 0.48, y, 3.5);
    } else if (section.h2Style === 'underline') {
      addH2Underline(slide, section.title, 0.48, y, 5.0);
    } else {
      addH2Dark(slide, section.title, 0.48, y, 3.0); // default: dark
    }
    y += 0.45;

    // 本文: 11pt #434343 行間1.15
    addBody(slide, section.body, 0.48, y, 8.8, 0.8);
    y += 0.9;

    // 異常系: セクションが3つ以上の場合は bodyH を 0.6 に縮める
    // 合計高さが4.5inを超える場合はセクションを別スライドに分割すること
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## 2カラム事例（横長/縦長/上下重ね）

左に画像、右にテキスト。事例紹介に頻出。3バリエーション。

テンプレート参照: slide-23〜34（2カラム事例スライド群）

### バリエーション1: 横長画像（PC画面など）

```js
// @param {object} pptx
// @param {object} params
//   heading   {string}   - 大見出し
//   imagePath {string}   - 画像パス
//   caseTitle {string}   - 事例タイトル（13pt Bold）
//   caseUrl   {string}   - 引用元URL（任意）
//   features  {Array}    - [{ label, text }]
//   pageNum   {number}
function createCaseStudy2ColLandscape(pptx, {
  heading, imagePath, caseTitle, caseUrl, features, pageNum
}) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // 左: 横長画像
  slide.addImage({
    path: imagePath,
    x: 0.34, y: 0.7, w: 4.8, h: 3.2,
    sizing: { type: 'cover' }
  });

  // 右: 事例タイトル 13pt Bold #111111
  slide.addText(caseTitle, {
    x: 5.4, y: 0.7, w: 4.2, h: 0.35,
    fontSize: 13, bold: true, color: C.black,
    fontFace: 'Noto Sans JP'
    // 異常系: タイトル25文字超は fontSize: 11 に下げる
  });

  // 引用元URL（リンク色 #4285F4）
  if (caseUrl) {
    slide.addText(caseUrl, {
      x: 5.4, y: 1.05, w: 4.2, h: 0.25,
      fontSize: 9, color: C.link, // #4285F4
      fontFace: 'Noto Sans JP',
      hyperlink: { url: caseUrl }
    });
  }

  // 特徴セクション
  let fy = 1.5;
  features.forEach(f => {
    slide.addText(f.label, {
      x: 5.4, y: fy, w: 4.2, h: 0.3,
      fontSize: 11, bold: true, color: C.black,
      fontFace: 'Noto Sans JP'
    });
    addBody(slide, f.text, 5.4, fy + 0.3, 4.2, 0.6);
    fy += 1.0;
  });

  addFooter(slide, pageNum);
  return slide;
}
```

### バリエーション2: 縦長画像（SP画面など）

```js
function createCaseStudy2ColPortrait(pptx, {
  heading, imagePath, caseTitle, caseUrl, features, pageNum
}) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // 左: 縦長画像（スマホスクリーンショット等）
  slide.addImage({
    path: imagePath,
    x: 0.34, y: 0.7, w: 3.5, h: 4.2,
    sizing: { type: 'cover' }
  });

  // 右: テキストエリア（x: 4.2 から）
  slide.addText(caseTitle, {
    x: 4.2, y: 0.7, w: 5.3, h: 0.35,
    fontSize: 13, bold: true, color: C.black,
    fontFace: 'Noto Sans JP'
  });
  if (caseUrl) {
    slide.addText(caseUrl, {
      x: 4.2, y: 1.05, w: 5.3, h: 0.25,
      fontSize: 9, color: C.link,
      fontFace: 'Noto Sans JP',
      hyperlink: { url: caseUrl }
    });
  }
  let fy = 1.5;
  features.forEach(f => {
    slide.addText(f.label, {
      x: 4.2, y: fy, w: 5.3, h: 0.3,
      fontSize: 11, bold: true, color: C.black,
      fontFace: 'Noto Sans JP'
    });
    addBody(slide, f.text, 4.2, fy + 0.3, 5.3, 0.6);
    fy += 1.0;
  });

  addFooter(slide, pageNum);
  return slide;
}
```

### バリエーション3: 画像上下配置（2画像）

```js
function createCaseStudy2ColStacked(pptx, {
  heading, image1Path, image2Path, caseTitle, features, pageNum
}) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // 左上: 画像1
  slide.addImage({
    path: image1Path,
    x: 0.34, y: 0.7, w: 4.0, h: 2.0,
    sizing: { type: 'cover' }
  });
  // 左下: 画像2
  slide.addImage({
    path: image2Path,
    x: 0.34, y: 2.8, w: 4.0, h: 2.0,
    sizing: { type: 'cover' }
  });

  // 右: テキストエリア（x: 4.6 から）
  slide.addText(caseTitle, {
    x: 4.6, y: 0.7, w: 5.0, h: 0.35,
    fontSize: 13, bold: true, color: C.black,
    fontFace: 'Noto Sans JP'
  });
  let fy = 1.2;
  (features || []).forEach(f => {
    slide.addText(f.label, {
      x: 4.6, y: fy, w: 5.0, h: 0.3,
      fontSize: 11, bold: true, color: C.black,
      fontFace: 'Noto Sans JP'
    });
    addBody(slide, f.text, 4.6, fy + 0.3, 5.0, 0.6);
    fy += 1.0;
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## 3カラム

3つの項目を横並びに。画像+テキストの組み合わせ。等分割（各3.1in幅）。

テンプレート参照: slide-35〜40（3カラムスライド群）

```js
// @param {object} pptx
// @param {object} params
//   heading {string}  - 大見出し
//   columns {Array}   - [{ title, imagePath?, text }] 最大3件
//   pageNum {number}
function create3ColumnSlide(pptx, { heading, columns, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  const colW = 2.8;
  const gap = 0.35;
  const startX = 0.34;

  columns.forEach((col, i) => {
    const x = startX + i * (colW + gap);

    // 小見出し: 11pt Bold #111111
    slide.addText(col.title, {
      x: x, y: 0.8, w: colW, h: 0.3,
      fontSize: 11, bold: true, color: C.black,
      fontFace: 'Noto Sans JP'
      // 異常系: タイトル15文字超は fontSize: 10 に下げる
    });

    // 画像（任意）
    if (col.imagePath) {
      slide.addImage({
        path: col.imagePath,
        x: x, y: 1.2, w: colW, h: 2.0,
        sizing: { type: 'contain' }
      });
    }

    // 本文: 11pt #434343 行間1.15
    addBody(slide, col.text, x, 3.4, colW, 1.4);
  });

  // ポイント:
  // - 各カラム間ギャップ 0.35in（約0.9cm）
  // - 境界が分かりにくい場合はライトグレー(#E6EBED)帯を座布団として敷いてよい
  // - カラム余白を均等にしてどの部分が何の説明かを明確にする

  addFooter(slide, pageNum);
  return slide;
}
```

---

## 非対称2カラム

左右の幅比率を変えた2カラムレイアウト。
監査レポート #8 で「非対称レイアウト 3〜4パターン追加」として優先度High指定。

テンプレート参照: evals ケース #6（非対称レイアウト・可変カラム）

### パターンA: 左狭(20%)・右広(80%)

用途: 左にラベル・カテゴリ、右にメイン内容

```js
// スライド幅 9.32in（マージン除く）での計算:
// 左幅 = 9.32 × 0.20 = 1.86in ≈ 1.9in
// 右幅 = 9.32 × 0.80 = 7.46in ≈ 7.2in（カラム間ギャップ 0.22in を引く）
// カラム間ギャップ: 最低 1.0cm ≈ 0.39in（本実装では 0.3in）
function createAsymmetric2ColNarrowLeft(pptx, { heading, label, mainContent, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  const leftX  = 0.34;
  const leftW  = 1.9;
  const gap    = 0.3;
  const rightX = leftX + leftW + gap; // 2.54
  const rightW = 7.12;

  // 左カラム背景（#E6EBED で区分を可視化）
  slide.addShape('rect', {
    x: leftX, y: 0.7, w: leftW, h: 4.4,
    fill: { color: C.lite_gray } // #E6EBED
  });

  // 左ラベルテキスト（縦書き的に中央配置）
  slide.addText(label, {
    x: leftX + 0.1, y: 1.5, w: leftW - 0.2, h: 2.5,
    fontSize: 11, bold: true, color: C.black,
    fontFace: 'Noto Sans JP',
    align: 'center', valign: 'middle',
    lineSpacingMultiple: 1.5
  });

  // 右カラム: メインコンテンツ（11pt #434343 行間1.15）
  addBody(slide, mainContent, rightX, 0.7, rightW, 4.4);
  // 異常系: mainContentが長文（500文字超）の場合は fontSize: 10 に下げる

  addFooter(slide, pageNum);
  return slide;
}
```

### パターンB: 左広(70%)・右狭(30%)

用途: 左にメイン図表、右にサイドバー注釈

```js
// 左幅 = 9.32 × 0.70 = 6.52in ≈ 6.3in
// 右幅 = 9.32 × 0.30 = 2.80in ≈ 2.7in
// カラム間ギャップ: 0.32in
function createAsymmetric2ColNarrowRight(pptx, { heading, mainContent, sidebar, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  const leftX  = 0.34;
  const leftW  = 6.3;
  const gap    = 0.32;
  const rightX = leftX + leftW + gap; // 6.96
  const rightW = 2.7;

  // 左カラム: メインコンテンツ（画像 or テキスト）
  if (mainContent.imagePath) {
    slide.addImage({
      path: mainContent.imagePath,
      x: leftX, y: 0.7, w: leftW, h: 4.4,
      sizing: { type: 'contain' }
    });
  } else {
    addBody(slide, mainContent.text, leftX, 0.7, leftW, 4.4);
  }

  // 右カラム: サイドバー（背景あり）
  slide.addShape('rect', {
    x: rightX, y: 0.7, w: rightW, h: 4.4,
    fill: { color: C.lite_gray } // #E6EBED
  });
  if (sidebar.title) {
    slide.addText(sidebar.title, {
      x: rightX + 0.1, y: 0.8, w: rightW - 0.2, h: 0.35,
      fontSize: 11, bold: true, color: C.black,
      fontFace: 'Noto Sans JP'
    });
  }
  addBody(slide, sidebar.text, rightX + 0.1, 1.2, rightW - 0.2, 3.7);

  addFooter(slide, pageNum);
  return slide;
}
```

---

## 非対称3カラム

3カラムを15%/50%/35%の比率で分割。左にカテゴリ、中にメイン、右に補足。
監査レポート #8 で明示的に「左15%・中50%・右35%」が指定されたパターン。

テンプレート参照: evals ケース #6（3カラム 15%-50%-35%）

```js
// 有効幅 9.32in（0.34〜9.66）での計算:
// 左幅  = 9.32 × 0.15 = 1.40in
// 中幅  = 9.32 × 0.50 = 4.66in
// 右幅  = 9.32 × 0.35 = 3.26in
// 合計 = 9.32in、カラム間ギャップ2個 × 0.14in = 0.28in を引くため
// 実際の列幅: 左 1.26in / 中 4.52in / 右 3.12in（ギャップ 0.16in × 2）
function createAsymmetric3Col(pptx, { heading, leftLabel, centerContent, rightSidebar, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  const startX = 0.34;
  const gap    = 0.16;
  const leftW  = 1.26;
  const centerW= 4.52;
  const rightW = 3.12;

  const centerX = startX + leftW + gap; // 0.34 + 1.26 + 0.16 = 1.76
  const rightX  = centerX + centerW + gap; // 1.76 + 4.52 + 0.16 = 6.44

  // 左カラム（カテゴリラベル背景 #E6EBED）
  slide.addShape('rect', {
    x: startX, y: 0.7, w: leftW, h: 4.4,
    fill: { color: C.lite_gray }
  });
  slide.addText(leftLabel, {
    x: startX + 0.05, y: 0.7, w: leftW - 0.1, h: 4.4,
    fontSize: 10, bold: true, color: C.black,
    fontFace: 'Noto Sans JP',
    align: 'center', valign: 'middle',
    lineSpacingMultiple: 1.5
    // 異常系: ラベルが8文字超の場合は fontSize: 9 に下げて lineSpacingMultiple: 2.0 で縦方向に広げる
  });

  // 中カラム: メインコンテンツ
  if (centerContent.imagePath) {
    slide.addImage({
      path: centerContent.imagePath,
      x: centerX, y: 0.7, w: centerW, h: 4.4,
      sizing: { type: 'contain' }
    });
  } else {
    addBody(slide, centerContent.text, centerX, 0.7, centerW, 4.4);
  }

  // 右カラム: 補足・サイドバー（VI n2p_lite_gray）
  slide.addShape('rect', {
    x: rightX, y: 0.7, w: rightW, h: 4.4,
    fill: { color: 'E6EBED' }
  });
  if (rightSidebar.title) {
    slide.addText(rightSidebar.title, {
      x: rightX + 0.1, y: 0.8, w: rightW - 0.2, h: 0.35,
      fontSize: 11, bold: true, color: C.black,
      fontFace: 'Noto Sans JP'
    });
  }
  addBody(slide, rightSidebar.text, rightX + 0.1, 1.25, rightW - 0.2, 3.7);

  addFooter(slide, pageNum);
  return slide;
}
```

---

## デザイン提案_MV

メインビジュアル（MV）を大きく表示し、下にコンセプト説明。

テンプレート参照: slide-41（デザイン提案_MV）

```js
// @param {object} pptx
// @param {object} params
//   heading     {string} - 大見出し（例:「デザイン提案 ／ MV」）
//   mvImagePath {string} - MVイメージパス
//   conceptText {string} - コンセプト説明（11pt, #434343）
//   pageNum     {number}
function createDesignMVSlide(pptx, { heading, mvImagePath, conceptText, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // MV画像: 大きく中央に配置
  slide.addImage({
    path: mvImagePath,
    x: 0.7, y: 0.7, w: 8.6, h: 3.8,
    sizing: { type: 'contain' }
    // 異常系: 縦長画像は type: 'cover' に変更し y: 0.7, h: 4.2 に拡大
  });

  // コンセプト説明: 11pt #434343 行間1.15
  addBody(slide, conceptText, 0.48, 4.6, 8.5, 0.5);

  addFooter(slide, pageNum);
  return slide;
}
```

---

## デザイン提案_詳細説明

中央に画像、四隅から引き出し線で注釈を付けるパターン。

テンプレート参照: slide-42（デザイン提案_詳細説明）

```js
// @param {object} pptx
// @param {object} params
//   heading     {string} - 大見出し
//   imagePath   {string} - 詳細説明対象画像
//   annotations {Array}  - [{ text, position: 'topLeft'|'topRight'|'bottomLeft'|'bottomRight' }]
//   pageNum     {number}
function createDesignDetailSlide(pptx, { heading, imagePath, annotations, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // 中央画像
  slide.addImage({
    path: imagePath,
    x: 2.0, y: 0.7, w: 6.0, h: 4.0,
    sizing: { type: 'contain' }
  });

  // 注釈: 4隅 + 引き出し線 + テキスト
  const positions = {
    topLeft:     { textX: 0.2, textY: 0.7,  dotX: 2.2, dotY: 1.2 },
    topRight:    { textX: 8.0, textY: 0.7,  dotX: 7.8, dotY: 1.2 },
    bottomLeft:  { textX: 0.2, textY: 4.0,  dotX: 2.2, dotY: 3.8 },
    bottomRight: { textX: 8.0, textY: 4.0,  dotX: 7.8, dotY: 3.8 }
  };

  annotations.forEach(ann => {
    const pos = positions[ann.position];
    // ドット (#999999)
    slide.addShape('ellipse', {
      x: pos.dotX, y: pos.dotY, w: 0.08, h: 0.08,
      fill: { color: C.mid_gray } // #929699
    });
    // 引き出し線 0.5pt #929699
    slide.addShape('line', {
      x: pos.dotX, y: pos.dotY,
      w: pos.textX - pos.dotX, h: pos.textY - pos.dotY,
      line: { color: C.mid_gray, width: 0.5 }
    });
    // テキスト: 9pt #434343 行間1.15
    slide.addText(ann.text, {
      x: pos.textX - 0.1, y: pos.textY, w: 1.8, h: 0.8,
      fontSize: 9, color: C.body,
      fontFace: 'Noto Sans JP',
      lineSpacingMultiple: 1.15
      // 異常系: 注釈テキスト50文字超は w: 2.0 に拡大し textX を0.1 内側に移動
    });
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## デザイン提案_複数案比較

A案/B案/C案を横並びに。3カラムで画像を大きく表示。

テンプレート参照: slide-43（デザイン提案_複数案比較）

```js
// @param {object} pptx
// @param {object} params
//   heading   {string} - 大見出し（例:「複数案 ／ 一覧」）
//   proposals {Array}  - [{ label: 'A', imagePath? }] 最大3件
//   pageNum   {number}
function createDesignComparisonSlide(pptx, { heading, proposals, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  const colW   = 2.8;
  const gap    = 0.3;
  const startX = 0.5;

  proposals.forEach((p, i) => {
    const x = startX + i * (colW + gap);

    // ラベル（「A案」「B案」「C案」）
    slide.addText(`${p.label}案`, {
      x: x, y: 0.55, w: 0.5, h: 0.4,
      fontSize: 11, color: C.black,
      fontFace: 'Noto Sans JP'
    });

    // 画像エリア（グレー背景 + 画像）
    slide.addShape('rect', {
      x: x, y: 0.6, w: colW, h: 4.2,
      fill: { color: C.cover_gray } // #D7DEE2
    });
    if (p.imagePath) {
      slide.addImage({
        path: p.imagePath,
        x: x, y: 0.6, w: colW, h: 4.2,
        sizing: { type: 'contain' }
      });
    }
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## コンセプトスライド

コンセプトのみを大きく中央に表示するインパクトスライド。

テンプレート参照: slide-44（コンセプトスライド）

```js
// @param {object} pptx
// @param {object} params
//   mainText {string} - メインコンセプト（32pt Bold、推奨: 15文字以内）
//   subText  {string} - サブテキスト（13pt, 任意）
//   pageNum  {number}
function createConceptSlide(pptx, { mainText, subText, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addLogoBlack(slide);

  // メインコンセプト: 32pt Bold #111111 中央配置
  // 異常系: 20文字超は fontSize: 24 に下げ、lineSpacingMultiple: 1.5 で視認性確保
  slide.addText(mainText, {
    x: 1.0, y: 1.5, w: 8.0, h: 1.5,
    fontSize: 32, bold: true, color: C.black,
    fontFace: 'Noto Sans JP',
    align: 'center', valign: 'middle',
    lineSpacingMultiple: 1.3
  });

  // サブテキスト: 13pt #676A6D 中央配置
  if (subText) {
    slide.addText(subText, {
      x: 1.5, y: 3.2, w: 7.0, h: 0.8,
      fontSize: 13, color: C.dark_gray, // #676A6D
      fontFace: 'Noto Sans JP',
      align: 'center', valign: 'top',
      lineSpacingMultiple: 1.5
    });
  }

  addFooter(slide, pageNum);
  return slide;
}
```

---

## キャンペーンフロー（詳細）

スマホ型フレーム内にSNS投稿UIを再現するパターン。3ステップ横並び。
キャンペーン固有アクセントカラーを使える数少ないスライドタイプ（全体の10%以内）。

テンプレート参照: slide-45（キャンペーンフロー詳細）

```js
// @param {object} pptx
// @param {object} params
//   heading     {string} - 大見出し
//   accentColor {string} - キャンペーン色HEX（省略時は '00BCD4'）
//   steps       {Array}  - [{ title, accountName?, postText?, description? }]
//   pageNum     {number}
function createCampaignFlowDetail(pptx, { heading, accentColor, steps, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  accentColor = accentColor || '00BCD4';
  const colW   = 2.6;
  const gap    = 0.4;
  const startX = 0.5;

  steps.forEach((step, i) => {
    const x = startX + i * (colW + gap);

    // ステップタイトル: 11pt Bold #111111
    slide.addText(step.title, {
      x: x, y: 0.7, w: colW, h: 0.3,
      fontSize: 11, bold: true, color: C.black,
      fontFace: 'Noto Sans JP', align: 'center'
    });

    // スマホフレーム（角丸長方形）1pt #CCCCCC
    slide.addShape('roundRect', {
      x: x + 0.2, y: 1.1, w: colW - 0.4, h: 3.0,
      line: { color: C.divider, width: 1 },
      rectRadius: 0.15
    });

    // アイコン丸（アクセントカラー）
    slide.addShape('ellipse', {
      x: x + 0.4, y: 1.3, w: 0.3, h: 0.3,
      fill: { color: accentColor }
    });
    slide.addText(step.accountName || '公式アカウント', {
      x: x + 0.8, y: 1.3, w: colW - 1.2, h: 0.3,
      fontSize: 9, color: C.body, // #434343
      fontFace: 'Noto Sans JP', valign: 'middle'
    });

    // 投稿テキスト
    if (step.postText) {
      slide.addText(step.postText, {
        x: x + 0.4, y: 1.7, w: colW - 0.8, h: 0.8,
        fontSize: 8, color: C.body,
        fontFace: 'Noto Sans JP',
        lineSpacingMultiple: 1.2
      });
    }

    // 画像プレースホルダー（VI n2p_lite_gray）
    slide.addShape('rect', {
      x: x + 0.4, y: 2.6, w: colW - 0.8, h: 1.0,
      fill: { color: 'E6EBED' }
    });

    // ステップ間矢印（最後以外）1pt #CCCCCC
    if (i < steps.length - 1) {
      slide.addShape('line', {
        x: x + colW + 0.05, y: 2.5,
        w: gap - 0.1, h: 0,
        line: { color: C.divider, width: 1, endArrowType: 'triangle' }
      });
    }

    // 下の説明テキスト: 11pt #434343
    if (step.description) {
      addBody(slide, step.description, x, 4.3, colW, 0.7);
    }
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## キャンペーンフロー（全体）

マストバイ等の全体フロー。横並びボックスにアイコン+テキスト。

テンプレート参照: slide-46（キャンペーンフロー全体）

```js
// @param {object} pptx
// @param {object} params
//   heading     {string} - 大見出し
//   accentColor {string} - キャンペーン固有色（省略時: '00BCD4'）
//   steps       {Array}  - [{ title, action?, description }]
//   pageNum     {number}
function createCampaignFlowOverview(pptx, { heading, accentColor, steps, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  accentColor = accentColor || '00BCD4';
  const stepCount = steps.length;
  const totalW    = 9.0;
  const colW      = totalW / stepCount - 0.3;
  const gap       = 0.3;

  steps.forEach((step, i) => {
    const x = 0.5 + i * (colW + gap);

    // スマホフレーム: 0.5pt #CCCCCC
    slide.addShape('roundRect', {
      x: x, y: 0.8, w: colW, h: 3.2,
      line: { color: C.divider, width: 0.5 },
      rectRadius: 0.15,
      fill: { color: C.white }
    });

    // アイコン（アクセントカラー丸）
    slide.addShape('ellipse', {
      x: x + colW / 2 - 0.25, y: 1.0, w: 0.5, h: 0.5,
      fill: { color: accentColor }
    });

    // ステップ名: 9pt #434343
    slide.addText(step.title, {
      x: x, y: 1.6, w: colW, h: 0.3,
      fontSize: 9, color: C.body,
      fontFace: 'Noto Sans JP', align: 'center'
    });

    // アクションボタン（任意）
    if (step.action) {
      slide.addShape('roundRect', {
        x: x + 0.3, y: 2.0, w: colW - 0.6, h: 0.3,
        fill: { color: accentColor },
        rectRadius: 0.15
      });
      slide.addText(step.action, {
        x: x + 0.3, y: 2.0, w: colW - 0.6, h: 0.3,
        fontSize: 9, bold: true, color: C.white,
        fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
      });
    }

    // 矢印（最後以外）: 1pt #CCCCCC
    if (i < stepCount - 1) {
      slide.addShape('line', {
        x: x + colW + 0.02, y: 2.2,
        w: gap - 0.04, h: 0,
        line: { color: C.divider, width: 1, endArrowType: 'triangle' }
      });
    }

    // 下部説明: 9pt #434343 中央揃え
    addBody(slide, step.description, x, 4.2, colW, 0.8, {
      fontSize: 9, align: 'center'
    });
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## ユーザーフロー（シンプル）

矢印型（シェブロン）で3ステップを横に並べるシンプルなフロー。

テンプレート参照: slide-47（ユーザーフローシンプル）

```js
// @param {object} pptx
// @param {object} params
//   heading   {string} - 大見出し
//   flowLabel {string} - フローラベル（任意、ダーク帯で表示）
//   steps     {Array}  - [{ text, iconPath? }]
//   pageNum   {number}
function createUserFlowSimple(pptx, { heading, flowLabel, steps, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // フローラベル（ダーク帯）
  if (flowLabel) {
    addH2Dark(slide, flowLabel, 0.48, 0.7, 3.5);
  }

  const stepW  = 2.8;
  const gap    = 0.15;
  const startX = 0.5;
  const startY = 1.2;

  steps.forEach((step, i) => {
    const x = startX + i * (stepW + gap);

    // シェブロン背景（ライトグレー #E6EBED）
    slide.addShape('chevron', {
      x: x, y: startY, w: stepW, h: 1.5,
      fill: { color: C.lite_gray } // #E6EBED
    });

    // アイコン（任意）
    if (step.iconPath) {
      slide.addImage({
        path: step.iconPath,
        x: x + stepW / 2 - 0.4, y: startY + 0.15, w: 0.8, h: 0.8
      });
    }

    // ステップテキスト: 9pt #434343
    slide.addText(step.text, {
      x: x + 0.2, y: startY + 1.0, w: stepW - 0.4, h: 0.4,
      fontSize: 9, color: C.body,
      fontFace: 'Noto Sans JP', align: 'center'
    });
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## マトリックス図（2軸グリッド）

縦軸・横軸の2軸で施策・要素を配置する評価マトリックス。
重要度×実現可能性、インパクト×コスト等に応用可能。

テンプレート参照: evals ケース #5（高度な図表パターン）

```js
// @param {object} pptx
// @param {object} params
//   heading  {string} - 大見出し
//   xLabel   {string} - 横軸ラベル（例:「実現可能性」）
//   yLabel   {string} - 縦軸ラベル（例:「重要度」）
//   xLow     {string} - 横軸低端（例:「低」）
//   xHigh    {string} - 横軸高端（例:「高」）
//   yLow     {string} - 縦軸低端（例:「低」）
//   yHigh    {string} - 縦軸高端（例:「高」）
//   items    {Array}  - [{ label, x: 0〜1, y: 0〜1, highlight? }]
//     x, y は 0（低）〜1（高）の正規化座標
//   pageNum  {number}
function createMatrixSlide(pptx, {
  heading, xLabel, yLabel, xLow, xHigh, yLow, yHigh, items, pageNum
}) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // グリッドエリアの定義
  const gridX = 1.2;   // グリッド左端
  const gridY = 0.75;  // グリッド上端
  const gridW = 7.5;   // グリッド幅
  const gridH = 4.0;   // グリッド高さ

  // グリッド外枠
  slide.addShape('rect', {
    x: gridX, y: gridY, w: gridW, h: gridH,
    line: { color: C.divider, width: 0.5 }, // #CCCCCC
    fill: { color: C.white }
  });

  // 4象限の区切り線（十字）: 0.5pt #CCCCCC
  // 縦中心線
  slide.addShape('line', {
    x: gridX + gridW / 2, y: gridY,
    w: 0, h: gridH,
    line: { color: C.divider, width: 0.5 }
  });
  // 横中心線
  slide.addShape('line', {
    x: gridX, y: gridY + gridH / 2,
    w: gridW, h: 0,
    line: { color: C.divider, width: 0.5 }
  });

  // 4象限ラベル（薄いグレーテキスト）
  const quadrants = [
    { text: '重要度高\n実現可能性高', x: gridX + gridW / 2 + 0.1, y: gridY + 0.05 },
    { text: '重要度高\n実現可能性低', x: gridX + 0.1, y: gridY + 0.05 },
    { text: '重要度低\n実現可能性高', x: gridX + gridW / 2 + 0.1, y: gridY + gridH / 2 + 0.05 },
    { text: '重要度低\n実現可能性低', x: gridX + 0.1, y: gridY + gridH / 2 + 0.05 }
  ];
  quadrants.forEach(q => {
    slide.addText(q.text, {
      x: q.x, y: q.y, w: 3.5, h: 0.45,
      fontSize: 8, color: C.mid_gray, // #929699
      fontFace: 'Noto Sans JP',
      lineSpacingMultiple: 1.2
    });
  });

  // 横軸ラベル
  slide.addText(xLow, {
    x: gridX - 0.05, y: gridY + gridH + 0.05, w: 0.6, h: 0.3,
    fontSize: 9, color: C.body, fontFace: 'Noto Sans JP', align: 'center'
  });
  slide.addText(xHigh, {
    x: gridX + gridW - 0.55, y: gridY + gridH + 0.05, w: 0.6, h: 0.3,
    fontSize: 9, color: C.body, fontFace: 'Noto Sans JP', align: 'center'
  });
  slide.addText(xLabel, {
    x: gridX, y: gridY + gridH + 0.05, w: gridW, h: 0.3,
    fontSize: 9, color: C.dark_gray, fontFace: 'Noto Sans JP', align: 'center'
  });

  // 縦軸ラベル（横書きで左側に）
  slide.addText(yHigh, {
    x: 0.1, y: gridY, w: 0.9, h: 0.3,
    fontSize: 9, color: C.body, fontFace: 'Noto Sans JP', align: 'right'
  });
  slide.addText(yLow, {
    x: 0.1, y: gridY + gridH - 0.3, w: 0.9, h: 0.3,
    fontSize: 9, color: C.body, fontFace: 'Noto Sans JP', align: 'right'
  });
  slide.addText(yLabel, {
    x: 0.1, y: gridY + gridH / 2 - 0.15, w: 0.9, h: 0.3,
    fontSize: 9, color: C.dark_gray, fontFace: 'Noto Sans JP', align: 'right'
  });

  // アイテムをグリッド内に配置
  // x: 0〜1（左→右=低→高）、y: 0〜1（下→上=低→高）
  items.forEach(item => {
    const px = gridX + item.x * gridW;
    const py = gridY + (1 - item.y) * gridH; // y軸反転

    // ハイライト: 黄色丸 / 通常: グレー丸
    const dotColor = item.highlight ? C.yellow_d : C.mid_gray;
    slide.addShape('ellipse', {
      x: px - 0.12, y: py - 0.12, w: 0.24, h: 0.24,
      fill: { color: dotColor }
    });

    // ラベルテキスト: 9pt #111111
    slide.addText(item.label, {
      x: px - 0.5, y: py + 0.15, w: 1.0, h: 0.3,
      fontSize: 9, color: C.black,
      fontFace: 'Noto Sans JP', align: 'center'
      // 異常系: ラベルが重なる場合は y オフセットを ±0.3 でずらす
    });
  });

  addFooter(slide, pageNum);
  return slide;
}
```

**ポイント**:
- グリッドサイズ: x=1.2〜8.7, y=0.75〜4.75（縦4.0in × 横7.5in）
- 4象限を #CCCCCC の十字線で分割
- アイテムの位置は `x: 0〜1, y: 0〜1` の正規化座標で指定
- ハイライト項目: `#E8E800` 丸、通常: `#929699` 丸
- 異常系: アイテムが重なる場合は `y` を ±0.25 でずらす

---

## タイムライン横長

横軸=時間（月・週・フェーズ）、縦軸=施策・チャネルのガントチャート型。
複数施策の期間を同時に比較表示する場合に使用。

テンプレート参照: evals ケース #4（複数セクション・大型構成）、スケジュールスライド発展形

```js
// @param {object} pptx
// @param {object} params
//   heading  {string} - 大見出し
//   periods  {string[]} - 横軸期間ラベル（例:['1月','2月','3月','4月']）
//   rows     {Array}  - [{ label, bars: [{ start, end, color? }] }]
//     bars[].start, end: 0始まりのperiods インデックス（小数可）
//   pageNum  {number}
function createTimelineSlide(pptx, { heading, periods, rows, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  const labelX  = 0.34; // 行ラベル左端
  const labelW  = 1.4;  // 行ラベル幅
  const chartX  = labelX + labelW + 0.1; // チャート左端 (1.84)
  const chartW  = 7.8;  // チャート幅（10 - 0.34 - 1.4 - 0.1 - 0.36 = 7.8）
  const chartY  = 0.9;  // チャート上端（ヘッダー行）
  const rowH    = 0.42; // 行高さ
  const periodW = chartW / periods.length; // 期間ごとの幅

  // ヘッダー行: 期間ラベル
  slide.addShape('rect', {
    x: chartX, y: chartY, w: chartW, h: rowH,
    fill: { color: C.lite_gray } // #E6EBED
  });
  periods.forEach((p, i) => {
    slide.addText(p, {
      x: chartX + i * periodW, y: chartY, w: periodW, h: rowH,
      fontSize: 9, bold: true, color: C.black,
      fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
    });
    // 縦区切り線（最初以外）0.5pt #CCCCCC
    if (i > 0) {
      slide.addShape('line', {
        x: chartX + i * periodW, y: chartY,
        w: 0, h: rowH + rows.length * rowH,
        line: { color: C.divider, width: 0.5 }
      });
    }
  });

  // データ行
  rows.forEach((row, ri) => {
    const rowY = chartY + rowH + ri * rowH;

    // 行ラベル: 10pt #111111
    slide.addText(row.label, {
      x: labelX, y: rowY, w: labelW, h: rowH,
      fontSize: 10, color: C.black,
      fontFace: 'Noto Sans JP', valign: 'middle'
      // 異常系: ラベルが15文字超は fontSize: 9 に下げる
    });

    // 行背景（偶数行は薄グレー）
    if (ri % 2 === 1) {
      slide.addShape('rect', {
        x: chartX, y: rowY, w: chartW, h: rowH,
        fill: { color: 'F8F8F8' }
      });
    }

    // バー描画
    (row.bars || []).forEach(bar => {
      const barX = chartX + bar.start * periodW;
      const barW = (bar.end - bar.start) * periodW;
      const barColor = bar.color || C.dark_gray; // #676A6D

      slide.addShape('roundRect', {
        x: barX + 0.05, y: rowY + 0.08, w: barW - 0.1, h: rowH - 0.16,
        fill: { color: barColor },
        rectRadius: 0.04
      });

      // バー内ラベル（幅に余裕がある場合）
      if (barW > 0.8 && bar.barLabel) {
        slide.addText(bar.barLabel, {
          x: barX + 0.1, y: rowY + 0.08, w: barW - 0.2, h: rowH - 0.16,
          fontSize: 8, color: C.white,
          fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
        });
      }
    });

    // 横区切り線 0.5pt #CCCCCC
    slide.addShape('line', {
      x: labelX, y: rowY + rowH,
      w: labelW + 0.1 + chartW, h: 0,
      line: { color: C.divider, width: 0.5 }
    });
  });

  // チャート外枠（pptxgenjsはfill省略時に塗りなし扱い）
  slide.addShape('rect', {
    x: chartX, y: chartY,
    w: chartW, h: rowH + rows.length * rowH,
    line: { color: C.divider, width: 0.5 },
    fill: { color: 'FFFFFF' }
  });

  addFooter(slide, pageNum);
  return slide;
}
```

**ポイント**:
- 期間（periods）は最大12列推奨（12列を超える場合はフォントを8ptに下げる）
- バーの色: `C.dark_gray (#676A6D)` をデフォルト。強調バーは `C.black (#111111)`
- 行ラベルエリア幅 1.4in（ラベルが長い場合は 1.8in に拡大し chartX を調整）

---

## 囲みカラム（ボックスグリッド）

ボックス（枠線付き）をグリッド状に並べるパターン。課題・特徴の列挙に使用。

テンプレート参照: slide-48〜51（囲みカラム・ボックスグリッド）

```js
// @param {object} pptx
// @param {object} params
//   heading        {string} - 大見出し
//   boxes          {Array}  - [{ title, content }]（最大6件推奨）
//   cols           {number} - 列数（デフォルト: 3）
//   highlightIndex {number} - 強調ボックスのindex（任意）
//   pageNum        {number}
function createBoxGridSlide(pptx, { heading, boxes, cols, highlightIndex, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  cols = cols || 3;
  const totalW = 9.0;
  const gap    = 0.25;
  const boxW   = (totalW - gap * (cols - 1)) / cols;
  const boxH   = 1.6;
  const startX = 0.5;
  const startY = 0.7;

  boxes.forEach((box, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x   = startX + col * (boxW + gap);
    const y   = startY + row * (boxH + gap);

    const isHighlight = (highlightIndex === i);
    const lineWidth   = isHighlight ? 2.5 : 1;
    const lineColor   = isHighlight ? C.black : C.body; // #111111 or #434343

    // ボックス枠
    slide.addShape('rect', {
      x: x, y: y, w: boxW, h: boxH,
      line: { color: lineColor, width: lineWidth },
      fill: { color: C.white }
    });

    // タイトル（上部）: 11pt Bold #111111
    slide.addText(box.title, {
      x: x + 0.15, y: y + 0.1, w: boxW - 0.3, h: 0.3,
      fontSize: 11, bold: isHighlight, color: C.black,
      fontFace: 'Noto Sans JP', align: 'center'
      // 異常系: タイトル12文字超は fontSize: 10 に下げる
    });

    // 内容テキスト: 10pt #434343 中央配置
    slide.addText(box.content, {
      x: x + 0.15, y: y + 0.5, w: boxW - 0.3, h: boxH - 0.7,
      fontSize: 10, color: C.body,
      fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
    });
  });

  // 奇数個で最終行が1つの場合: startX をずらして中央に
  // lastRowCount = boxes.length % cols;
  // if (lastRowCount === 1) { 最終ボックスの x を (totalW - boxW) / 2 + startX に変更 }

  addFooter(slide, pageNum);
  return slide;
}
```

---

## 費用・リスト

費用表をテキストベースで表現。テーブル図形ではなく、テキスト+下線で構成。

テンプレート参照: slide-52（費用スライド）

```js
// @param {object} pptx
// @param {object} params
//   heading     {string} - 大見出し
//   plans       {Array}  - [{ name, price, items: string[] }]（左側）
//   detailItems {Array}  - [{ name, price }]（右側明細）
//   totalLabel  {string} - 合計ラベル（右側上部）
//   totalAmount {string} - 合計金額
//   pageNum     {number}
function createPricingSlide(pptx, { heading, plans, detailItems, totalLabel, totalAmount, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // 左側: プラン概算
  if (plans) {
    let y = 0.7;
    slide.addText('概算', {
      x: 0.48, y: y, w: 4.0, h: 0.3,
      fontSize: 9, color: C.dark_gray, fontFace: 'Noto Sans JP'
    });
    y += 0.35;

    plans.forEach(plan => {
      // プラン名 + 金額: 13pt Bold #111111
      slide.addText(plan.name, {
        x: 0.48, y: y, w: 2.5, h: 0.35,
        fontSize: 13, bold: true, color: C.black,
        fontFace: 'Noto Sans JP'
      });
      slide.addText(plan.price, {
        x: 3.0, y: y, w: 2.0, h: 0.35,
        fontSize: 13, color: C.black,
        fontFace: 'Noto Sans JP', align: 'right'
      });
      // 下線: 0.5pt #CCCCCC
      slide.addShape('line', {
        x: 0.48, y: y + 0.38,
        w: 4.5, h: 0,
        line: { color: C.divider, width: 0.5 }
      });
      y += 0.4;

      // 内訳: 10pt #434343
      (plan.items || []).forEach(item => {
        slide.addText(`- ${item}`, {
          x: 0.7, y: y, w: 4.0, h: 0.22,
          fontSize: 10, color: C.body,
          fontFace: 'Noto Sans JP'
        });
        y += 0.22;
      });
      y += 0.2;
    });
  }

  // 右側: 詳細明細
  if (detailItems) {
    let y = 0.7;
    // 合計行: 13pt Bold #111111
    if (totalLabel) {
      slide.addText(totalLabel, {
        x: 5.5, y: y, w: 2.0, h: 0.35,
        fontSize: 13, bold: true, color: C.black,
        fontFace: 'Noto Sans JP'
      });
      slide.addText(totalAmount, {
        x: 7.5, y: y, w: 2.0, h: 0.35,
        fontSize: 13, bold: true, color: C.black,
        fontFace: 'Noto Sans JP', align: 'right'
      });
      slide.addShape('line', {
        x: 5.5, y: y + 0.38, w: 4.0, h: 0,
        line: { color: C.divider, width: 0.5 }
      });
      y += 0.5;
    }
    // 明細行: 11pt #434343 + 点線区切り
    detailItems.forEach(item => {
      slide.addText(item.name, {
        x: 5.5, y: y, w: 2.5, h: 0.3,
        fontSize: 11, color: C.body,
        fontFace: 'Noto Sans JP'
      });
      slide.addText(item.price, {
        x: 8.0, y: y, w: 1.5, h: 0.3,
        fontSize: 11, color: C.body,
        fontFace: 'Noto Sans JP', align: 'right'
      });
      slide.addShape('line', {
        x: 5.5, y: y + 0.32, w: 4.0, h: 0,
        line: { color: C.divider, width: 0.5, dashType: 'dot' }
      });
      y += 0.38;
    });
  }

  addFooter(slide, pageNum);
  return slide;
}
```

---

## スケジュール

日付+丸ドット+イベント名を縦に並べるタイムライン形式。

テンプレート参照: slide-53〜54（スケジュールスライド）

```js
// @param {object} pptx
// @param {object} params
//   heading {string} - 大見出し
//   events  {Array}  - [{ date, name, highlight? }]
//   pageNum {number}
function createScheduleSlide(pptx, { heading, events, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  const startY  = 0.7;
  const lineH   = 0.5;
  const dateW   = 0.8;
  const eventW  = 3.5;

  // 2列表示
  [0, 4.8].forEach((baseX) => {
    events.forEach((ev, i) => {
      const y = startY + i * lineH;

      // 日付: 11pt Bold #111111（MM/DD形式）
      slide.addText(ev.date, {
        x: baseX + 0.48, y: y, w: dateW, h: 0.35,
        fontSize: 11, bold: true, color: C.black,
        fontFace: 'Noto Sans JP'
      });

      // ドット（丸）: #111111
      slide.addShape('ellipse', {
        x: baseX + 1.3, y: y + 0.12, w: 0.1, h: 0.1,
        fill: { color: C.black }
      });

      // 横線: 1pt #111111
      slide.addShape('line', {
        x: baseX + 1.45, y: y + 0.17,
        w: 0.15, h: 0,
        line: { color: C.black, width: 1 }
      });

      // イベント名
      if (ev.highlight) {
        // 強調: 黒ベタ背景 + 白文字 #FCFCFC
        slide.addShape('roundRect', {
          x: baseX + 1.65, y: y, w: eventW, h: 0.35,
          fill: { color: C.black }, // #111111
          rectRadius: 0.02
        });
        slide.addText(ev.name, {
          x: baseX + 1.65, y: y, w: eventW, h: 0.35,
          fontSize: 11, color: C.white,
          fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
        });
      } else {
        // 通常: 角丸枠のみ 0.5pt #111111
        slide.addShape('roundRect', {
          x: baseX + 1.65, y: y, w: eventW, h: 0.35,
          line: { color: C.black, width: 0.5 },
          rectRadius: 0.17
        });
        slide.addText(ev.name, {
          x: baseX + 1.65, y: y, w: eventW, h: 0.35,
          fontSize: 11, color: C.black,
          fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
          // 異常系: イベント名15文字超は fontSize: 9 に下げる
        });
      }
    });
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## フロー図（ステップ式）

STEP1→STEP2→...を縦に並べる導入フロー。

テンプレート参照: slide-55（フロー図ステップ式）

```js
// @param {object} pptx
// @param {object} params
//   heading {string} - 大見出し
//   steps   {Array}  - [{ name, description }]（最大6件推奨）
//   pageNum {number}
function createStepFlowSlide(pptx, { heading, steps, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  const startY = 0.7;
  const stepH  = 0.75;

  steps.forEach((step, i) => {
    const y = startY + i * stepH;

    // STEP番号: 11pt Italic #676A6D
    slide.addText(`STEP${i + 1}`, {
      x: 0.48, y: y, w: 0.8, h: 0.35,
      fontSize: 11, italic: true, color: C.dark_gray, // #676A6D
      fontFace: 'Noto Sans JP'
    });

    // ステップ名（角丸グレー帯）: 11pt Bold #FCFCFC
    slide.addShape('roundRect', {
      x: 1.3, y: y, w: 3.0, h: 0.35,
      fill: { color: C.mid_gray }, // #929699
      rectRadius: 0.17
    });
    slide.addText(step.name, {
      x: 1.3, y: y, w: 3.0, h: 0.35,
      fontSize: 11, bold: true, color: C.white,
      fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
    });

    // 説明テキスト: 10pt #434343 行間1.15
    slide.addText(step.description, {
      x: 1.3, y: y + 0.38, w: 7.5, h: 0.3,
      fontSize: 10, color: C.body,
      fontFace: 'Noto Sans JP',
      lineSpacingMultiple: 1.15
    });
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## LPワイヤーフレーム

PC・SP（タブレット）のワイヤーフレームを3つ並べるパターン。

テンプレート参照: slide-56（LPワイヤーフレーム）

```js
// @param {object} pptx
// @param {object} params
//   heading    {string} - 大見出し
//   wireframes {Array}  - [{ type: 'pc'|'sp'|'tablet', imagePath? }]
//   pageNum    {number}
function createWireframeSlide(pptx, { heading, wireframes, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading);
  addLogoBlack(slide);

  // PC版（大）+ SP版（中）+ タブレット版（中）の3分割レイアウト
  const layouts = {
    pc:     { x: 0.3,  y: 0.7, w: 4.0, h: 4.2 },
    sp:     { x: 4.5,  y: 0.7, w: 2.5, h: 4.2 },
    tablet: { x: 7.2,  y: 0.7, w: 2.5, h: 4.2 }
  };

  wireframes.forEach(wf => {
    const l = layouts[wf.type] || layouts.pc;
    // デバイスフレーム: 1pt #CCCCCC 角丸
    slide.addShape('roundRect', {
      x: l.x, y: l.y, w: l.w, h: l.h,
      line: { color: C.divider, width: 1 },
      rectRadius: 0.08,
      fill: { color: 'E6EBED' }
    });
    // ワイヤーフレーム画像
    if (wf.imagePath) {
      slide.addImage({
        path: wf.imagePath,
        x: l.x + 0.05, y: l.y + 0.2,
        w: l.w - 0.1, h: l.h - 0.3,
        sizing: { type: 'contain' }
      });
    }
  });

  addFooter(slide, pageNum);
  return slide;
}
```

---

## 組織図

NONAME Produce のチーム体制を図示。左側に組織ツリー、右側にパートナー企業。

テンプレート参照: slide-57（組織図）

```js
// @param {object} pptx
// @param {object} params
//   heading  {string} - 大見出し（省略時: '組織図'）
//   orgTree  {object} - { manager: { role, name }, members: [{ role, name }] }
//   partners {Array}  - [{ role, name, note? }]
//   pageNum  {number}
function createOrgChartSlide(pptx, { heading, orgTree, partners, pageNum }) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  addH1(slide, heading || '組織図');
  addLogoBlack(slide);

  // トップボックス: 会社名 1pt #111111
  const topX = 1.5, topY = 0.7, boxW = 3.5, boxH = 0.45;
  slide.addShape('roundRect', {
    x: topX, y: topY, w: boxW, h: boxH,
    line: { color: C.black, width: 1 }, // #111111
    rectRadius: 0.04
  });
  slide.addText('∧∧∧ 株式会社 NONAME Produce', {
    x: topX, y: topY, w: boxW, h: boxH,
    fontSize: 10, bold: true, color: C.black,
    fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
  });

  // 責任者ボックス: 0.5pt #111111
  const mgr  = orgTree.manager;
  const mgrY = topY + 0.7;
  slide.addShape('rect', {
    x: 2.2, y: mgrY, w: 2.0, h: 0.7,
    line: { color: C.black, width: 0.5 }
  });
  slide.addText(`${mgr.role}\n${mgr.name}`, {
    x: 2.2, y: mgrY, w: 2.0, h: 0.7,
    fontSize: 10, color: C.black,
    fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
  });

  // 縦線（マネージャーから下）: 0.5pt #111111
  slide.addShape('line', {
    x: 3.2, y: mgrY + 0.7, w: 0, h: 0.3,
    line: { color: C.black, width: 0.5 }
  });

  // サブメンバー
  const members = orgTree.members || [];
  const subY    = mgrY + 1.1;
  members.forEach((m, i) => {
    const mx = 1.0 + i * 2.5;
    slide.addShape('rect', {
      x: mx, y: subY, w: 2.0, h: 0.7,
      line: { color: C.black, width: 0.5 }
    });
    slide.addText(`${m.role}\n${m.name}`, {
      x: mx, y: subY, w: 2.0, h: 0.7,
      fontSize: 10, color: C.black,
      fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
    });
  });

  // 右側: パートナー企業
  if (partners) {
    let py = 1.5;
    partners.forEach(p => {
      addH2Dark(slide, p.role, 6.0, py, 3.5);
      py += 0.45;
      slide.addText(p.name, {
        x: 6.0, y: py, w: 3.5, h: 0.35,
        fontSize: 11, bold: true, color: C.black,
        fontFace: 'Noto Sans JP', align: 'center'
      });
      if (p.note) {
        slide.addText(p.note, {
          x: 6.0, y: py + 0.35, w: 3.5, h: 0.25,
          fontSize: 9, color: C.dark_gray, // #676A6D
          fontFace: 'Noto Sans JP', align: 'center'
        });
      }
      py += 0.8;
    });
  }

  addFooter(slide, pageNum);
  return slide;
}
```

---

## 会社概要

上部にダークヘッダー帯、下部に会社情報テーブル。

テンプレート参照: slide-58（会社概要スライド）

```js
// @param {object} pptx - PptxGenJS インスタンス
// フッターなし（会社概要は専用レイアウトのため標準フッターは使わない）
function createCompanySlide(pptx) {
  const slide = pptx.addSlide();

  // ダークヘッダー（#111111 全幅）
  slide.addShape('rect', {
    x: 0, y: 0, w: 10, h: 1.2,
    fill: { color: C.black } // #111111
  });

  // ヘッダータイトル: 24pt Bold #FCFCFC
  slide.addText('運営会社', {
    x: 2.0, y: 0.2, w: 6.0, h: 0.8,
    fontSize: 24, bold: true, color: C.white,
    fontFace: 'Noto Sans JP', align: 'center', valign: 'middle'
  });

  // ヘッダー内ロゴ（白）
  slide.addImage({
    path: LOGO_WHITE,
    x: 8.9, y: 0.15, w: 0.9, h: 0.30
  });

  // 会社情報テーブル: 11pt #111111（ラベル）/ #434343（値）
  const info = [
    ['会社名', '株式会社 NONAME Produce'],
    ['創業', '2006年8月'],
    ['代表取締役', '村上烈'],
    ['所在地', '〒160-0022 東京都新宿区新宿1-23-1 新宿マルネビル 10F'],
    ['事業内容', 'WEBサイト・モバイルサイト制作、WEBシステム構築、\nWEBを活用した広告キャンペーンの企画・製作・運用'],
    ['企業HP', 'https://n2p.co.jp/']
  ];

  let y = 1.8;
  info.forEach(([label, value]) => {
    // ラベル: 11pt Bold #111111
    slide.addText(label, {
      x: 2.0, y: y, w: 1.5, h: 0.45,
      fontSize: 11, bold: true, color: C.black,
      fontFace: 'Noto Sans JP', valign: 'middle'
    });
    // 値: 11pt #434343（URLのみ #4285F4）
    const isLink = value.startsWith('http');
    slide.addText(value, {
      x: 3.5, y: y, w: 5.5, h: 0.45,
      fontSize: 11, color: isLink ? C.link : C.body, // #4285F4 or #434343
      fontFace: 'Noto Sans JP', valign: 'middle',
      hyperlink: isLink ? { url: value } : undefined
    });
    // 区切り線: 0.5pt #CCCCCC
    slide.addShape('line', {
      x: 2.0, y: y + 0.45, w: 7.0, h: 0,
      line: { color: C.divider, width: 0.5 }
    });
    y += 0.55;
  });

  // 下部コピーライト: 8pt #999999
  slide.addText('© NONAME Produce Inc. All Rights Reserved', {
    x: 2.0, y: 5.1, w: 6.0, h: 0.3,
    fontSize: 8, color: C.footer,
    fontFace: 'Noto Sans JP', align: 'center'
  });

  return slide;
}
```

---

## エンドスライド

ロゴを中央に大きく配置してシンプルに締める。
企業名テキストを追加する場合は VI 準拠の表記のみ使用する。

テンプレート参照: slide-60（エンドスライド）

**厳守**: エンドスライドに `nonameproduce`（全小文字NG表記）を使ってはならない。
使用可能表記: `NONAME Produce` / `株式会社 NONAME Produce` / `n2p` / テキストなし

```js
// @param {object} pptx
// @param {object} params
//   showTagline {boolean} - 企業名テキストを表示するか（省略時: false）
//   tagline     {string}  - 表示テキスト（省略時: 'NONAME Produce'）
function createEndSlide(pptx, { showTagline = false, tagline } = {}) {
  const slide = pptx.addSlide();
  slide.background = { color: C.white };

  // 中央にロゴ（黒）: 3.0in × 1.0in
  slide.addImage({
    path: LOGO_BLACK,
    x: 3.5, y: 2.0, w: 3.0, h: 0.99
    // ロゴ隔離エリア: 0.99 × 0.5 = 0.495in 四方確保済（y=2.0 - 0.495 = 1.505 に余裕あり）
  });

  // 企業名テキスト（任意）: VI準拠表記のみ
  if (showTagline) {
    const text = tagline || 'NONAME Produce';
    // NG: 'nonameproduce' / 'noname produce' / 'N2P'
    slide.addText(text, {
      x: 3.0, y: 3.1, w: 4.0, h: 0.4,
      fontSize: 12, color: C.black, // #111111
      fontFace: 'Noto Sans JP',
      align: 'center'
    });
  }

  // フッターなし、ページ番号なし
  return slide;
}
```

---

## 標準的な資料構成

n2pの提案資料は以下の構成が標準。案件の内容に応じて中間部分を増減する。

```
1.  表紙（プレーン または 写真付き）
2.  目次スライド
3.  [中表紙] 01. 要件のご確認
4〜N.  本文スライド群（課題、ターゲット、競合分析等）
N+1.  [中表紙] 02. キャンペーンご提案
N+2〜M.  事例スライド（2カラム事例 × 複数）
M+1.  デザイン提案 MV
M+2.  デザイン提案 詳細説明
M+3.  デザイン提案 複数案比較
M+4.  コンセプトスライド（任意）
M+5.  キャンペーンフロー全体
M+6.  キャンペーンフロー詳細
M+7.  ユーザーフロー（シンプル）（任意）
M+8.  [中表紙] 03. スケジュール・費用感
M+9.  スケジュール
M+10. 費用・リスト
M+11. フロー図（ステップ式）
末尾-3.  組織図
末尾-2.  会社概要
末尾-1.  エンドスライド
```

**必要に応じて追加するスライド**:
- 囲みカラム（課題一覧・特徴比較）
- LPワイヤーフレーム（Web制作系の場合）
- マトリックス図（施策優先度評価）
- タイムライン横長（複数施策の期間比較）
- 非対称2カラム / 非対称3カラム（情報量の非対称な比較）

**スライドタイプ別のフッター・ロゴ方針**:

| スライドタイプ | フッター | ロゴ |
|---|---|---|
| 表紙 | なし | 右下透かし（白ロゴ、透明度70%） |
| 目次 | あり | 右上（黒ロゴ） |
| 中表紙 | あり | 右上（白ロゴ） |
| 本文（全種類） | あり | 右上（黒ロゴ） |
| 会社概要 | 代替フッター | ヘッダー内（白ロゴ） |
| エンドスライド | なし | 中央大（黒ロゴ） |

<!-- DONE: 14820 -->
