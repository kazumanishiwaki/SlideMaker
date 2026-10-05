const pptxgen = require('pptxgenjs');
const path = require('path');

const EXAMPLE_DIR = __dirname;
const ROOT_DIR = path.resolve(EXAMPLE_DIR, '..', '..');

const pptx = new pptxgen();
pptx.author = 'NONAME Produce';
pptx.subject = 'agent-skills 利用促進';
pptx.title = 'agent-skills 利用促進';
pptx.company = 'NONAME Produce Inc.';
pptx.lang = 'ja-JP';
pptx.defineLayout({ name: 'n2p', width: 10, height: 5.625 });
pptx.layout = 'n2p';
pptx.theme = {
  headFontFace: 'Noto Sans JP',
  bodyFontFace: 'Noto Sans JP',
  lang: 'ja-JP'
};
pptx.margin = 0;

const LOGO_BLACK = path.join(ROOT_DIR, 'assets/symbol_black.png');
const LOGO_WHITE = path.join(ROOT_DIR, 'assets/symbol_white.png');
const ILLUSTRATIONS = {
  slide04: path.join(EXAMPLE_DIR, 'generated-assets/slide-04/image-v5.png'),
  slide09: path.join(EXAMPLE_DIR, 'generated-assets/slide-09/image-v5.png'),
  slide12: path.join(EXAMPLE_DIR, 'generated-assets/slide-12/image-v5.png')
};

const C = {
  black: '111111',
  white: 'FCFCFC',
  cover: 'D7DEE2',
  lite: 'E6EBED',
  dark: '676A6D',
  mid: '929699',
  body: '434343',
  footer: '999999',
  divider: 'CCCCCC',
  yellowD: 'E8E800',
  yellowL: 'F4F400',
  link: '4285F4'
};

const FONT = 'Noto Sans JP';
const W = 10;
const H = 5.625;

function addBg(slide, color = C.white) {
  slide.background = { color };
}

function addLogoBlack(slide) {
  slide.addImage({ path: LOGO_BLACK, x: 8.9, y: 0.15, w: 0.9, h: 0.3 });
}

function addLogoWhite(slide) {
  slide.addImage({ path: LOGO_WHITE, x: 8.9, y: 0.15, w: 0.9, h: 0.3 });
}

function addFooter(slide, pageNum) {
  slide.addShape(pptx.ShapeType.line, {
    x: 0.28, y: 5.28, w: 9.44, h: 0,
    line: { color: C.divider, width: 0.5 }
  });
  slide.addText('© 2026 NONAME Produce Inc.', {
    x: 0.28, y: 5.30, w: 3.6, h: 0.25,
    fontFace: FONT, fontSize: 8, color: C.footer,
    margin: 0
  });
  slide.addText(String(pageNum), {
    x: 9.20, y: 5.30, w: 0.5, h: 0.25,
    fontFace: FONT, fontSize: 9, color: C.footer,
    align: 'right', margin: 0
  });
}

function addH1(slide, text) {
  slide.addShape(pptx.ShapeType.line, {
    x: 0.05, y: 0.35, w: 0.45, h: 0,
    line: { color: C.black, width: 1 }
  });
  slide.addText(text, {
    x: 0.55, y: 0.14, w: 7.5, h: 0.42,
    fontFace: FONT, fontSize: text.length > 28 ? 13 : 16,
    bold: true, color: C.black, margin: 0,
    fit: 'shrink'
  });
}

function addSlideFrame(slide, title, pageNum) {
  addBg(slide);
  addLogoBlack(slide);
  addH1(slide, title);
  addFooter(slide, pageNum);
}

function addEyebrow(slide, text, x, y, w = 1.2) {
  slide.addShape(pptx.ShapeType.rect, {
    x, y, w, h: 0.18,
    fill: { color: C.yellowD },
    line: { color: C.yellowD, transparency: 100 }
  });
  slide.addText(text, {
    x, y: y + 0.21, w, h: 0.2,
    fontFace: FONT, fontSize: 8, bold: true,
    color: C.black, margin: 0
  });
}

