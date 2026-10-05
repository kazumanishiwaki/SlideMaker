const pptxgen = require('pptxgenjs');
const path = require('path');
const fs = require('fs');

const ROOT_DIR = path.resolve(__dirname, '../../..');
const OUT_DIR = path.resolve(__dirname, '..');
const OUT_FILE = path.join(OUT_DIR, 'aha-receipt-lite-sales-sheet.pptx');

fs.mkdirSync(OUT_DIR, { recursive: true });

const pptx = new pptxgen();
pptx.author = 'NONAME Produce';
pptx.company = 'NONAME Produce Inc.';
pptx.subject = 'Aha Receipt Lite セールスシート';
pptx.title = 'Aha Receipt Lite セールスシート';
pptx.lang = 'ja-JP';
pptx.defineLayout({ name: 'n2p', width: 10, height: 5.625 });
pptx.layout = 'n2p';
pptx.theme = {
  headFontFace: 'Noto Sans JP',
  bodyFontFace: 'Noto Sans JP',
  lang: 'ja-JP',
};
pptx.margin = 0;

const LOGO_BLACK = path.join(ROOT_DIR, 'assets/symbol_black.png');
const LOGO_WHITE = path.join(ROOT_DIR, 'assets/symbol_white.png');

const C = {
  black: '111111',
  white: 'FCFCFC',
  cover: 'D7DEE2',
  lite: 'E6EBED',
  pale: 'F5F7F8',
  dark: '676A6D',
  mid: '929699',
  body: '434343',
  footer: '999999',
  divider: 'CCCCCC',
  yellowD: 'E8E800',
  yellowL: 'F4F400',
};

const FONT = 'Noto Sans JP';

function addBg(slide, color = C.white) {
  slide.background = { color };
}

function addLogoBlack(slide) {
  slide.addImage({ path: LOGO_BLACK, x: 8.9, y: 0.15, w: 0.9, h: 0.3 });
}

function addFooter(slide, pageNum) {
  slide.addShape(pptx.ShapeType.line, {
    x: 0.28, y: 5.28, w: 9.44, h: 0,
    line: { color: C.divider, width: 0.5 },
  });
  slide.addText('© 2026 NONAME Produce Inc.', {
    x: 0.28, y: 5.30, w: 3.6, h: 0.25,
    fontFace: FONT, fontSize: 8, color: C.footer, margin: 0,
  });
  slide.addText(String(pageNum), {
    x: 9.20, y: 5.30, w: 0.5, h: 0.25,
    fontFace: FONT, fontSize: 9, color: C.footer, align: 'right', margin: 0,
  });
}

function addH1(slide, text, y = 0.42) {
  slide.addShape(pptx.ShapeType.line, {
    x: 0.05, y: y + 0.21, w: 0.45, h: 0,
    line: { color: C.black, width: 1 },
  });
  slide.addText(text, {
    x: 0.55, y, w: 7.55, h: 0.44,
    fontFace: FONT,
    fontSize: text.length > 31 ? 13 : 16,
    bold: true,
    color: C.black,
    margin: 0,
    fit: 'shrink',
  });
}

function addLabel(slide, label) {
  slide.addText(label, {
    x: 0.55, y: 0.14, w: 2.2, h: 0.22,
    fontFace: FONT, fontSize: 9.5, bold: true,
    color: C.dark, margin: 0, fit: 'shrink',
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 0.55, y: 0.39, w: 0.68, h: 0,
    line: { color: C.yellowD, width: 2 },
  });
}

function addFrame(slide, label, title, pageNum) {
  addBg(slide);
  addLogoBlack(slide);
  addLabel(slide, label);
  addH1(slide, title);
  addFooter(slide, pageNum);
}

function addBody(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: FONT,
    fontSize: opts.fontSize || 11,
    color: opts.color || C.body,
    bold: opts.bold || false,
    align: opts.align || 'left',
    valign: opts.valign || 'top',
    margin: opts.margin ?? 0.03,
    fit: 'shrink',
    paraSpaceAfterPt: opts.paraSpaceAfterPt ?? 4,
    breakLine: false,
    lineSpacingMultiple: 1.15,
  });
}

