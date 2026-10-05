const path = require('path');
const pptxgen = require('pptxgenjs');
const { imageSize } = require('image-size');

const pptx = new pptxgen();

const ROOT = path.resolve(__dirname, '../../..');
const WORK = path.resolve(__dirname, '..');
const OUT = path.join(WORK, 'output');

const LOGO_BLACK = path.join(ROOT, 'assets/symbol_black.png');
const LOGO_WHITE = path.join(ROOT, 'assets/symbol_white.png');

const IMG = {
  gacha: path.join(WORK, 'generated-assets/skill-usage-lt/slide-03/image-v2.png'),
  package: path.join(WORK, 'generated-assets/skill-usage-lt/slide-07/image-v2.png'),
  loop: path.join(WORK, 'generated-assets/skill-usage-lt/slide-11/image-v2.png'),
};

const C = {
  black: '111111',
  white: 'FCFCFC',
  cover: 'D7DEE2',
  lite: 'E6EBED',
  body: '434343',
  mid: '929699',
  dark: '676A6D',
  footer: '999999',
  divider: 'CCCCCC',
  yellow: 'F4F400',
  yellowD: 'E8E800',
};

const FONT = 'Noto Sans JP';
const W = 10;
const H = 5.625;

pptx.author = 'NONAME Produce';
pptx.company = 'NONAME Produce Inc.';
pptx.subject = 'Skill usage LT';
pptx.title = 'Skillを使って、AIガチャを止めて、無駄トークンをなくそう';
pptx.lang = 'ja-JP';
pptx.defineLayout({ name: 'n2p', width: W, height: H });
pptx.layout = 'n2p';
pptx.theme = {
  headFontFace: FONT,
  bodyFontFace: FONT,
  lang: 'ja-JP',
};
pptx.margin = 0;

let page = 1;

function bg(slide, color = C.white) {
  slide.background = { color };
}

function addLogoBlack(slide) {
  slide.addImage({ path: LOGO_BLACK, x: 8.9, y: 0.15, w: 0.9, h: 0.3 });
}

function addLogoWhite(slide) {
  slide.addImage({ path: LOGO_WHITE, x: 8.9, y: 0.15, w: 0.9, h: 0.3 });
}

function addCoverWatermark(slide) {
  slide.addImage({ path: LOGO_BLACK, x: 6.2, y: 4.02, w: 3.6, h: 1.19, transparency: 70 });
}

function addFooter(slide) {
  slide.addShape('line', {
    x: 0.28, y: 5.28, w: 9.44, h: 0,
    line: { color: C.divider, width: 0.5 },
  });
  slide.addText('© 2026 NONAME Produce Inc.', {
    x: 0.28, y: 5.30, w: 3.6, h: 0.22,
    fontFace: FONT, fontSize: 8, color: C.footer,
  });
  slide.addText(String(page), {
    x: 9.2, y: 5.30, w: 0.5, h: 0.22,
    fontFace: FONT, fontSize: 9, color: C.footer, align: 'right',
  });
  page += 1;
}

function addBodyChrome(slide, title) {
  bg(slide);
  addLogoBlack(slide);
  slide.addShape('line', {
    x: 0.05, y: 0.35, w: 0.45, h: 0,
    line: { color: C.black, width: 1 },
  });
  slide.addText(title, {
    x: 0.55, y: 0.14, w: 7.7, h: 0.42,
    fontFace: FONT, fontSize: title.length > 24 ? 14 : 16,
    bold: true, color: C.black, valign: 'middle',
    fit: 'shrink',
  });
  addFooter(slide);
}

function addKicker(slide, text, x, y, w) {
  slide.addShape('rect', {
    x, y, w, h: 0.09,
    fill: { color: C.yellowD },
    line: { color: C.yellowD, transparency: 100 },
  });
  slide.addText(text, {
    x, y: y + 0.12, w, h: 0.2,
    fontFace: FONT, fontSize: 8, color: C.mid, bold: true,
    margin: 0,
  });
}