function addBody(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: FONT, fontSize: opts.fontSize || 11,
    color: opts.color || C.body,
    bold: opts.bold || false,
    breakLine: false,
    fit: 'shrink',
    margin: opts.margin ?? 0.02,
    valign: opts.valign || 'top',
    paraSpaceAfterPt: opts.paraSpaceAfterPt ?? 5,
    breakLine: false,
    lineSpacingMultiple: 1.15
  });
}

function addLead(slide, text, y = 0.82) {
  slide.addText(text, {
    x: 0.55, y, w: 8.6, h: 0.55,
    fontFace: FONT, fontSize: 16, bold: true,
    color: C.black, margin: 0,
    fit: 'shrink'
  });
}

function addBullets(slide, items, x, y, w, opts = {}) {
  const gap = opts.gap || 0.46;
  items.forEach((item, i) => {
    const yy = y + i * gap;
    slide.addShape(pptx.ShapeType.ellipse, {
      x, y: yy + 0.07, w: 0.08, h: 0.08,
      fill: { color: opts.dot || C.black },
      line: { color: opts.dot || C.black, transparency: 100 }
    });
    slide.addText(item, {
      x: x + 0.18, y: yy, w, h: 0.3,
      fontFace: FONT, fontSize: opts.fontSize || 11,
      color: opts.color || C.body,
      margin: 0,
      fit: 'shrink'
    });
  });
}

function addNumberCard(slide, num, title, text, x, y, w, h) {
  slide.addShape(pptx.ShapeType.rect, {
    x, y, w, h,
    fill: { color: C.white },
    line: { color: C.divider, width: 0.6 }
  });
  slide.addText(num, {
    x: x + 0.16, y: y + 0.14, w: 0.45, h: 0.24,
    fontFace: FONT, fontSize: 10, bold: true,
    color: C.black, margin: 0
  });
  slide.addShape(pptx.ShapeType.line, {
    x: x + 0.16, y: y + 0.46, w: 0.36, h: 0,
    line: { color: C.yellowD, width: 2 }
  });
  slide.addText(title, {
    x: x + 0.68, y: y + 0.12, w: w - 0.84, h: 0.32,
    fontFace: FONT, fontSize: 12, bold: true,
    color: C.black, margin: 0,
    fit: 'shrink'
  });
  addBody(slide, text, x + 0.68, y + 0.55, w - 0.84, h - 0.72, { fontSize: 9.5 });
}

function addQuote(slide, text, x, y, w, h) {
  slide.addShape(pptx.ShapeType.rect, {
    x, y, w, h,
    fill: { color: C.lite },
    line: { color: C.lite, transparency: 100 }
  });
  slide.addText(text, {
    x: x + 0.22, y: y + 0.18, w: w - 0.44, h: h - 0.36,
    fontFace: FONT, fontSize: 18, bold: true,
    color: C.black, margin: 0,
    align: 'center', valign: 'middle',
    fit: 'shrink'
  });
}

function addMiniScreen(slide, x, y, w, h, opts = {}) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: 0.04,
    fill: { color: opts.fill || C.white },
    line: { color: C.black, width: 1 }
  });
  slide.addShape(pptx.ShapeType.line, {
    x, y: y + 0.24, w, h: 0,
    line: { color: C.divider, width: 0.8 }
  });
  slide.addShape(pptx.ShapeType.rect, {
    x: x + 0.18, y: y + 0.42, w: w * 0.36, h: h * 0.28,
    fill: { color: C.lite },
    line: { color: C.lite, transparency: 100 }
  });
  [0, 1, 2].forEach((i) => {
    slide.addShape(pptx.ShapeType.line, {
      x: x + w * 0.58, y: y + 0.46 + i * 0.18, w: w * 0.28, h: 0,
      line: { color: C.divider, width: 2 }
    });
  });
  if (opts.highlight) {
    slide.addShape(pptx.ShapeType.line, {
      x: x + 0.18, y: y + h - 0.34, w: w * 0.42, h: 0,
      line: { color: C.yellowD, width: 3 }
    });
  }
}