function addBulletList(slide, items, x, y, w, opts = {}) {
  const gap = opts.gap || 0.44;
  items.forEach((item, i) => {
    const yy = y + i * gap;
    slide.addShape(pptx.ShapeType.ellipse, {
      x, y: yy + 0.08, w: 0.08, h: 0.08,
      fill: { color: opts.dot || C.black },
      line: { color: opts.dot || C.black, transparency: 100 },
    });
    slide.addText(item, {
      x: x + 0.18, y: yy, w, h: opts.h || 0.31,
      fontFace: FONT,
      fontSize: opts.fontSize || 11,
      color: opts.color || C.body,
      bold: opts.bold || false,
      margin: 0,
      fit: 'shrink',
      breakLine: false,
      lineSpacingMultiple: 1.15,
    });
  });
}

function addCard(slide, title, text, x, y, w, h, opts = {}) {
  slide.addShape(pptx.ShapeType.rect, {
    x, y, w, h,
    fill: { color: opts.fill || C.white },
    line: { color: opts.line || C.divider, width: opts.lineWidth || 0.6 },
  });
  slide.addText(title, {
    x: x + 0.14, y: y + 0.13, w: w - 0.28, h: 0.26,
    fontFace: FONT, fontSize: opts.titleSize || 11.5,
    bold: true, color: C.black, margin: 0, fit: 'shrink',
  });
  if (text) {
    addBody(slide, text, x + 0.14, y + 0.48, w - 0.28, h - 0.58, {
      fontSize: opts.fontSize || 9.8,
      color: opts.textColor || C.body,
      paraSpaceAfterPt: opts.paraSpaceAfterPt ?? 2,
    });
  }
}

function addDarkHeader(slide, text, x, y, w) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h: 0.34,
    rectRadius: 0.02,
    fill: { color: C.body },
    line: { color: C.body, transparency: 100 },
  });
  slide.addText(text, {
    x, y: y + 0.08, w, h: 0.16,
    fontFace: FONT, fontSize: 10.5, bold: true,
    color: C.white, align: 'center', margin: 0, fit: 'shrink',
  });
}

function addStepRow(slide, index, step, owner, days, y) {
  const cols = [
    [0.58, 0.52, String(index).padStart(2, '0')],
    [1.18, 4.35, step],
    [5.75, 1.45, owner],
    [7.48, 1.25, days],
  ];
  cols.forEach(([x, w, text], i) => {
    slide.addShape(pptx.ShapeType.rect, {
      x, y, w, h: 0.43,
      fill: { color: index % 2 === 0 ? C.pale : C.white },
      line: { color: C.divider, width: 0.45 },
    });
    slide.addText(text, {
      x: x + 0.07, y: y + 0.12, w: w - 0.14, h: 0.15,
      fontFace: FONT, fontSize: i === 1 ? 8.6 : 8.4,
      bold: i === 0,
      color: i === 0 ? C.black : C.body,
      align: i === 0 || i > 1 ? 'center' : 'left',
      margin: 0,
      fit: 'shrink',
    });
  });
}

