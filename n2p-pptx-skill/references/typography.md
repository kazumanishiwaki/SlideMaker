# n2p タイポグラフィ仕様

## 1. 使用フォント体系

### 1.1 Web / PPTX 用（デジタル標準）

| フォント | ウェイト | 用途 |
|---|---|---|
| **Noto Sans JP** Light | 300 | 表紙・中表紙の大タイトル補助、エレガント演出 |
| **Noto Sans JP** Regular | 400 | 本文・キャプション・フッター |
| **Noto Sans JP** Bold | 700 | 大見出し・中見出し・強調テキスト |
| **Helvetica Neue** Light | 300 | 欧文サブタイトル・数値強調（細め） |
| **Helvetica Neue** Regular | 400 | 欧文本文・URL・英語固有名詞 |
| **Helvetica Neue** Bold | 700 | 欧文見出し・英語強調 |

> **ルール**: 日本語テキストは Noto Sans JP、欧文テキスト（アルファベット・数字）は Helvetica Neue を優先。pptxgenjs では fontFace を切り替えて指定する。

### 1.2 印刷用（合成フォント）

| フォント | スケール | 用途 |
|---|---|---|
| **中ゴシック BBB** | 100% | 日本語テキスト（印刷向け） |
| **Helvetica** | **105%** | 欧文テキスト（印刷向け、105%スケール適用） |

> **注意**: Helveticaは印刷時に105%スケールで合成フォントとして設定する。Web/PPTXではHelvetica Neueを使用し、Helvetica（スケールなし）は印刷専用。

---

## 2. フォントサイズ階層テーブル

| 階層 | サイズ | ウェイト | フォント | 色 | 行間 | 用途 |
|---|---|---|---|---|---|---|
| 表紙タイトル | **28pt** | Bold | Noto Sans JP | #111111 | 1.2 | 表紙メインタイトル |
| 中表紙タイトル | **28pt** | Bold | Noto Sans JP | #111111 | 1.2 | 章タイトル・中表紙 |
| 大見出し | **16pt** | Bold | Noto Sans JP | #111111 | 1.15 | 各スライドのメイン見出し |
| 中見出し | **13pt** | Bold | Noto Sans JP | #111111 | 1.15 | セクション内の中分類 |
| 小見出し | **13pt** | Regular | Noto Sans JP | #434343 | 1.15 | リスト項目・補助見出し |
| 本文 | **11pt** | Regular | Noto Sans JP | #434343 | **1.15** | 本文・説明テキスト |
| フッター | **8〜9pt** | Regular | Noto Sans JP | #999999 | — | コピーライト・ページ番号 |
| 表紙宛名 | **14pt** | Regular | Noto Sans JP | #111111 | 1.15 | 提案先企業名・担当者名 |
| コンセプト文 | **13〜16pt** | Light | Noto Sans JP | #111111 | **1.3〜1.5** | コンセプトスライドの長文 |
| キャプション | **9pt** | Regular | Noto Sans JP | #676A6D | 1.15 | 図表下キャプション |

---

## 3. 行間（lineSpacing）仕様

| コンテキスト | 行間 | 適用スライド |
|---|---|---|
| 本文テキスト | **1.15** | 本文スライド全般 |
| 見出し（大・中・小） | **1.15** | 全スライド |
| 表紙タイトル | **1.2** | 表紙・中表紙 |
| コンセプト文・長文 | **1.3〜1.5** | コンセプトスライド |
| フッターテキスト | 設定不要（単行） | 全スライド |

---

## 4. 数字・記号の表記ルール

### 数字は半角必須
- **OK**: `100`, `2024年`, `50%`, `1,234,567`
- **NG**: `１００`（全角数字禁止）

### 英数字の混在
- 数値と単位の間はスペースなし: `50%`, `16pt`, `10mm`
- 英単語前後に不要なスペースを入れない

### カッコ・記号
- 日本語文中の括弧: 全角「（」「）」
- コード・英文中の括弧: 半角`(`  `)`
- 箇条書き記号: 中黒「・」または「●」を統一使用

---

## 5. pptxgenjs での fontFace 指定方法