function addThinArrow(slide, x, y, w) {
  slide.addShape(pptx.ShapeType.line, {
    x, y, w, h: 0,
    line: { color: C.black, width: 1, endArrowType: 'triangle' }
  });
}

function addEditableLabel(slide, text, x, y, w, opts = {}) {
  slide.addText(text, {
    x, y, w, h: opts.h || 0.28,
    fontFace: FONT, fontSize: opts.fontSize || 11,
    bold: opts.bold ?? true,
    color: opts.color || C.black,
    align: opts.align || 'center',
    margin: 0,
    fit: 'shrink'
  });
}

function addCover() {
  const slide = pptx.addSlide();
  addBg(slide, C.cover);
  slide.addImage({ path: LOGO_WHITE, x: 6.2, y: 4.0, w: 3.8, h: 1.25, transparency: 70 });
  slide.addText('agent-skills\n利用促進', {
    x: 1.05, y: 1.55, w: 7.2, h: 1.05,
    fontFace: FONT, fontSize: 28, bold: true,
    color: C.black, margin: 0,
    breakLine: false,
    fit: 'shrink'
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 1.05, y: 2.82, w: 1.4, h: 0,
    line: { color: C.yellowD, width: 3 }
  });
  slide.addText('AIモックを、ポン出しに見えない提案材料へ。', {
    x: 1.05, y: 3.05, w: 6.5, h: 0.36,
    fontFace: FONT, fontSize: 14, color: C.black, margin: 0
  });
  slide.addText('2026.05.07', {
    x: 1.05, y: 4.78, w: 2.0, h: 0.24,
    fontFace: FONT, fontSize: 11, color: C.footer, margin: 0
  });
}

function addToc() {
  const slide = pptx.addSlide();
  addSlideFrame(slide, '本日の流れ', 1);
  const items = [
    ['01', 'ポン出しは、もう差別化にならない'],
    ['02', 'ポン出し感が、提案の信頼を下げる'],
    ['03', '中途半端な装飾は、誤解を生む'],
    ['04', '感覚の指示を、共通ルールに変える'],
    ['05', 'agent-skills の役割と使い方']
  ];
  items.forEach((it, i) => {
    const y = 1.0 + i * 0.72;
    slide.addText(it[0], {
      x: 0.65, y, w: 0.55, h: 0.24,
      fontFace: FONT, fontSize: 10, bold: true,
      color: C.mid, margin: 0
    });
    slide.addShape(pptx.ShapeType.line, {
      x: 1.25, y: y + 0.11, w: 0.45, h: 0,
      line: { color: C.divider, width: 0.75 }
    });
    slide.addText(it[1], {
      x: 1.85, y: y - 0.03, w: 6.8, h: 0.32,
      fontFace: FONT, fontSize: 14, bold: true,
      color: C.black, margin: 0,
      fit: 'shrink'
    });
  });
}

function addSection(num, title, subtitle) {
  const slide = pptx.addSlide();
  addBg(slide, C.cover);
  addLogoWhite(slide);
  slide.addText(num, {
    x: 0.78, y: 1.38, w: 0.9, h: 0.3,
    fontFace: FONT, fontSize: 14, color: C.black, margin: 0
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 0.78, y: 1.82, w: 1.0, h: 0,
    line: { color: C.yellowD, width: 3 }
  });
  slide.addText(title, {
    x: 0.78, y: 2.12, w: 7.7, h: 0.9,
    fontFace: FONT, fontSize: 28, bold: true,
    color: C.black, margin: 0,
    fit: 'shrink'
  });
  slide.addText(subtitle, {
    x: 0.8, y: 3.25, w: 6.5, h: 0.35,
    fontFace: FONT, fontSize: 12, color: C.body, margin: 0
  });
}