function addCover() {
  const slide = pptx.addSlide();
  addBg(slide, C.cover);
  slide.addImage({ path: LOGO_WHITE, x: 6.2, y: 4.0, w: 3.8, h: 1.25, transparency: 70 });
  slide.addText('レシート応募キャンペーンを、\nもっと簡単に。', {
    x: 0.9, y: 1.22, w: 7.75, h: 0.96,
    fontFace: FONT, fontSize: 28, bold: true,
    color: C.black, margin: 0, fit: 'shrink',
    breakLine: false, lineSpacingMultiple: 1.08,
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 0.92, y: 2.44, w: 1.5, h: 0,
    line: { color: C.yellowD, width: 3 },
  });
  slide.addText('広告代理店・メーカーの販促担当のための、\nレシート応募キャンペーンCMS', {
    x: 0.92, y: 2.78, w: 6.85, h: 0.58,
    fontFace: FONT, fontSize: 13.5, bold: true,
    color: C.black, margin: 0, fit: 'shrink',
    lineSpacingMultiple: 1.15,
  });
  const proof = [
    'LP設定から応募受付・抽選まで一つの管理画面',
    'Web・LINEミニアプリ両対応',
  ];
  proof.forEach((p, i) => {
    slide.addShape(pptx.ShapeType.ellipse, {
      x: 1.0, y: 3.72 + i * 0.42, w: 0.08, h: 0.08,
      fill: { color: C.black },
      line: { color: C.black, transparency: 100 },
    });
    slide.addText(p, {
      x: 1.18, y: 3.65 + i * 0.42, w: 5.7, h: 0.23,
      fontFace: FONT, fontSize: 10.5, color: C.body,
      margin: 0, fit: 'shrink',
    });
  });
  slide.addText('2026.07.08', {
    x: 0.92, y: 4.9, w: 2.0, h: 0.2,
    fontFace: FONT, fontSize: 10, color: C.footer, margin: 0,
  });
}

function slideToc(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '目次', '本日の流れ', page);
  const items = ['課題', '解決策', '機能一覧', '導入の流れ', '選ばれる理由', '適用ケース', '料金', '運用・セキュリティ', 'お問い合わせ'];
  items.forEach((item, i) => {
    const col = i < 5 ? 0 : 1;
    const row = col === 0 ? i : i - 5;
    const x = col === 0 ? 1.0 : 5.05;
    const y = 1.24 + row * 0.66;
    const num = String(i + 1).padStart(2, '0');
    slide.addText(num, {
      x, y, w: 0.42, h: 0.2,
      fontFace: FONT, fontSize: 9.5, bold: true,
      color: C.mid, margin: 0,
    });
    slide.addShape(pptx.ShapeType.line, {
      x: x + 0.55, y: y + 0.1, w: 0.36, h: 0,
      line: { color: C.divider, width: 0.75 },
    });
    slide.addText(item, {
      x: x + 1.05, y: y - 0.05, w: 2.85, h: 0.3,
      fontFace: FONT, fontSize: 14, bold: true,
      color: C.black, margin: 0, fit: 'shrink',
    });
  });
}

function slideIssue(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '課題', '作業が分散するほど、キャンペーンの運用負荷は増える。', page);
  addBody(slide, 'LP制作、フォーム構築、画像受付、応募者管理、重複確認、CSV集計、抽選。7つの作業が別ツールと手作業に分かれがちです。', 0.68, 1.18, 4.15, 0.82, { fontSize: 12, bold: true, color: C.black });
  const tasks = ['LP制作', 'フォーム構築', '画像受付', '応募者管理', '重複確認', 'CSV集計', '抽選'];
  tasks.forEach((task, i) => {
    const x = 5.35 + (i % 2) * 1.8;
    const y = 1.03 + Math.floor(i / 2) * 0.58;
    slide.addShape(pptx.ShapeType.roundRect, {
      x, y, w: i === 6 ? 3.3 : 1.45, h: 0.34,
      rectRadius: 0.02,
      fill: { color: i === 6 ? C.yellowL : C.lite },
      line: { color: i === 6 ? C.yellowL : C.lite, width: 0.4 },
    });
    slide.addText(task, {
      x, y: y + 0.08, w: i === 6 ? 3.3 : 1.45, h: 0.15,
      fontFace: FONT, fontSize: 9.4, bold: true,
      color: C.black, align: 'center', margin: 0, fit: 'shrink',
    });
  });
  addCard(slide, '小〜中規模案件で起きやすいこと', '高機能システムは、要件・費用ともに過剰になりやすい。導入前の整理、設定、運用確認に時間がかかるほど、キャンペーン本来のスピードが落ちます。', 0.72, 3.15, 8.28, 1.12, { fill: C.pale, titleSize: 12, fontSize: 10.8 });
}