function text(slide, str, x, y, w, h, opts = {}) {
  slide.addText(str, {
    x, y, w, h,
    fontFace: opts.fontFace || FONT,
    fontSize: opts.fontSize || 11,
    color: opts.color || C.body,
    bold: opts.bold || false,
    breakLine: false,
    fit: opts.fit || 'shrink',
    valign: opts.valign || 'top',
    align: opts.align || 'left',
    margin: opts.margin === undefined ? 0.04 : opts.margin,
    paraSpaceAfterPt: opts.paraSpaceAfterPt === undefined ? 4 : opts.paraSpaceAfterPt,
  });
}

function bullets(slide, items, x, y, w, h, opts = {}) {
  const body = items.map((item) => `• ${item}`).join('\n');
  text(slide, body, x, y, w, h, {
    fontSize: opts.fontSize || 11,
    color: opts.color || C.body,
    fit: 'shrink',
    paraSpaceAfterPt: 6,
  });
}

function card(slide, x, y, w, h, title, body, opts = {}) {
  slide.addShape('rect', {
    x, y, w, h,
    fill: { color: opts.fill || C.white },
    line: { color: opts.line || C.black, width: opts.lineWidth || 0.8 },
  });
  if (opts.accent) {
    slide.addShape('rect', {
      x, y, w: 0.08, h,
      fill: { color: opts.accent },
      line: { color: opts.accent, transparency: 100 },
    });
  }
  text(slide, title, x + 0.18, y + 0.17, w - 0.36, 0.26, {
    fontSize: opts.titleSize || 13,
    bold: true,
    color: C.black,
    margin: 0,
  });
  text(slide, body, x + 0.18, y + 0.55, w - 0.36, h - 0.7, {
    fontSize: opts.bodySize || 10.5,
    color: C.body,
    fit: 'shrink',
  });
}

function label(slide, str, x, y, w, opts = {}) {
  slide.addShape('roundRect', {
    x, y, w, h: 0.3,
    fill: { color: opts.fill || C.lite },
    line: { color: opts.fill || C.lite, transparency: 100 },
    rectRadius: 0.02,
  });
  text(slide, str, x, y + 0.04, w, 0.2, {
    fontSize: opts.fontSize || 9.5,
    color: opts.color || C.black,
    bold: true,
    align: 'center',
    margin: 0,
  });
}

function codeBlock(slide, lines, x, y, w, h, opts = {}) {
  slide.addShape('rect', {
    x, y, w, h,
    fill: { color: opts.fill || C.lite },
    line: { color: opts.line || C.black, width: opts.lineWidth || 0.7 },
  });
  text(slide, Array.isArray(lines) ? lines.join('\n') : lines, x + 0.18, y + 0.16, w - 0.36, h - 0.26, {
    fontFace: 'Helvetica Neue',
    fontSize: opts.fontSize || 9.2,
    color: opts.color || C.black,
    margin: 0,
    paraSpaceAfterPt: 2,
    fit: 'shrink',
  });
}

function arrow(slide, x, y, w, color = C.black) {
  slide.addShape('line', {
    x, y, w, h: 0,
    line: { color, width: 1.2, beginArrowType: 'none', endArrowType: 'triangle' },
  });
}

function addImageContain(slide, imagePath, x, y, w, h) {
  const size = imageSize(imagePath);
  const ratio = size.width / size.height;
  let iw = w;
  let ih = w / ratio;
  if (ih > h) {
    ih = h;
    iw = h * ratio;
  }
  slide.addImage({
    path: imagePath,
    x: x + (w - iw) / 2,
    y: y + (h - ih) / 2,
    w: iw,
    h: ih,
  });
}