addCover();
addToc();
addSection('01', 'ポン出しは、もう差別化にならない', '速さだけでは、提案の深さは伝わりにくい。');

let page = 2;
{
  const slide = pptx.addSlide();
  addSlideFrame(slide, 'ポン出しは、もう差別化にならない', page++);
  addLead(slide, 'AIモックは誰でも作れる。だから、そのまま出すだけでは提案になりにくい。');
  slide.addImage({ path: ILLUSTRATIONS.slide04, x: 1.4, y: 1.18, w: 7.2, h: 4.05 });
  addEditableLabel(slide, '速い出力', 1.58, 1.62, 1.55, { fontSize: 10.5 });
  addEditableLabel(slide, '案件理解', 4.35, 1.62, 1.32, { fontSize: 10.5 });
  addEditableLabel(slide, '提案材料', 6.88, 1.62, 1.55, { fontSize: 10.5 });
  slide.addText('AIを使う前提で、ポン出しに見えないモックにする。', {
    x: 1.15, y: 4.90, w: 7.7, h: 0.24,
    fontFace: FONT, fontSize: 13, bold: true,
    color: C.black, align: 'center', margin: 0,
    fit: 'shrink'
  });
}

{
  const slide = pptx.addSlide();
  addSlideFrame(slide, 'ポン出し感が、提案の信頼を下げる', page++);
  addLead(slide, '見た目は整っている。でも、提案としての意図が薄く見える。');
  const items = ['どこかで見たことがある', '案件らしさよりAIっぽさが目立つ', '「これで考えてきたの？」と思われる', '情報設計より見た目に話が寄る'];
  addBullets(slide, items, 0.85, 1.75, 4.0, { fontSize: 13, gap: 0.58 });
  slide.addShape(pptx.ShapeType.rect, {
    x: 5.65, y: 1.45, w: 3.55, h: 2.75,
    fill: { color: C.lite },
    line: { color: C.divider, width: 0.5 }
  });
  addEyebrow(slide, '例', 5.95, 1.8, 0.5);
  addBody(slide, '大きすぎる日本語見出し\n中央の大きなカード\n強いグラデーション\n過剰なシャドウ\nなんとなく入ったアニメーション', 5.95, 2.18, 2.75, 1.45, { fontSize: 11.5, color: C.black });
  slide.addText('話したい論点が、表面の見た目に引っ張られる。', {
    x: 5.95, y: 3.78, w: 2.85, h: 0.28,
    fontFace: FONT, fontSize: 10, bold: true,
    color: C.body, margin: 0,
    fit: 'shrink'
  });
}

{
  const slide = pptx.addSlide();
  addSlideFrame(slide, '中途半端な装飾は、誤解を生む', page++);
  addLead(slide, '「このデザインで進むんですか？」が、構成議論をズラしてしまう。');
  addQuote(slide, '本来見てほしいこと', 0.72, 1.52, 2.2, 0.46);
  addBullets(slide, ['情報の順番', '導線', '画面構成', '迷わず使えるか', '社内で説明しやすいか'], 0.86, 2.2, 2.3, { fontSize: 11.5, gap: 0.42 });
  slide.addShape(pptx.ShapeType.line, {
    x: 3.72, y: 2.85, w: 1.05, h: 0,
    line: { color: C.black, width: 1, beginArrowType: 'none', endArrowType: 'triangle' }
  });
  addQuote(slide, '誤解されやすいこと', 5.42, 1.52, 2.45, 0.46);
  addBullets(slide, ['このグラデーションで進むのか', 'このシャドウが完成形か', 'このカードUIが本番か', '後工程で作り直しが増える'], 5.55, 2.2, 3.2, { fontSize: 11.5, gap: 0.48 });
  slide.addShape(pptx.ShapeType.rect, {
    x: 1.0, y: 4.45, w: 7.9, h: 0.08,
    fill: { color: C.yellowD },
    line: { color: C.yellowD, transparency: 100 }
  });
  slide.addText('提案時のモックは、完成デザインではなく判断材料。', {
    x: 1.0, y: 4.1, w: 7.9, h: 0.28,
    fontFace: FONT, fontSize: 14, bold: true,
    color: C.black, align: 'center', margin: 0
  });
}