function slideSolution(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '解決策', '必要十分な機能を、一つのCMSで。', page);
  const points = [
    ['テンプレートベースのLP設定', '制作なしで公開まで最短▢営業日'],
    ['ワンストップ運用', '応募フォーム・画像受付・応募者管理・抽選まで対応'],
    ['クライアントユーザー管理', '権限発行により、担当者間で運用を分担'],
    ['Web／LINEミニアプリ両対応', 'キャンペーンの公開種別に合わせて応募受付'],
  ];
  points.forEach(([title, text], i) => {
    const x = 0.72 + (i % 2) * 4.25;
    const y = 1.05 + Math.floor(i / 2) * 1.36;
    addCard(slide, title, text, x, y, 3.65, 1.02, { fill: i === 0 ? C.yellowL : C.white, line: i === 0 ? C.yellowL : C.divider, titleSize: 12, fontSize: 10.5 });
  });
  addBody(slide, 'LP設定から応募データの出力まで、キャンペーン運用の基本動線を一つの管理画面に集約します。', 1.0, 4.22, 7.6, 0.34, { fontSize: 12, bold: true, color: C.black, align: 'center' });
}

function slideFeatures(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '機能一覧', '開始から抽選まで、実務に必要な機能を標準搭載。', page);
  const groups = [
    ['ページ・公開設定', [
      ['テンプレートLP設定', '文言、画像、配色、フォント、ロゴ画像などを設定'],
      ['OGP / SEO設定', 'メタタイトル、説明文、OGP画像、faviconを設定'],
      ['期間設定', 'キャンペーン期間、レシート対象期間、応募受付期間を管理'],
      ['Web / LINEミニアプリ応募受付', 'Web公開に加え、LINEミニアプリ上の応募受付に対応'],
    ]],
    ['応募・データ管理', [
      ['応募フォーム設定', '個人情報項目、アンケート項目、必須設定、選択肢を設定'],
      ['レシート画像受付', '複数枚アップロード可能。1応募あたり最大▢枚'],
      ['応募者管理', '名前、メールアドレス、応募日、重複フィルターで検索'],
      ['CSV出力', '検索条件を反映して応募者CSVを出力。出力項目 ▢'],
    ]],
    ['運用・拡張', [
      ['自動返信メール', '送信元、件名、本文、差し込み変数を設定'],
      ['トラッキング設定', 'GA、GTM、GA4などの計測タグを設定'],
      ['抽選・当選候補CSV出力', '指定人数をランダム抽出し、CSV出力'],
      ['ユーザー管理', 'クライアント担当者アカウントを発行・管理'],
    ]],
  ];
  groups.forEach(([group, rows], gi) => {
    const x = 0.58 + gi * 2.72;
    addDarkHeader(slide, group, x, 0.92, 1.92);
    rows.forEach(([title, text], ri) => {
      const y = 1.42 + ri * 0.72;
      slide.addText(title, {
        x, y, w: 2.35, h: 0.18,
        fontFace: FONT, fontSize: 8.9, bold: true,
        color: C.black, margin: 0, fit: 'shrink',
      });
      addBody(slide, text, x, y + 0.22, 2.35, 0.32, { fontSize: 7.8, paraSpaceAfterPt: 0 });
      slide.addShape(pptx.ShapeType.line, {
        x, y: y + 0.6, w: 2.35, h: 0,
        line: { color: C.divider, width: 0.45 },
      });
    });
  });
  addBody(slide, '応募データ保持期間：▢', 0.62, 4.62, 3.0, 0.2, { fontSize: 9.3, color: C.footer });
}