```javascript
// 基本的なテキスト追加（日本語本文）
slide.addText('本文テキスト', {
  x: 0.5, y: 1.0, w: 9.0, h: 0.5,
  fontFace: 'Noto Sans JP',
  fontSize: 11,
  color: '434343',
  lineSpacingMultiple: 1.15,
});

// 大見出し
slide.addText('スライドタイトル', {
  x: 0.5, y: 0.3, w: 8.0, h: 0.6,
  fontFace: 'Noto Sans JP',
  fontSize: 16,
  bold: true,
  color: '111111',
  lineSpacingMultiple: 1.15,
});

// 表紙タイトル
slide.addText('提案書タイトル', {
  x: 0.5, y: 1.5, w: 9.0, h: 1.2,
  fontFace: 'Noto Sans JP',
  fontSize: 28,
  bold: true,
  color: '111111',
  lineSpacingMultiple: 1.2,
});

// フッター（コピーライト）
slide.addText('© NONAME Produce Inc.', {
  x: 0.28, y: 5.30, w: 4.0, h: 0.25,
  fontFace: 'Noto Sans JP',
  fontSize: 8,
  color: '999999',
});

// ページ番号（右寄せ）
slide.addText('1', {
  x: 9.20, y: 5.30, w: 0.5, h: 0.25,
  fontFace: 'Noto Sans JP',
  fontSize: 9,
  color: '999999',
  align: 'right',
});

// 欧文テキスト（Helvetica Neue）
slide.addText('NONAME Produce', {
  x: 0.5, y: 2.0, w: 5.0, h: 0.5,
  fontFace: 'Helvetica Neue',
  fontSize: 13,
  bold: true,
  color: '111111',
});

// コンセプト文（行間広め）
slide.addText('長めのコンセプト文がここに入ります。\n改行を含む場合もこの設定で対応します。', {
  x: 0.8, y: 1.5, w: 8.4, h: 2.0,
  fontFace: 'Noto Sans JP',
  fontSize: 14,
  color: '111111',
  lineSpacingMultiple: 1.4,
});

// 段落スタイルを使った複合テキスト
slide.addText([
  { text: '見出しテキスト', options: { fontFace: 'Noto Sans JP', fontSize: 13, bold: true, color: '111111' } },
  { text: '\n本文テキストが続きます。', options: { fontFace: 'Noto Sans JP', fontSize: 11, bold: false, color: '434343' } },
], {
  x: 0.5, y: 1.0, w: 9.0, h: 1.5,
  lineSpacingMultiple: 1.15,
});
```

---

## 6. フォントが見つからない環境でのフォールバック

### フォールバック優先順位

#### 日本語テキスト
1. `Noto Sans JP`（推奨）
2. `Hiragino Kaku Gothic Pro`（macOS標準）
3. `Meiryo`（Windows標準）
4. `Yu Gothic`（Windows 8.1以降）
5. `sans-serif`（システムデフォルト）

#### 欧文テキスト
1. `Helvetica Neue`（macOS推奨）
2. `Helvetica`（macOS代替）
3. `Arial`（Windows標準・最終フォールバック）
4. `sans-serif`（システムデフォルト）

### pptxgenjs でのフォールバック実装例

```javascript
// 環境依存フォントの定数定義（OS別）
const FONT_CONFIG = {
  // 日本語
  ja: {
    primary: 'Noto Sans JP',
    fallback: process.platform === 'win32' ? 'Meiryo' : 'Hiragino Kaku Gothic Pro',
  },
  // 欧文
  en: {
    primary: 'Helvetica Neue',
    fallback: process.platform === 'win32' ? 'Arial' : 'Helvetica',
  },
};

// 使用例
const jaFont = FONT_CONFIG.ja.primary; // Noto Sans JPが推奨
const enFont = FONT_CONFIG.en.primary; // Helvetica Neueが推奨
```

### フォントが欠落している場合の判別

- PPTX生成後、PowerPoint/Keynoteで開いたときにフォント代替警告が出る場合はフォールバックが適用されている
- Noto Sans JPはGoogleFontsから無料取得可能（https://fonts.google.com/noto/specimen/Noto+Sans+JP）
- Helvetica Neue はmacOSにデフォルト搭載。Windowsでは別途インストールが必要

---

## 7. フォント使用チェックリスト

- [ ] 日本語テキストに `Noto Sans JP` を指定しているか
- [ ] 欧文テキストに `Helvetica Neue` を指定しているか
- [ ] 全角数字（`１２３`）が混入していないか
- [ ] 本文の行間が `1.15` に設定されているか
- [ ] 表紙タイトルのフォントサイズが `28pt` か
- [ ] 大見出しが `16pt` Bold か
- [ ] フッター文字が `8〜9pt` か
- [ ] 印刷版でHelveticaが `105%` スケールで合成されているか（印刷対応時のみ）

<!-- DONE: 2987 -->