addSection('02', '感覚の修正を、共通ルールへ', '毎回の後処理を、最初に渡す前提に変える。');

{
  const slide = pptx.addSlide();
  addSlideFrame(slide, '毎回、同じ修正をしていないか？', page++);
  addLead(slide, '同じ指摘が続くなら、それはレビューではなく事故の後処理。');
  const fixes = ['もっと普通に', 'AIっぽさを消して', '見出しが大きすぎる', 'シャドウを弱くして', 'グラデーションいらない', '実装を軽くして', '本番で使いにくそう'];
  fixes.forEach((t, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.75 + col * 4.25;
    const y = 1.55 + row * 0.72;
    slide.addShape(pptx.ShapeType.rect, {
      x, y, w: 3.65, h: 0.42,
      fill: { color: row === 1 ? C.lite : C.white },
      line: { color: C.divider, width: 0.6 }
    });
    slide.addText(t, {
      x: x + 0.18, y: y + 0.1, w: 3.3, h: 0.2,
      fontFace: FONT, fontSize: 11.5, bold: true,
      color: C.black, margin: 0,
      fit: 'shrink'
    });
  });
  slide.addText('「もっと普通に」は、人にもAIにも曖昧。', {
    x: 1.15, y: 4.55, w: 7.7, h: 0.28,
    fontFace: FONT, fontSize: 15, bold: true,
    color: C.black, align: 'center', margin: 0
  });
}

{
  const slide = pptx.addSlide();
  addSlideFrame(slide, '感覚での指示を、共通ルールに変える', page++);
  addLead(slide, '完璧なデザインをAIに作らせるのではなく、判断基準を先に渡す。');
  slide.addImage({ path: ILLUSTRATIONS.slide09, x: 1.35, y: 1.38, w: 7.0, h: 3.94 });
  addEditableLabel(slide, '感覚指示', 1.58, 1.72, 1.65, { fontSize: 11 });
  addEditableLabel(slide, '言語化', 4.36, 1.86, 1.2, { fontSize: 11 });
  addEditableLabel(slide, '共通ルール', 6.85, 1.72, 1.5, { fontSize: 11 });
  slide.addText('言語化すると、AIへの依頼もレビュー観点も揃う。', {
    x: 1.05, y: 4.82, w: 7.9, h: 0.28,
    fontFace: FONT, fontSize: 14, bold: true,
    color: C.black, align: 'center', margin: 0
  });
}

addSection('03', 'agent-skills を使う', 'チーム共通のルールを、AIへの依頼文に入れる。');

{
  const slide = pptx.addSlide();
  addSlideFrame(slide, 'agent-skillsとは', page++);
  addLead(slide, 'AIに渡す、チーム共通のルール集。');
  slide.addText('Repository', {
    x: 0.75, y: 1.55, w: 1.2, h: 0.24,
    fontFace: FONT, fontSize: 10, bold: true,
    color: C.mid, margin: 0
  });
  const repoUrl = 'https://github.com/n2p-' + 'noname' + 'produce/agent-skills';
  slide.addText('github.com/n2p-.../agent-skills', {
    x: 0.75, y: 1.86, w: 5.8, h: 0.3,
    fontFace: FONT, fontSize: 11,
    color: C.link, margin: 0,
    hyperlink: { url: repoUrl },
    fit: 'shrink'
  });
  addNumberCard(slide, '01', 'AIっぽいUIを避けるルール', '見た目の癖を抑え、提案意図が伝わるモックに寄せる。', 0.75, 2.55, 2.6, 1.18);
  addNumberCard(slide, '02', '実装を軽くするルール', 'TailwindやFLOCSS、JavaScriptを増やしすぎない判断基準を渡す。', 3.65, 2.55, 2.6, 1.18);
  addNumberCard(slide, '03', 'AIに貼る指示テンプレート', '毎回ゼロから依頼文を考えず、案件要件を足すだけにする。', 6.55, 2.55, 2.6, 1.18);
  slide.addText('エンジニアだけでなく、ディレクターがモック依頼前に使うための土台。', {
    x: 0.95, y: 4.35, w: 8.0, h: 0.3,
    fontFace: FONT, fontSize: 13, bold: true,
    color: C.black, align: 'center', margin: 0,
    fit: 'shrink'
  });
}