function slideFlow(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '導入の流れ', '設定して、確認して、公開。あとは応募を集めて抽選。', page);
  const headers = [['No.', 0.58, 0.52], ['ステップ', 1.18, 4.35], ['担当', 5.75, 1.45], ['目安日数', 7.48, 1.25]];
  headers.forEach(([h, x, w]) => {
    slide.addShape(pptx.ShapeType.rect, {
      x, y: 1.0, w, h: 0.34,
      fill: { color: C.lite },
      line: { color: C.black, width: 0.65 },
    });
    slide.addText(h, {
      x, y: 1.09, w, h: 0.13,
      fontFace: FONT, fontSize: 8.3, bold: true,
      color: C.black, align: 'center', margin: 0,
    });
  });
  const rows = [
    ['プロジェクトを作成', '代理店／御社', '▢日'],
    ['キャンペーン文言、フォーム、画像、メール、計測タグを設定', '代理店／御社', '▢日'],
    ['プレビューURLでLP・フォーム・確認画面・完了画面を確認', '代理店／クライアント', '▢日'],
    ['プレビュー応募でテスト送信を確認', '代理店／クライアント', '▢日'],
    ['公開ステータスに切り替え', '御社', '▢日'],
    ['応募内容を管理画面で確認し、必要に応じてCSV出力', '代理店／クライアント', '▢日'],
    ['キャンペーン終了後に抽選し、当選候補CSVを出力', '代理店／御社', '▢日'],
  ];
  rows.forEach((row, i) => addStepRow(slide, i + 1, row[0], row[1], row[2], 1.34 + i * 0.43));
  addBody(slide, 'プレビュー応募は本番応募データに残らないため、公開前の表示確認・入力確認に使えます。', 0.72, 4.62, 8.1, 0.25, { fontSize: 10, align: 'center' });
}

function slideReason(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '選ばれる理由', '機能数で競わない。必要十分なCMSとして、キャンペーンの前段に立つ。', page);
  addCard(slide, '標準非搭載を明示', 'AI-OCR自動読取\n不正応募の自動判定\n即時抽選\nLINE配信\n\n個別要件として対応可。料金Optionで整理します。', 0.72, 1.12, 2.42, 2.95, { fill: C.lite, titleSize: 11.5, fontSize: 9.8 });
  addCard(slide, '基本動線を集約', 'LP設定、フォーム、画像受付、応募者管理、CSV出力、抽選までを一画面に集約。小〜中規模キャンペーンの運用を迷わせません。', 3.54, 1.12, 2.72, 2.95, { fill: C.white, line: C.black, titleSize: 11.5, fontSize: 10.2 });
  addCard(slide, 'ロックインしない設計', '応募データはCSVで持ち出せます。要件が育ったら拡張・移行できるため、まず小さく始められます。', 6.66, 1.12, 2.42, 2.95, { fill: C.yellowL, line: C.yellowL, titleSize: 11.5, fontSize: 10.2 });
  addBody(slide, '高機能ツールの前段として、まずはレシート応募キャンペーンを確実に開始・運用するためのCMSです。', 1.05, 4.45, 7.65, 0.32, { fontSize: 12, bold: true, color: C.black, align: 'center' });
}

function slideCases(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '適用ケース', '標準機能の範囲で完結する、小〜中規模キャンペーンに。', page);
  addDarkHeader(slide, '代理店向け', 0.78, 1.12, 2.0);
  addBulletList(slide, ['複数クライアント案件の並行運用（権限分離）', '短納期の店頭連動', '複数案件の設定・応募データ確認を一元化'], 0.88, 1.66, 3.25, { fontSize: 10.5, gap: 0.5 });
  addDarkHeader(slide, 'メーカー向け', 4.15, 1.12, 2.0);
  addBulletList(slide, ['自社製品のレシート応募', '期間・エリア限定の販促', 'アンケート付き応募による購買後接点づくり'], 4.25, 1.66, 3.1, { fontSize: 10.5, gap: 0.5 });
  addCard(slide, '標準訴求の範囲', 'LINEミニアプリでの応募受付\n応募者管理\n重複候補確認\nCSV出力\n後日抽選', 7.55, 1.12, 1.78, 2.55, { fill: C.lite, titleSize: 10, fontSize: 8.8 });
  addCard(slide, '実施例', '▢\n1件入り次第、想定ケースと差し替え', 0.85, 4.08, 8.1, 0.65, { fill: C.white, titleSize: 10.5, fontSize: 9.4 });
}