function addTitleSlide() {
  const slide = pptx.addSlide();
  bg(slide, C.cover);
  addCoverWatermark(slide);
  text(slide, 'Skillを使って、', 0.88, 1.54, 8.2, 0.45, {
    fontSize: 22, bold: true, color: C.black, margin: 0,
  });
  text(slide, 'AIガチャを止めて、\n無駄トークンをなくそう', 0.86, 1.98, 8.4, 1.05, {
    fontSize: 28, bold: true, color: C.black, margin: 0,
  });
  text(slide, 'AIに毎回考えさせず、速度と質が安定したアウトプットを気軽につくる', 0.9, 3.24, 7.4, 0.34, {
    fontSize: 13, color: C.body, margin: 0,
  });
  text(slide, '5分LT / 非エンジニア向け', 0.9, 4.56, 3.4, 0.25, {
    fontSize: 10, color: C.footer, margin: 0,
  });
}

function addConclusionSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, '今日話すこと');
  text(slide, '結論', 0.76, 0.92, 1.2, 0.26, { fontSize: 13, bold: true, color: C.black, margin: 0 });
  slide.addShape('rect', {
    x: 0.76, y: 1.24, w: 8.45, h: 0.86,
    fill: { color: C.lite },
    line: { color: C.lite, transparency: 100 },
  });
  text(slide, 'AIガチャを止めるには、AIにやってもらうことを明確にする。\nそのために Skill を使う。', 0.98, 1.40, 7.9, 0.52, {
    fontSize: 16, bold: true, color: C.black, margin: 0,
  });
  const items = [
    ['1', 'AIガチャが起きる理由', '曖昧な依頼のまま、毎回AIに「それっぽく」考えさせている。'],
    ['2', '何がまずいのか', '出力がブレる。トークンを使う。文脈が汚れる。'],
    ['3', 'Skillで何が変わるのか', '共通ルールを作業パッケージとして渡し、今回の内容だけを考えさせる。'],
  ];
  items.forEach((it, i) => {
    const y = 2.58 + i * 0.75;
    slide.addShape('ellipse', { x: 0.82, y, w: 0.34, h: 0.34, fill: { color: C.black }, line: { color: C.black, transparency: 100 } });
    text(slide, it[0], 0.82, y + 0.06, 0.34, 0.15, { fontSize: 8.5, bold: true, color: C.white, align: 'center', margin: 0 });
    text(slide, it[1], 1.36, y - 0.02, 2.4, 0.24, { fontSize: 12.5, bold: true, color: C.black, margin: 0 });
    text(slide, it[2], 3.45, y - 0.02, 5.4, 0.36, { fontSize: 10.5, color: C.body, margin: 0 });
  });
}

function addGachaSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'AIガチャとは何か');
  text(slide, '曖昧な依頼を出し、期待と違うたびに引き直す状態。', 0.72, 0.76, 8.2, 0.28, {
    fontSize: 13, color: C.body, margin: 0,
  });
  addImageContain(slide, IMG.gacha, 0.70, 1.00, 8.55, 3.86);
  label(slide, 'なんとなく依頼', 0.80, 4.78, 1.55);
  label(slide, '再生成ループ', 4.04, 4.78, 1.55, { fill: C.yellow });
  label(slide, 'トークン・文脈の消耗', 7.18, 4.78, 1.95);
}

function addVagueStateSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'うまく使えていない状態');
  text(slide, '問題はAIの能力だけではなく、何を任せるかが曖昧なこと。', 0.72, 0.76, 8.4, 0.28, {
    fontSize: 13, color: C.body, margin: 0,
  });
  slide.addShape('rect', { x: 0.86, y: 1.18, w: 3.1, h: 3.24, fill: { color: C.lite }, line: { color: C.lite, transparency: 100 } });
  const flow = ['いい感じにして', 'なんか違う', 'もう少し普通に', '今度は弱すぎる', '最初の方がよかったかも'];
  flow.forEach((s, i) => {
    text(slide, s, 1.1, 1.42 + i * 0.53, 2.45, 0.21, {
      fontSize: 11, color: i % 2 === 0 ? C.black : C.body, bold: i % 2 === 0, margin: 0,
    });
    if (i < flow.length - 1) {
      text(slide, '↓', 2.25, 1.70 + i * 0.53, 0.3, 0.18, { fontSize: 10, color: C.mid, align: 'center', margin: 0 });
    }
  });
  slide.addShape('line', { x: 4.55, y: 1.16, w: 0, h: 3.30, line: { color: C.divider, width: 0.5 } });
  text(slide, '曖昧なまま依頼すると、AIは毎回「それっぽく」考える。', 5.10, 1.26, 3.95, 0.58, {
    fontSize: 16, bold: true, color: C.black, margin: 0,
  });
  bullets(slide, [
    '前提が固定されない',
    '判断基準が会話ごとに揺れる',
    '人間側が何度も引き直す',
    '最後は出力も文脈も疲れる',
  ], 5.18, 2.18, 3.8, 1.36);
  text(slide, 'AIを使っているつもりが、実際にはAIガチャを回している。', 5.18, 4.00, 3.75, 0.45, {
    fontSize: 12, bold: true, color: C.black, margin: 0,
  });
}

function addCostSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'AIガチャが起きると何がまずいか');
  const cards = [
    ['1', '出力が安定しない', '見た目、構成、実装方針、言葉が毎回少しずつ変わる。'],
    ['2', 'トークンを無駄に使う', 'やり直しのたびに会話が長くなり、重要でない文脈が増える。'],
    ['3', 'コンテクストが汚れる', 'ボツ案、途中変更、一時的な修正が残り、何を優先すべきか曖昧になる。'],
  ];
  cards.forEach((c, i) => {
    const x = 0.72 + i * 3.05;
    slide.addShape('rect', { x, y: 1.18, w: 2.55, h: 3.06, fill: { color: i === 1 ? C.lite : C.white }, line: { color: C.black, width: 0.8 } });
    slide.addShape('ellipse', { x: x + 0.2, y: 1.46, w: 0.42, h: 0.42, fill: { color: i === 1 ? C.yellowD : C.black }, line: { color: i === 1 ? C.yellowD : C.black, transparency: 100 } });
    text(slide, c[0], x + 0.2, 1.54, 0.42, 0.15, { fontSize: 9, bold: true, color: i === 1 ? C.black : C.white, align: 'center', margin: 0 });
    text(slide, c[1], x + 0.2, 2.02, 2.1, 0.52, { fontSize: 14, bold: true, color: C.black, margin: 0 });
    text(slide, c[2], x + 0.2, 2.88, 2.1, 0.84, { fontSize: 10.5, color: C.body, margin: 0 });
  });
  text(slide, '単なる時間の問題ではなく、出力の集中力が落ちる問題。', 0.78, 4.56, 8.25, 0.25, {
    fontSize: 12, bold: true, color: C.black, align: 'center', margin: 0,
  });
}

function addSeparationSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'では、どうすればいいか');
  text(slide, '毎回AIに考えさせない。任せる部分と、任せない部分を分ける。', 0.72, 0.76, 8.5, 0.3, {
    fontSize: 13, color: C.body, margin: 0,
  });
  card(slide, 0.78, 1.30, 4.05, 2.86, '毎回変えなくていいもの', 'PPTXの色ルール\nロゴの配置\nフッターの位置\n余白\n見出しのスタイル\n画像生成の保存場所\nリテイク履歴の残し方', {
    fill: C.lite, accent: C.black, titleSize: 14, bodySize: 10.8,
  });
  card(slide, 5.18, 1.30, 4.05, 2.86, '今回だけ考えるもの', '誰に話すのか\n何を伝えるのか\nどの素材を使うのか\n何ページにするのか\nどの主張を残すのか\n今回の制約は何か', {
    fill: C.white, accent: C.yellowD, titleSize: 14, bodySize: 10.8,
  });
  arrow(slide, 4.66, 2.72, 0.46, C.black);
  text(slide, 'AIの仕事を「ゼロから全部考える」から「決めた型に沿って実行する」へ近づける。', 1.06, 4.54, 7.9, 0.28, {
    fontSize: 12.5, bold: true, color: C.black, align: 'center', margin: 0,
  });
}

function addSkillPackageSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'そこで Skill');
  text(slide, 'Skillは、AIに渡す作業パッケージ。長いプロンプトではなく、作業環境を固定する仕組み。', 0.72, 0.76, 8.3, 0.32, {
    fontSize: 12.8, color: C.body, margin: 0,
  });
  addImageContain(slide, IMG.package, 4.86, 1.04, 4.22, 3.17);
  addKicker(slide, 'PACKAGE CONTENTS', 0.78, 1.28, 2.5);
  bullets(slide, [
    '作業手順',
    '判断基準',
    '禁止事項',
    '参照資料',
    '素材',
    '補助スクリプト',
    'QAチェックリスト',
  ], 0.92, 1.86, 3.45, 2.36);
  label(slide, '共通ルールを先に渡す', 5.16, 4.34, 2.1);
  label(slide, '今回の内容だけ当てはめる', 7.38, 4.34, 2.1, { fill: C.yellow });
}

function addBeforeAfterSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'Skillで何が変わるか');
  card(slide, 0.78, 1.18, 3.9, 3.28, 'Before: AIガチャ型', '「いい感じの提案資料を作って」\n「AIっぽくないUIにして」\n「シンプルに実装して」\n\nAIは毎回、広すぎる言葉を想像する。', {
    fill: C.white, accent: C.black, titleSize: 14,
  });
  card(slide, 5.28, 1.18, 3.9, 3.28, 'After: Skill活用型', '「n2p-pptx Skillを前提に、PPTXを作ってください」\n\n色、余白、ロゴ、フッター、表記をSkillに従わせる。', {
    fill: C.lite, accent: C.yellowD, titleSize: 14,
  });
  arrow(slide, 4.78, 2.82, 0.38, C.black);
  text(slide, '雰囲気ではなく、守るべき型を渡す。', 2.22, 4.72, 5.6, 0.25, {
    fontSize: 13, bold: true, color: C.black, align: 'center', margin: 0,
  });
}

function addFourSkillsSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, '今回のSkillの例');
  const items = [
    ['n2p PPTX Skill', '色、フォント、余白、フッター、ロゴ、企業名表記を固定する。'],
    ['n2p Slide Illustration Skill', '入れるスライド、トーン、保存場所、リテイク履歴を管理する。'],
    ['AIっぽいデザインを避けるSkill', 'グラデーション、強い影、大きすぎる見出しを避ける。'],
    ['Tailwind × FLOCSS Skill', 'CSS設計と実装判断を固定し、JSやライブラリを増やしすぎない。'],
  ];
  items.forEach((it, i) => {
    const x = 0.72 + (i % 2) * 4.45;
    const y = 1.10 + Math.floor(i / 2) * 1.72;
    card(slide, x, y, 3.92, 1.28, it[0], it[1], {
      fill: i === 1 ? C.lite : C.white,
      accent: i === 1 ? C.yellowD : C.black,
      titleSize: 12.4,
      bodySize: 9.6,
    });
  });
  text(slide, '共通ルール = Skill / 今回の内容 = プロンプト', 1.24, 4.58, 7.5, 0.28, {
    fontSize: 13, bold: true, color: C.black, align: 'center', margin: 0,
  });
}

function addHowToSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, '使い方はシンプル');
  const steps = [
    ['1', 'clone / pull', 'Skillを置いたリポジトリを手元に持ち、作業前に最新化する。'],
    ['2', 'Skillを選ぶ', 'PPTX、イラスト、UI、HTML/CSSなど、作業に合うSkillを選ぶ。'],
    ['3', '最初に読ませる', '途中ではなく、作業の最初に「このSkill前提」と明示する。'],
    ['4', '今回の要件だけ足す', '対象、ページ数、目的、素材、今回だけの制約を追加する。'],
  ];
  steps.forEach((s, i) => {
    const y = 1.02 + i * 0.82;
    slide.addShape('ellipse', { x: 0.82, y, w: 0.42, h: 0.42, fill: { color: i === 2 ? C.yellowD : C.black }, line: { color: i === 2 ? C.yellowD : C.black, transparency: 100 } });
    text(slide, s[0], 0.82, y + 0.08, 0.42, 0.15, { fontSize: 9, bold: true, color: i === 2 ? C.black : C.white, align: 'center', margin: 0 });
    text(slide, s[1], 1.50, y - 0.02, 2.0, 0.24, { fontSize: 13, bold: true, color: C.black, margin: 0 });
    text(slide, s[2], 3.28, y - 0.02, 5.55, 0.36, { fontSize: 10.5, color: C.body, margin: 0 });
    if (i < steps.length - 1) {
      slide.addShape('line', { x: 1.03, y: y + 0.43, w: 0, h: 0.34, line: { color: C.divider, width: 1 } });
    }
  });
  slide.addShape('rect', { x: 0.92, y: 4.58, w: 8.1, h: 0.34, fill: { color: C.lite }, line: { color: C.lite, transparency: 100 } });
  text(slide, 'Skillは共通ルール。プロンプトは今回だけの内容。', 0.92, 4.66, 8.1, 0.15, {
    fontSize: 11, bold: true, color: C.black, align: 'center', margin: 0,
  });
}

function addGitCloneSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'まず、GitHubからcloneする');
  text(slide, 'チームで共有しているSkillやルールを、作業前に手元へ持ってくる。すでにclone済みならpullで最新化する。', 0.72, 0.76, 8.5, 0.34, {
    fontSize: 12.5, color: C.body, margin: 0,
  });
  codeBlock(slide, [
    '$ git clone https://github.com/n2p-nonameproduce/agent-skills.git',
    '$ cd agent-skills',
  ], 0.84, 1.36, 8.3, 0.88, { fontSize: 9.3 });
  codeBlock(slide, [
    '$ git pull origin main',
  ], 0.84, 2.70, 8.3, 0.58, { fontSize: 9.3, fill: C.white });
  addKicker(slide, 'POINT', 0.86, 3.72, 1.2);
  bullets(slide, [
    'Skillは「AIに読ませるルール置き場」と考える',
    '作業のたびに最新版を使うと、チームの判断基準が揃う',
    '非エンジニアでも、clone済みのフォルダを指定して読ませればよい',
  ], 1.00, 4.12, 8.0, 0.72, { fontSize: 10.2 });
}

function addPromptExampleSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'プロンプト例');
  text(slide, '最初の依頼で「共通ルール」と「今回の内容」を分けて渡す。これだけで、出力のブレがかなり減る。', 0.72, 0.76, 8.5, 0.34, {
    fontSize: 12.5, color: C.body, margin: 0,
  });
  codeBlock(slide, [
    'まず、n2p-pptx Skillを読んでください。',
    '今回の作業では、色・余白・ロゴ・フッター・企業名表記は',
    'すべてSkillのルールを前提にしてください。',
    '',
    '入力はこのMarkdownです。',
    '5分LT向けに、13枚前後のPPTXへ要約してください。',
  ], 0.78, 1.26, 4.15, 2.78, { fontSize: 8.2 });
  codeBlock(slide, [
    'PPTXを作ったあと、n2p-slide-illustration Skillを読んでください。',
    '理解が速くなるスライドだけを選び、',
    'n2pトーンの生成イラストを追加してください。',
    '',
    '画像内に重要な文字は入れず、',
    'ラベルはPPTX上で編集できるようにしてください。',
  ], 5.18, 1.26, 4.05, 2.78, { fontSize: 8.2, fill: C.white });
  text(slide, '雰囲気の依頼ではなく、守るべき型を先に渡す。', 1.20, 4.54, 7.6, 0.26, {
    fontSize: 13, bold: true, color: C.black, align: 'center', margin: 0,
  });
}

function addImproveLoopSlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, '使う・見る・戻す');
  text(slide, '失敗を毎回チャットで直すのではなく、次の改善材料としてSkillに戻す。', 0.72, 0.76, 8.4, 0.3, {
    fontSize: 12.8, color: C.body, margin: 0,
  });
  addImageContain(slide, IMG.loop, 0.90, 1.02, 8.2, 3.72);
  label(slide, '使う', 1.10, 4.74, 1.2);
  label(slide, '出力を見る', 4.38, 4.74, 1.45, { fill: C.lite });
  label(slide, 'Skillに戻す', 7.40, 4.74, 1.55, { fill: C.yellow });
  text(slide, 'AIを育てるというより、AIに渡す作業環境を育てる。', 1.30, 4.42, 7.35, 0.24, {
    fontSize: 12.5, bold: true, color: C.black, align: 'center', margin: 0,
  });
}

function addSummarySlide() {
  const slide = pptx.addSlide();
  addBodyChrome(slide, 'まとめ');
  text(slide, 'AIガチャを止めるには、毎回考えなくていいことをSkillにしておく。', 0.78, 0.92, 8.2, 0.42, {
    fontSize: 17, bold: true, color: C.black, margin: 0,
  });
  const outcomes = ['速度が上がる', '品質が安定する', 'やり直しが減る', 'トークンを節約できる', '気軽にアウトプットできる'];
  outcomes.forEach((o, i) => {
    const x = 0.92 + (i % 3) * 2.95;
    const y = i < 3 ? 1.80 : 3.02;
    const w = i < 3 ? 2.42 : 3.22;
    slide.addShape('rect', { x, y, w, h: 0.82, fill: { color: i === 1 ? C.yellow : C.lite }, line: { color: C.black, width: 0.7 } });
    text(slide, o, x + 0.12, y + 0.27, w - 0.24, 0.16, { fontSize: 12, bold: true, color: C.black, align: 'center', margin: 0 });
  });
  text(slide, 'AIの仕事を、ゼロからの生成ではなく、決められた型に沿った実行に近づける。', 1.10, 4.50, 7.8, 0.28, {
    fontSize: 12.5, color: C.body, align: 'center', margin: 0,
  });
}

function addEndSlide() {
  const slide = pptx.addSlide();
  bg(slide, C.white);
  slide.addImage({ path: LOGO_BLACK, x: 3.5, y: 1.50, w: 3.0, h: 0.99 });
  text(slide, '毎回考えなくていいことを、Skillにしておく。', 1.28, 3.08, 7.45, 0.42, {
    fontSize: 20, bold: true, color: C.black, align: 'center', margin: 0,
  });
  text(slide, 'AIに全部考えさせない。それだけで、AIはかなり使いやすくなる。', 1.65, 3.72, 6.8, 0.24, {
    fontSize: 11.5, color: C.body, align: 'center', margin: 0,
  });
}

addTitleSlide();
addConclusionSlide();
addGachaSlide();
addVagueStateSlide();
addCostSlide();
addSeparationSlide();
addSkillPackageSlide();
addBeforeAfterSlide();
addFourSkillsSlide();
addHowToSlide();
addGitCloneSlide();
addPromptExampleSlide();
addImproveLoopSlide();
addSummarySlide();
addEndSlide();

pptx.writeFile({ fileName: path.join(OUT, 'skill-usage-lt-n2p.pptx') });