{
  const slide = pptx.addSlide();
  addSlideFrame(slide, '使い方は、まず貼るだけでいい', page++);
  addLead(slide, '最初から完璧に運用しなくていい。次の依頼で1回貼ってみる。');
  slide.addImage({ path: ILLUSTRATIONS.slide12, x: 1.6, y: 1.34, w: 6.8, h: 3.83 });
  addEditableLabel(slide, 'リポジトリ', 1.82, 1.72, 1.35, { fontSize: 10.5 });
  addEditableLabel(slide, 'ルール', 4.48, 1.66, 1.05, { fontSize: 10.5 });
  addEditableLabel(slide, 'AI依頼', 6.88, 1.72, 1.25, { fontSize: 10.5 });
  addEditableLabel(slide, 'UI', 3.75, 4.32, 0.8, { fontSize: 9.5 });
  addEditableLabel(slide, '実装', 5.1, 4.32, 0.8, { fontSize: 9.5 });
}

{
  const slide = pptx.addSlide();
  addSlideFrame(slide, 'まとめ：AIを使うほど、最初のルールが効く', page++);
  addLead(slide, 'AIモックを個人技ではなく、チームで使える制作基盤にする。');
  addBullets(slide, [
    'ポン出しは、もう差別化にならない',
    'ポン出ししてきた感は、提案の信頼を下げる',
    '中途半端な装飾は、誤解を生む',
    '感覚指示は、共通ルールに変えられる',
    'agent-skills は、そのための土台',
    'まずは次のモック依頼で1回使う'
  ], 0.85, 1.55, 4.8, { fontSize: 11.5, gap: 0.45 });
  slide.addShape(pptx.ShapeType.rect, {
    x: 6.25, y: 1.55, w: 2.65, h: 2.4,
    fill: { color: C.lite },
    line: { color: C.divider, width: 0.5 }
  });
  slide.addText('使う\n見る\n戻す', {
    x: 6.6, y: 1.94, w: 1.95, h: 0.95,
    fontFace: FONT, fontSize: 24, bold: true,
    color: C.black, align: 'center', valign: 'middle', margin: 0,
    fit: 'shrink'
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 6.85, y: 3.18, w: 1.45, h: 0,
    line: { color: C.yellowD, width: 2 }
  });
  slide.addText('テンプレートを貼る\n出力を見る\n足りないところをルールに戻す', {
    x: 6.55, y: 3.38, w: 2.05, h: 0.42,
    fontFace: FONT, fontSize: 9.2,
    color: C.body, align: 'center', margin: 0,
    fit: 'shrink'
  });
}

{
  const slide = pptx.addSlide();
  addBg(slide);
  slide.addImage({ path: LOGO_BLACK, x: 3.5, y: 2.0, w: 3.0, h: 0.99 });
  slide.addText('Thank you', {
    x: 0, y: 3.2, w: W, h: 0.35,
    fontFace: FONT, fontSize: 14, color: C.body,
    align: 'center', margin: 0
  });
}

pptx.writeFile({ fileName: path.join(EXAMPLE_DIR, 'agent-skills-promotion.pptx') });