function slidePricing(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '料金', 'キャンペーン単位の、わかりやすい料金。', page);
  addCard(slide, '基本料金', '初期 ¥▢ ＋ キャンペーン ¥▢\n（月額課金の場合：月額 ¥▢）', 0.75, 1.15, 2.45, 1.28, { fill: C.yellowL, line: C.yellowL, titleSize: 12, fontSize: 11 });
  addCard(slide, '含まれるもの', '標準機能一式\n▢', 3.55, 1.15, 2.35, 1.28, { titleSize: 12, fontSize: 11 });
  addCard(slide, 'Option', 'LINEミニアプリ対応 ¥▢\nLINE公式アカウント＋審査が前提\nOCR連携等は個別見積', 6.25, 1.15, 2.65, 1.28, { titleSize: 12, fontSize: 9.7 });
  addCard(slide, '変動要因', '料金はキャンペーン期間、応募想定数、レシート枚数、フォーム項目数、LINEミニアプリ審査・設定範囲、運用支援範囲により変動します。', 0.75, 3.0, 8.15, 0.92, { fill: C.pale, titleSize: 11.2, fontSize: 10.2 });
  addBody(slide, '※OCR、自動レシート判定、即時抽選、抽選履歴保存、LINEメッセージ配信、友だち追加連携は個別見積または拡張オプションとして整理。', 0.88, 4.35, 7.85, 0.3, { fontSize: 9.4, color: C.footer });
}

function slideSecurity(page) {
  const slide = pptx.addSlide();
  addFrame(slide, '運用・セキュリティ', '応募者の個人情報を扱う前提で、保護と運用の仕様を明示。', page);
  const items = [
    ['通信の暗号化', '▢'],
    ['データ保管先', '▢（国内リージョン等）'],
    ['保持期間・削除', 'キャンペーン終了後▢日で削除 等'],
    ['アクセス制御', 'クライアントユーザー管理による権限分離'],
    ['サポート窓口・対応時間', '▢'],
  ];
  items.forEach(([title, text], i) => {
    const x = 0.78 + (i % 2) * 4.05;
    const y = 1.05 + Math.floor(i / 2) * 1.03;
    const w = i === 4 ? 8.1 : 3.25;
    addCard(slide, title, text, x, y, w, 0.72, { fill: i === 3 ? C.lite : C.white, titleSize: 11, fontSize: 10 });
  });
  addBody(slide, '商談時には、上記▢項目を案件ごとの運用条件に合わせて明示します。', 1.05, 4.52, 7.55, 0.25, { fontSize: 10.5, align: 'center', color: C.footer });
}

function slideContact(page) {
  const slide = pptx.addSlide();
  addFrame(slide, 'お問い合わせ', '次のレシートキャンペーンを、もっと手軽に。', page);
  slide.addText('Aha Receipt Liteで、\nレシート応募キャンペーンをもっと運用しやすく。', {
    x: 1.05, y: 1.08, w: 7.8, h: 0.72,
    fontFace: FONT, fontSize: 21, bold: true,
    color: C.black, align: 'center', margin: 0,
    fit: 'shrink', lineSpacingMultiple: 1.12,
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 3.85, y: 1.95, w: 2.3, h: 0,
    line: { color: C.yellowD, width: 3 },
  });
  const ctas = [
    ['30分デモ予約', '▢URL / QR'],
    ['見積依頼', '▢'],
    ['既存運用からの移行相談', '▢'],
  ];
  ctas.forEach(([title, text], i) => {
    addCard(slide, title, text, 0.92 + i * 2.86, 2.45, 2.35, 0.92, { fill: i === 0 ? C.yellowL : C.white, line: i === 0 ? C.yellowL : C.black, titleSize: 11.5, fontSize: 10 });
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: 1.35, y: 3.95, w: 7.3, h: 0.74,
    fill: { color: C.lite },
    line: { color: C.divider, width: 0.5 },
  });
  addBody(slide, 'NONAME Produce Inc.／担当▢／連絡先▢', 1.6, 4.2, 6.8, 0.22, { fontSize: 12, bold: true, color: C.black, align: 'center' });
}

addCover();
let page = 1;
slideToc(page++);
slideIssue(page++);
slideSolution(page++);
slideFeatures(page++);
slideFlow(page++);
slideReason(page++);
slideCases(page++);
slidePricing(page++);
slideSecurity(page++);
slideContact(page++);

pptx.writeFile({ fileName: OUT_FILE });
