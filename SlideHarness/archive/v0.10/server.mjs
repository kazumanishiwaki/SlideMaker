import http from 'node:http';
import fs from 'node:fs/promises';
import fssync from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CodexAppServerClient } from './src/codex-app-server-client.mjs';
import { ProjectStore } from './src/project-store.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 4317);
const PUBLIC = path.join(__dirname, 'public');
const WORKSPACE = path.join(__dirname, 'workspace');
const SKILL = path.join(__dirname, 'skill', 'SKILL.md');
const ENGINE = path.join(__dirname, 'engine', 'cli.py');

const store = new ProjectStore({ root: WORKSPACE, engineCli: ENGINE });
const codex = new CodexAppServerClient({ cwd: __dirname });
const sseClients = new Set();
const activeTurns = new Map();

function broadcast(event) {
  const payload = `data: ${JSON.stringify(event)}\n\n`;
  for (const res of sseClients) {
    try { res.write(payload); } catch {}
  }
}

for (const event of ['status', 'stderr', 'notification', 'agent_delta', 'turn_completed', 'server_request', 'protocol_error']) {
  codex.on(event, broadcast);
}

function json(res, code, value) {
  const body = JSON.stringify(value);
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'content-length': Buffer.byteLength(body) });
  res.end(body);
}

async function bodyJson(req, maxBytes = 120 * 1024 * 1024) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > maxBytes) throw new Error('request too large');
    chunks.push(chunk);
  }
  const text = Buffer.concat(chunks).toString('utf8');
  return text ? JSON.parse(text) : {};
}

function mime(file) {
  const ext = path.extname(file).toLowerCase();
  return ({
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
    '.svg': 'image/svg+xml', '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  })[ext] || 'application/octet-stream';
}

async function serveFile(res, file) {
  try {
    const data = await fs.readFile(file);
    res.writeHead(200, { 'content-type': mime(file), 'cache-control': 'no-store' });
    res.end(data);
  } catch {
    json(res, 404, { error: 'not found' });
  }
}

async function readState(projectId) {
  return store.readJson(projectId, 'state/project_state.json', {});
}
async function writeState(projectId, state) {
  return store.writeJson(projectId, 'state/project_state.json', state);
}
async function fileMtime(projectId, relativePath) {
  try { return (await fs.stat(store.safeProjectPath(projectId, relativePath))).mtimeMs; } catch { return 0; }
}

async function captureTurnInputs(projectId, slideId = null) {
  return {
    deck: await fileMtime(projectId, 'planning/deck_plan.json'),
    plans: await fileMtime(projectId, 'planning/slide_plans.json'),
    plan: slideId ? await fileMtime(projectId, `planning/slide_plans/${slideId}.json`) : 0,
    recipes: await fileMtime(projectId, 'planning/image_recipes.json'),
  };
}

const SLIDE_PHASES = ['deck_plan','slide_plan','image','layout','render','qa'];

function ensureStateSlide(state, slideId) {
  state.slides ||= {};
  state.slides[slideId] ||= {};
  for (const phase of SLIDE_PHASES) state.slides[slideId][phase] ||= 'DRAFT';
  return state.slides[slideId];
}

async function refreshContinuityAndImageState(projectId, state, slideIds = null) {
  const layoutPlanning = await store.planLayouts(projectId, { slides: slideIds });
  for (const row of layoutPlanning.parsed?.errors || []) {
    const ss = ensureStateSlide(state, row.slide_id);
    if (!['LOCKED','STALE_LOCKED'].includes(ss.layout)) ss.layout = 'ERROR';
  }
  await store.refreshContinuity(projectId);
  const recipesDoc = await store.readJson(projectId, 'planning/image_recipes.json', { recipes: [] });
  const manifest = await store.readJson(projectId, 'render/generated_assets/manifest.json', { selected_by_recipe: {} });
  const requested = slideIds ? new Set(slideIds) : null;
  const bySlide = new Map();
  for (const recipe of recipesDoc.recipes || []) {
    if (requested && !requested.has(recipe.slide_id)) continue;
    if (!bySlide.has(recipe.slide_id)) bySlide.set(recipe.slide_id, []);
    bySlide.get(recipe.slide_id).push(recipe);
  }
  const deck = await store.readJson(projectId, 'planning/deck_plan.json', { slides: [] });
  for (const slide of deck.slides || []) {
    const sid = slide.slide_id;
    if (requested && !requested.has(sid)) continue;
    const ss = ensureStateSlide(state, sid);
    if (['LOCKED','STALE_LOCKED'].includes(ss.image)) continue;
    const recipes = bySlide.get(sid) || [];
    if (!recipes.length) {
      ss.image = 'APPROVED';
      continue;
    }
    const missingTarget = recipes.some(r => !(((r.target || {}).source_object_id || (r.target || {}).layout_slot_id) && (r.target || {}).bbox));
    const ready = recipes.every(r => r.selected_asset_id && (manifest.selected_by_recipe || {})[r.recipe_id] === r.selected_asset_id);
    ss.image = missingTarget ? 'REVIEW_REQUIRED' : (ready ? 'APPROVED' : 'DRAFT');
  }
  return { recipesDoc, manifest, layoutPlanning: layoutPlanning.parsed || layoutPlanning };
}

async function applyImageQaState(projectId, state, slideIds = null) {
  const qa = await store.validateImages(projectId);
  const imageQa = qa.parsed?.image_harmony || { checks: [] };
  const recipesDoc = await store.readJson(projectId, 'planning/image_recipes.json', { recipes: [] });
  const requested = slideIds ? new Set(slideIds) : null;
  const slides = new Set((recipesDoc.recipes || []).map(r => r.slide_id).filter(Boolean));
  if (requested) for (const sid of [...slides]) if (!requested.has(sid)) slides.delete(sid);
  for (const sid of slides) {
    const ss = ensureStateSlide(state, sid);
    if (['LOCKED','STALE_LOCKED'].includes(ss.image)) continue;
    const checks = (imageQa.checks || []).filter(c => c.slide_id === sid);
    const blocking = checks.some(c => c.result === 'fail' && c.severity === 'blocking');
    const warning = checks.some(c => c.result === 'fail' && c.severity !== 'blocking');
    ss.image = blocking ? 'ERROR' : (warning ? 'REVIEW_REQUIRED' : 'APPROVED');
    if (!['LOCKED','STALE_LOCKED'].includes(ss.render)) ss.render = 'STALE';
    if (!['LOCKED','STALE_LOCKED'].includes(ss.qa)) ss.qa = 'STALE';
  }
  state.deck_harmony = slides.size ? 'STALE' : state.deck_harmony;
  return qa;
}

function isLockedState(state, slideId) {
  const s = state?.slides?.[slideId] || {};
  return Object.values(s).some(v => v === 'LOCKED' || v === 'STALE_LOCKED');
}

async function finalizeTurnContext(event) {
  const turnId = event?.turn?.id || event?.turnId;
  const ctx = activeTurns.get(turnId);
  if (!ctx) return;
  activeTurns.delete(turnId);
  const { projectId, task, slideId, before = {} } = ctx;
  const state = await readState(projectId);
  const deck = await store.readJson(projectId, 'planning/deck_plan.json', { slides: [] });

  if (task === 'structure') {
    // Structure remains user-reviewable. Approval happens only at Gate C.
    state.project ||= {};
    state.project.ui_state = 'structure_review';
    state.project.status = 'DRAFT';
    await refreshContinuityAndImageState(projectId, state);
  } else if (task === 'samples') {
    const compiled = await store.compilePlans(projectId);
    if (compiled.parsed?.blocking_count) throw new Error('Slide Plan semantic validation failed');
    const selection = await store.readJson(projectId, 'planning/sample_selection.json', { slides: [] });
    const sampleIds = (selection.slides || []).map(x => x.slide_id).filter(Boolean);
    for (const sid of sampleIds) {
      if (!(await fileMtime(projectId, `planning/slide_plans/${sid}.json`))) continue;
      const ss = ensureStateSlide(state, sid);
      ss.slide_plan = 'APPROVED';
      ss.layout = 'DRAFT';
      ss.render = 'DRAFT';
      ss.qa = 'DRAFT';
    }
    await refreshContinuityAndImageState(projectId, state, sampleIds);
  } else if (task === 'qa_fix') {
    const changed = [];
    for (const sid of ctx.slideIds || []) {
      const after = await fileMtime(projectId, `planning/slide_plans/${sid}.json`);
      if (after > (ctx.planMtimes?.[sid] || 0)) {
        changed.push(sid);
        const ss = ensureStateSlide(state, sid);
        ss.slide_plan = 'APPROVED';
        ss.layout = 'DRAFT';
        ss.render = 'DRAFT';
        ss.qa = 'DRAFT';
      }
    }
    if (changed.length) await refreshContinuityAndImageState(projectId, state, changed);
  } else if (task === 'full_deck') {
    const compiled = await store.compilePlans(projectId);
    if (compiled.parsed?.blocking_count) throw new Error('Slide Plan semantic validation failed');
    state.project ||= {};
    state.project.ui_state = 'page_review';
    state.project.status = 'DRAFT';
    for (const slide of deck.slides || []) {
      const sid = slide.slide_id;
      if (!sid || !(await fileMtime(projectId, `planning/slide_plans/${sid}.json`))) continue;
      const ss = ensureStateSlide(state, sid);
      if (!isLockedState(state, sid)) {
        ss.slide_plan = 'APPROVED';
        ss.layout = 'DRAFT';
        ss.render = 'DRAFT';
        ss.qa = 'DRAFT';
      }
    }
    await refreshContinuityAndImageState(projectId, state);
  } else if (task === 'message' && slideId) {
    const after = await captureTurnInputs(projectId, slideId);
    const ss = ensureStateSlide(state, slideId);
    if (after.deck > (before.deck || 0)) ss.deck_plan = 'DRAFT';
    if (after.plans > (before.plans || 0)) {
      const compiled = await store.compilePlans(projectId);
      if (compiled.parsed?.blocking_count) ss.slide_plan = 'REVIEW_REQUIRED';
      else ss.slide_plan = 'APPROVED';
      await refreshContinuityAndImageState(projectId, state, [slideId]);
    }
    if (after.plan > (before.plan || 0)) {
      ss.slide_plan = 'APPROVED';
      ss.layout = 'DRAFT';
      ss.render = 'DRAFT';
      ss.qa = 'DRAFT';
    }
  }
  await writeState(projectId, state);
}

codex.on('turn_completed', (event) => {
  finalizeTurnContext(event).catch((error) => broadcast({ type:'host_error', scope:'turn_finalize', error:error.message }));
});

async function ensureThread(projectId, model = 'gpt-5.6-sol') {
  const projectDir = store.projectDir(projectId);
  const state = await readState(projectId);
  let threadId = state?.project?.thread_id;
  if (threadId) {
    try { await codex.resumeThread({ threadId }); return threadId; } catch {}
  }
  const started = await codex.startThread({ cwd: projectDir, model });
  threadId = started.thread.id;
  state.project ||= {};
  state.project.thread_id = threadId;
  await writeState(projectId, state);
  return threadId;
}

function structurePrompt() {
  return [
    'このプロジェクトを Gate C（全体構成の確認）まで進めてください。',
    'analysis/manuscript_analysis.json, analysis/source_slides.json, analysis/template_profile.json, inputs/design.md を読んでください。',
    'このターンでAIが更新する計画ファイルは planning/deck_plan.json だけです。',
    '原稿と制作メモを分離し、1スライド1メッセージを基本にページ構成・順番・Primary Messageを決めてください。',
    '画像、元PPT候補、レイアウト、表示文はまだ決めません。',
    '判断ログはDeck構成の採否に必要な短い reason_codes だけにしてください。',
    'このターンではPPTX生成を行わず、構成レビューで止めてください。',
  ].join('\n');
}

function samplePlanPrompt() {
  return [
    'Gate Cで承認済みのDeck Planを基に、全ページのSlide Planを一括で作成してください。これは通常生成の2回目で最後の計画ターンです。',
    'planning/deck_plan.json, analysis/source_slides.json, analysis/source_assets.json, analysis/manuscript_analysis.json, inputs/design.md を読んでください。',
    'skill/schemas/slide_plans.schema.json に従い planning/slide_plans.json を作成してください。',
    '各ページで message / semantic_chunks / semantic_relation / visual / source / layout / content / image を一つのSlide Planへまとめてください。',
    'semantic_chunks は意味境界です。文字数を均等化するために壊さないでください。',
    '意味とLayoutの対応は statement / sequence / cause_effect / comparison / containment / parallel_categories / hierarchy / evidence / transformation / data を使ってください。',
    '座標は書かず、公開Layout Familyと階層だけを選びます。内部Rendererは statement / grid / media / flow / data の5系統です。',
    '写真・スクリーンショットは内容を説明する場合だけ required=true にし、空白埋めは禁止です。図表・フローはPowerPointネイティブ要素を優先してください。',
    'planning/sample_selection.json に性質の異なる代表3ページを保存してください。',
    'decisions/decision_trace.jsonl は元PPT・Layout・意味変更など主要判断のみ、短いreason_codesで記録してください。',
    'このターンではPPTXを生成せず、全Slide Planのレビュー可能状態で止めてください。',
  ].join('\n');
}

function qaRepairPrompt() {
  return [
    'QAで指定されたページだけを、1回だけ再計画してください。',
    'qa/sample_deck_qa.json, planning/slide_plans.json, planning/sample_selection.json を読んでください。',
    'Technical QAは決定論的修正を優先し、Content/Design問題だけSlide Planを修正してください。',
    'Primary Message、原稿の事実、source_text/semantic_textは勝手に変更しないでください。表示文はsemantic_chunksから作り直してください。',
    '修正順は文章整理、Layout Variant変更の順です。2回目の自動再計画は禁止し、解決しなければREVIEW_REQUIREDにしてください。',
    '無関係なページ、LOCKEDページ、template_chromeを変更しないでください。',
    'このターンではPPTXを生成せず、planning/slide_plans.jsonの該当行だけを更新してください。',
  ].join('\n');
}


function fullDeckPlanPrompt() {
  return [
    '通常は planning/slide_plans.json が全ページ分すでに存在します。欠落またはREVIEW_REQUIREDのページだけを補完してください。',
    '既存の承認済みSlide PlanとLOCKEDページは変更しないでください。',
    '新しい判断フェーズを増やさず、Slide Planの一行へ表現・元PPT・文章・画像・Layoutをまとめてください。',
    'このターンではPPTXを生成しません。',
  ].join('\n');
}


async function handleApi(req, res, url) {
  if (req.method === 'GET' && url.pathname === '/api/health') {
    return json(res, 200, { ok: true, node: process.version, codexReady: codex.available });
  }
  if (req.method === 'GET' && url.pathname === '/api/events') {
    res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' });
    res.write(`data: ${JSON.stringify({ type: 'hello', codexReady: codex.available })}\n\n`);
    sseClients.add(res);
    req.on('close', () => sseClients.delete(res));
    return;
  }
  if (req.method === 'POST' && url.pathname === '/api/codex/connect') {
    try {
      await codex.start();
      const account = await codex.accountRead();
      if (!account?.account && account?.requiresOpenaiAuth) {
        return json(res, 200, { ok: true, account, models: { data: [] }, needsAuth: true });
      }
      const models = await codex.modelList();
      return json(res, 200, { ok: true, account, models, needsAuth: false });
    } catch (e) {
      return json(res, 503, { ok: false, error: e.message, hint: 'Codex CLIをインストールしてください。接続後はこのUIからChatGPTログインを開始できます。' });
    }
  }
  if (req.method === 'POST' && url.pathname === '/api/codex/login') {
    try {
      await codex.start();
      const payload = await bodyJson(req, 1024 * 1024);
      const result = payload?.mode === 'device' ? await codex.loginDeviceCode() : await codex.loginChatGPT();
      return json(res, 200, { ok: true, ...result });
    } catch (e) { return json(res, 503, { ok: false, error: e.message }); }
  }
  if (req.method === 'POST' && url.pathname === '/api/codex/logout') {
    try { await codex.logout(); return json(res, 200, { ok: true }); }
    catch (e) { return json(res, 503, { ok: false, error: e.message }); }
  }
  if (req.method === 'GET' && url.pathname === '/api/codex/models') {
    try { return json(res, 200, await codex.modelList()); } catch (e) { return json(res, 503, { error: e.message }); }
  }
  if (req.method === 'GET' && url.pathname === '/api/codex/account') {
    try { return json(res, 200, await codex.accountRead()); } catch (e) { return json(res, 503, { error: e.message }); }
  }
  if (req.method === 'POST' && url.pathname.startsWith('/api/approvals/')) {
    const requestId = url.pathname.split('/').pop();
    try {
      const { decision = 'decline' } = await bodyJson(req, 1024 * 1024);
      codex.respondToServerRequest(requestId, { decision });
      return json(res, 200, { ok: true });
    } catch (e) { return json(res, 400, { error: e.message }); }
  }
  if (req.method === 'GET' && url.pathname === '/api/projects') {
    return json(res, 200, { projects: await store.list() });
  }
  if (req.method === 'POST' && url.pathname === '/api/projects') {
    try {
      const payload = await bodyJson(req);
      const result = await store.createFromUploads(payload);
      return json(res, 201, result);
    } catch (e) { return json(res, 400, { error: e.message }); }
  }
  if (req.method === 'POST' && url.pathname === '/api/demo/prepare') {
    try {
      const projectId = 'demo';
      const projectDir = store.projectDir(projectId);
      await fs.rm(projectDir, { recursive: true, force: true });
      await store.runPython([
        'init', '--project', projectDir,
        '--ppt', path.join(__dirname, 'examples/test-case/inputs/source.pptx'),
        '--manuscript', path.join(__dirname, 'examples/test-case/inputs/manuscript.docx'),
        '--design', path.join(__dirname, 'examples/test-case/design.md'),
      ]);
      await store.analyze(projectId);
      return json(res, 200, { projectId, snapshot: await store.snapshot(projectId) });
    } catch (e) { return json(res, 500, { error: e.message }); }
  }

  const m = url.pathname.match(/^\/api\/projects\/([^/]+)(?:\/(.*))?$/);
  if (m) {
    const projectId = decodeURIComponent(m[1]);
    const action = m[2] || '';
    if (req.method === 'GET' && action === 'snapshot') {
      return json(res, 200, await store.snapshot(projectId));
    }
    if (req.method === 'POST' && action === 'analyze') {
      try {
        const result = await store.analyze(projectId);
        const project = await store.readJson(projectId, 'project.json', {});
        let imageBootstrap = null;
        if ((project.uploaded_assets || []).length) {
          try {
            imageBootstrap = await store.generateImages(projectId, { provider:'auto' });
            const nextState = await readState(projectId);
            await refreshContinuityAndImageState(projectId, nextState);
            await applyImageQaState(projectId, nextState);
            await writeState(projectId, nextState);
          } catch (imageError) {
            imageBootstrap = { warning:imageError.message };
          }
        }
        return json(res, 200, { ok: true, log: result, imageBootstrap:imageBootstrap?.parsed || imageBootstrap, snapshot: await store.snapshot(projectId) });
      } catch (e) { return json(res, 500, { error: e.message }); }
    }
    if (req.method === 'POST' && action === 'build-skeleton') {
      try {
        const result = await store.buildSkeleton(projectId);
        return json(res, 200, { ok: true, result: result.parsed, download: `/project/${encodeURIComponent(projectId)}/file?path=${encodeURIComponent('output/template_skeleton.pptx')}` });
      } catch (e) { return json(res, 500, { error: e.message }); }
    }
    if (req.method === 'POST' && action === 'image-action') {
      try {
        const payload = await bodyJson(req, 45 * 1024 * 1024);
        const recipeId = String(payload.recipeId || '').trim();
        const operation = String(payload.action || '').trim();
        if (!recipeId && operation !== 'validate') throw new Error('recipeId is required');

        const state = await readState(projectId);
        await refreshContinuityAndImageState(projectId, state);
        const recipesDoc = await store.readJson(projectId, 'planning/image_recipes.json', { recipes: [] });
        const recipe = recipeId ? (recipesDoc.recipes || []).find(x => x.recipe_id === recipeId) : null;
        if (recipeId && !recipe) throw new Error('image recipe not found');
        if (recipe?.slide_id && isLockedState(state, recipe.slide_id)) throw new Error('このページは固定されています。固定解除してから画像を変更してください。');

        let result = null;
        if (operation === 'upload') {
          const relativePath = await store.saveImageUpload(projectId, {
            recipeId,
            filename: payload.filename || 'image.png',
            base64: payload.base64,
          });
          result = await store.generateImages(projectId, {
            provider: 'manual',
            recipes: [recipeId],
            manual: { [recipeId]: relativePath },
          });
        } else if (operation === 'generate') {
          const supported = new Set(['auto','local','openai','mock']);
          const provider = supported.has(payload.provider) ? payload.provider : 'auto';
          result = await store.generateImages(projectId, {
            provider,
            recipes: [recipeId],
            quality: payload.quality || process.env.OPENAI_IMAGE_QUALITY || 'medium',
            model: payload.model || process.env.OPENAI_IMAGE_MODEL || 'gpt-image-2',
            allowMock: provider === 'mock',
          });
        } else if (operation === 'select') {
          if (!payload.assetId) throw new Error('assetId is required');
          result = await store.selectImage(projectId, recipeId, payload.assetId);
        } else if (operation === 'update-recipe') {
          result = await store.updateImageRecipe(projectId, recipeId, {
            prompt: payload.prompt ?? null,
            negativeSpace: payload.negativeSpace ?? null,
            focalPoint: payload.focalPoint ?? null,
          });
        } else if (operation === 'validate') {
          result = await store.validateImages(projectId);
        } else {
          throw new Error('unknown image action');
        }
        const touched = recipe?.slide_id ? [recipe.slide_id] : null;
        const nextState = await readState(projectId);
        let imageQa = null;
        if (operation === 'update-recipe') {
          await refreshContinuityAndImageState(projectId, nextState, touched);
        } else {
          imageQa = await applyImageQaState(projectId, nextState, touched);
        }
        await writeState(projectId, nextState);
        return json(res, 200, { ok: true, result: result?.parsed || result, imageQa: imageQa?.parsed || imageQa, snapshot: await store.snapshot(projectId) });
      } catch (e) {
        const status = /OPENAI_API_KEY|No uploaded image candidate/.test(e.message) ? 409 : 400;
        return json(res, status, { error: e.message });
      }
    }

    if (req.method === 'POST' && action === 'compose') {
      try {
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        const slides = Array.isArray(payload.slides) ? payload.slides : null;
        const output = payload.output || (slides?.length ? 'sample_deck.pptx' : 'presentation_draft.pptx');
        await store.planLayouts(projectId, { slides });
        const result = await store.compose(projectId, { slides, output });
        const qa = await store.validateOutput(projectId, `output/${output}`, slides?.length ? 'sample' : 'draft');
        const state = await readState(projectId);
        const composedIds = result.parsed?.slide_count ? ((await store.readJson(projectId, `output/${path.parse(output).name}_compose_report.json`, { slides: [] })).slides || []).map(x => x.slide_id) : [];
        for (const sid of composedIds) {
          const ss = ensureStateSlide(state, sid);
          if (!['LOCKED','STALE_LOCKED'].includes(ss.layout)) ss.layout = 'APPROVED';
          if (!['LOCKED','STALE_LOCKED'].includes(ss.render)) ss.render = 'APPROVED';
          const slideChecks = (qa.parsed?.checks || []).filter(c => c.slide_id === sid);
          const failed = slideChecks.some(c => c.result === 'fail' && c.severity === 'blocking');
          const imageFailed = slideChecks.some(c => String(c.check_id || '').startsWith('IMAGE_') && c.result === 'fail' && c.severity === 'blocking');
          const imageWarning = slideChecks.some(c => String(c.check_id || '').startsWith('IMAGE_') && c.result === 'fail' && c.severity !== 'blocking');
          if (!['LOCKED','STALE_LOCKED'].includes(ss.image) && slideChecks.some(c => String(c.check_id || '').startsWith('IMAGE_'))) ss.image = imageFailed ? 'ERROR' : (imageWarning ? 'REVIEW_REQUIRED' : 'APPROVED');
          if (!['LOCKED','STALE_LOCKED'].includes(ss.qa)) ss.qa = failed ? 'ERROR' : 'APPROVED';
        }
        await writeState(projectId, state);
        return json(res, 200, { ok: true, result: result.parsed, qa: qa.parsed, download: `/project/${encodeURIComponent(projectId)}/file?path=${encodeURIComponent(`output/${output}`)}` });
      } catch (e) { return json(res, 500, { error: e.message }); }
    }
    if (req.method === 'POST' && action === 'export-final') {
      try {
        await store.planLayouts(projectId, { slides:null });
        const deck = await store.readJson(projectId, 'planning/deck_plan.json', { slides: [] });
        const state = await readState(projectId);
        const imageRecipes = await store.readJson(projectId, 'planning/image_recipes.json', { recipes: [] });
        const imageManifest = await store.readJson(projectId, 'render/generated_assets/manifest.json', { assets: [], selected_by_recipe: {} });
        const imageAssetsById = new Map((imageManifest.assets || []).map(asset => [asset.asset_id, asset]));
        const imageBySlide = new Map();
        for (const recipe of imageRecipes.recipes || []) {
          if (!recipe.slide_id) continue;
          if (!imageBySlide.has(recipe.slide_id)) imageBySlide.set(recipe.slide_id, []);
          imageBySlide.get(recipe.slide_id).push(recipe);
        }
        const blockers = [];
        const current = (v) => v === 'APPROVED' || v === 'LOCKED';
        for (const slide of deck.slides || []) {
          const sid=slide.slide_id;
          const plan=await store.readJson(projectId, `planning/slide_plans/${sid}.json`, null);
          const ss=state?.slides?.[sid] || {};
          if (!plan) { blockers.push({ slide_id:sid, code:'MISSING_SLIDE_PLAN' }); continue; }
          const executable = plan.composer_support === 'supported' || plan.composer_support === 'layout_engine' || (plan.composer_support === 'requires_layout_engine' && plan.layout_request);
          if (!executable) blockers.push({ slide_id:sid, code:'UNSUPPORTED_LAYOUT', reason:plan.layout_engine_reason || null });
          const slideRecipes = imageBySlide.get(sid) || [];
          for (const recipe of slideRecipes) {
            const target = recipe.target || {};
            const hasTarget = Boolean((target.source_object_id || target.layout_slot_id) && target.bbox);
            if (!hasTarget) {
              blockers.push({ slide_id:sid, code:'IMAGE_RECIPE_REVIEW_REQUIRED', recipe_id:recipe.recipe_id, reason:recipe.review_reason || 'No resolved source or Layout Engine image slot' });
            } else if (!recipe.selected_asset_id) {
              blockers.push({ slide_id:sid, code:'MISSING_IMAGE_ASSET', recipe_id:recipe.recipe_id });
            } else {
              const manifestSelection = (imageManifest.selected_by_recipe || {})[recipe.recipe_id];
              const selectedAsset = imageAssetsById.get(recipe.selected_asset_id);
              if (manifestSelection !== recipe.selected_asset_id || !selectedAsset) {
                blockers.push({ slide_id:sid, code:'IMAGE_ASSET_MANIFEST_MISMATCH', recipe_id:recipe.recipe_id, asset_id:recipe.selected_asset_id });
              } else if (selectedAsset.provider === 'mock') {
                blockers.push({ slide_id:sid, code:'IMAGE_PLACEHOLDER_NOT_DELIVERABLE', recipe_id:recipe.recipe_id, asset_id:recipe.selected_asset_id });
              } else if (!selectedAsset.processed_path) {
                blockers.push({ slide_id:sid, code:'IMAGE_PROCESSED_ASSET_MISSING', recipe_id:recipe.recipe_id, asset_id:recipe.selected_asset_id });
              }
            }
          }
          const requiredPhases = ['deck_plan','slide_plan', ...(slideRecipes.length ? ['image'] : [])];
          for (const phase of requiredPhases) {
            if (!current(ss[phase])) blockers.push({ slide_id:sid, code:'PHASE_NOT_CURRENT', phase, state:ss[phase] || 'DRAFT' });
          }
        }
        if (blockers.length) return json(res, 409, { error:'最終書き出しの前提を満たしていないページがあります。', blockers });

        const output='presentation_final.pptx';
        const result=await store.compose(projectId,{ slides:null, output });
        const qa=await store.validateOutput(projectId,`output/${output}`,'final');
        const harmony=await store.validateDeck(projectId);
        const next=await readState(projectId);
        const report=await store.readJson(projectId,'output/presentation_final_compose_report.json',{slides:[]});
        for (const item of report.slides || []) {
          const sid=item.slide_id; const ss=ensureStateSlide(next,sid);
          const slideChecks=(qa.parsed?.checks || []).filter(c => c.slide_id===sid);
          const failed=slideChecks.some(c => c.result==='fail' && c.severity==='blocking');
          const imageFailed=slideChecks.some(c => String(c.check_id || '').startsWith('IMAGE_') && c.result==='fail' && c.severity==='blocking');
          const imageWarning=slideChecks.some(c => String(c.check_id || '').startsWith('IMAGE_') && c.result==='fail' && c.severity!=='blocking');
          if (!['LOCKED','STALE_LOCKED'].includes(ss.image) && slideChecks.some(c => String(c.check_id || '').startsWith('IMAGE_'))) ss.image=imageFailed?'ERROR':(imageWarning?'REVIEW_REQUIRED':'APPROVED');
          if (!['LOCKED','STALE_LOCKED'].includes(ss.layout)) ss.layout='APPROVED';
          if (!['LOCKED','STALE_LOCKED'].includes(ss.render)) ss.render='APPROVED';
          if (!['LOCKED','STALE_LOCKED'].includes(ss.qa)) ss.qa=failed?'ERROR':'APPROVED';
        }
        next.deck_harmony=(harmony.parsed?.warning_count || 0) ? 'REVIEW_REQUIRED' : 'APPROVED';
        next.project ||= {}; next.project.ui_state='page_review'; next.project.status=qa.parsed?.status==='pass'?'FINAL_QA_PASS':'ERROR';
        await writeState(projectId,next);
        if (qa.parsed?.status !== 'pass') return json(res, 409, { error:`最終QAでblocking errorが ${qa.parsed?.blocking_count || 0} 件あります。`, qa:qa.parsed, harmony:harmony.parsed });
        return json(res,200,{ ok:true,result:result.parsed,qa:qa.parsed,harmony:harmony.parsed,download:`/project/${encodeURIComponent(projectId)}/file?path=${encodeURIComponent(`output/${output}`)}` });
      } catch (e) { return json(res,500,{ error:e.message }); }
    }
    if (req.method === 'POST' && action === 'codex/structure') {
      try {
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        const model = payload.model || 'gpt-5.6-sol';
        const threadId = await ensureThread(projectId, model);
        const turn = await codex.startTurn({ threadId, cwd: store.projectDir(projectId), text: structurePrompt(), skillPath: SKILL, model, effort: payload.effort || 'high' });
        if (turn.turn?.id) activeTurns.set(turn.turn.id, { projectId, task:'structure' });
        return json(res, 202, { ok: true, threadId, turn: turn.turn });
      } catch (e) { return json(res, 503, { error: e.message }); }
    }
    if (req.method === 'POST' && action === 'codex/samples') {
      try {
        const state = await readState(projectId);
        if (state?.project?.ui_state !== 'sample_review' && state?.project?.status !== 'APPROVED') {
          return json(res, 409, { error: '構成を承認してから代表ページ設計へ進んでください。' });
        }
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        const model = payload.model || 'gpt-5.6-sol';
        const threadId = await ensureThread(projectId, model);
        const turn = await codex.startTurn({ threadId, cwd: store.projectDir(projectId), text: samplePlanPrompt(), skillPath: SKILL, model, effort: payload.effort || 'high' });
        if (turn.turn?.id) activeTurns.set(turn.turn.id, { projectId, task:'samples' });
        return json(res, 202, { ok: true, threadId, turn: turn.turn });
      } catch (e) { return json(res, 503, { error: e.message }); }
    }
    if (req.method === 'POST' && action === 'codex/full-deck') {
      try {
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        const model = payload.model || 'gpt-5.6-sol';
        const state = await readState(projectId);
        if (state?.project?.ui_state === 'structure_review') return json(res, 409, { error:'構成を承認してから全ページ設計へ進んでください。' });
        const threadId = await ensureThread(projectId, model);
        const turn = await codex.startTurn({ threadId, cwd: store.projectDir(projectId), text: fullDeckPlanPrompt(), skillPath: SKILL, model, effort: payload.effort || 'high' });
        if (turn.turn?.id) activeTurns.set(turn.turn.id, { projectId, task:'full_deck' });
        return json(res, 202, { ok:true, threadId, turn:turn.turn });
      } catch (e) { return json(res, 503, { error:e.message }); }
    }
    if (req.method === 'POST' && action === 'codex/fix-qa') {
      try {
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        const model = payload.model || 'gpt-5.6-sol';
        const threadId = await ensureThread(projectId, model);
        const qa = await store.readJson(projectId, 'qa/sample_deck_qa.json', { checks: [] });
        const slideIds = [...new Set((qa.checks || []).filter(c => c.result === 'fail' && c.slide_id).map(c => c.slide_id))];
        const planMtimes = Object.fromEntries(await Promise.all(slideIds.map(async sid => [sid, await fileMtime(projectId, `planning/slide_plans/${sid}.json`)])));
        const turn = await codex.startTurn({ threadId, cwd: store.projectDir(projectId), text: qaRepairPrompt(), skillPath: SKILL, model, effort: payload.effort || 'high' });
        if (turn.turn?.id) activeTurns.set(turn.turn.id, { projectId, task:'qa_fix', slideIds, planMtimes });
        return json(res, 202, { ok: true, threadId, turn: turn.turn });
      } catch (e) { return json(res, 503, { error: e.message }); }
    }
    if (req.method === 'POST' && action === 'codex/message') {
      try {
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        const model = payload.model || 'gpt-5.6-sol';
        const state = await readState(projectId);
        if (payload.slideId && isLockedState(state, payload.slideId)) return json(res, 409, { error:'このページは固定されています。固定解除してから変更してください。' });
        const before = await captureTurnInputs(projectId, payload.slideId || null);
        const threadId = await ensureThread(projectId, model);
        const scopePrefix = payload.slideId ? `対象は ${payload.slideId} のみ。無関係なページを変更しないでください。\n` : '';
        const turn = await codex.startTurn({ threadId, cwd: store.projectDir(projectId), text: scopePrefix + payload.text, skillPath: SKILL, model, effort: payload.effort || 'high' });
        if (turn.turn?.id) activeTurns.set(turn.turn.id, { projectId, task:'message', slideId:payload.slideId || null, before });
        return json(res, 202, { ok: true, threadId, turn: turn.turn });
      } catch (e) { return json(res, 503, { error: e.message }); }
    }
    if (req.method === 'POST' && action === 'approve-structure') {
      const state = await readState(projectId);
      state.project ||= {};
      state.project.phase = 'planning';
      state.project.ui_state = 'sample_review';
      state.project.status = 'APPROVED';
      const deck = await store.readJson(projectId, 'planning/deck_plan.json', { slides: [] });
      for (const slide of deck.slides || []) {
        const ss = ensureStateSlide(state, slide.slide_id);
        ss.deck_plan = 'APPROVED';
        ss.slide_plan ||= 'DRAFT'; ss.image ||= 'DRAFT'; ss.layout ||= 'DRAFT'; ss.render ||= 'DRAFT'; ss.qa ||= 'DRAFT';
      }
      await refreshContinuityAndImageState(projectId, state);
      await writeState(projectId, state);
      return json(res, 200, { ok: true, state });
    }
    if (req.method === 'POST' && action === 'asset-action') {
      try {
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        const assetId = payload.assetId;
        const classification = payload.classification;
        const policies = {
          template_chrome: 'keep',
          content_visual: 'replace',
          container_or_frame: 'replace_inner',
          unknown: 'review_required',
        };
        if (!assetId || !Object.prototype.hasOwnProperty.call(policies, classification)) throw new Error('assetId / valid classification are required');
        const assetsDoc = await store.readJson(projectId, 'analysis/source_assets.json', { assets: [] });
        const asset = assetsDoc.assets?.find(a => a.id === assetId);
        if (!asset) throw new Error('asset not found');
        const before = { classification: asset.classification, action_policy: asset.action_policy, status: asset.status };
        asset.classification = classification;
        asset.action_policy = policies[classification];
        asset.status = classification === 'unknown' ? 'REVIEW_REQUIRED' : 'APPROVED';
        asset.origin = 'user_override';
        assetsDoc.summary = Object.fromEntries(['template_chrome','content_visual','container_or_frame','unknown'].map(k => [k, assetsDoc.assets.filter(a => a.classification === k).length]));
        await store.writeJson(projectId, 'analysis/source_assets.json', assetsDoc);
        await store.refreshContinuity(projectId);

        const matches = await store.readJson(projectId, 'planning/slide_matching.json', { slides: [] });
        const state = await readState(projectId);
        state.slides ||= {};
        const affected = [];
        for (const m of matches.slides || []) {
          const selected = m.selected || m.candidates?.[0];
          if (selected?.source_slide_id !== asset.source_slide_id) continue;
          affected.push(m.slide_id);
          state.slides[m.slide_id] ||= {};
          for (const phase of ['slide_plan','image','layout','render','qa']) {
            state.slides[m.slide_id][phase] = state.slides[m.slide_id][phase] === 'LOCKED' ? 'STALE_LOCKED' : 'STALE';
          }
        }
        state.deck_harmony = affected.length ? 'STALE' : state.deck_harmony;
        await writeState(projectId, state);
        const tracePath = store.safeProjectPath(projectId, 'decisions/decision_trace.jsonl');
        await fs.mkdir(path.dirname(tracePath), { recursive: true });
        await fs.appendFile(tracePath, JSON.stringify({ decision_id:`USER-ASSET-${Date.now()}`, timestamp:new Date().toISOString(), phase:'source_asset_classification', target:{type:'asset',id:assetId}, decision_type:'asset_classification_override', selected:{classification,action_policy:policies[classification]}, previous:before, origin:'user', rerun_scope:affected.flatMap(id => [`${id}:slide_plan`,`${id}:image`,`${id}:layout`,`${id}:render`,`${id}:qa`]).concat(affected.length?['deck_harmony']:[]) }) + '\n');
        return json(res, 200, { ok: true, asset, affectedSlides: affected, state });
      } catch (e) { return json(res, 400, { error: e.message }); }
    }

    if (req.method === 'POST' && action === 'feedback') {
      try {
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        if (!payload.slideId || !payload.kind) throw new Error('slideId / kind are required');
        const state = await readState(projectId);
        if (isLockedState(state, payload.slideId)) return json(res, 409, { error:'このページは固定されています。固定解除してから変更してください。' });
        const result = await store.applyFeedback(projectId, { slideId:payload.slideId, kind:payload.kind, value:payload.value });
        return json(res, 200, { ok:true, result:result.parsed || result });
      } catch (e) { return json(res, 400, { error:e.message }); }
    }

    if (req.method === 'POST' && action === 'slide-action') {
      try {
        const payload = await bodyJson(req, 2 * 1024 * 1024);
        const slideId = payload.slideId;
        if (!slideId) throw new Error('slideId is required');
        const deck = await store.readJson(projectId, 'planning/deck_plan.json', { slides: [] });
        const slide = deck.slides?.find(s => s.slide_id === slideId);
        if (!slide) throw new Error('slide not found');
        const state = await readState(projectId);
        state.slides ||= {};
        state.slides[slideId] ||= {};
        if (payload.action === 'approve') {
          slide.status = 'APPROVED';
          state.slides[slideId].deck_plan = 'APPROVED';
        } else if (payload.action === 'lock') {
          state.lock_snapshots ||= {};
          state.lock_snapshots[slideId] = { ...state.slides[slideId] };
          slide.status = 'LOCKED';
          for (const phase of ['deck_plan','slide_plan','image','layout','render','qa']) state.slides[slideId][phase] = 'LOCKED';
        } else if (payload.action === 'unlock') {
          const snapshot = state.lock_snapshots?.[slideId] || {};
          slide.status = snapshot.deck_plan === 'DRAFT' ? 'DRAFT' : 'APPROVED';
          for (const phase of ['deck_plan','slide_plan','image','layout','render','qa']) {
            if (state.slides[slideId][phase] === 'STALE_LOCKED') state.slides[slideId][phase] = 'STALE';
            else if (state.slides[slideId][phase] === 'LOCKED') state.slides[slideId][phase] = snapshot[phase] || 'DRAFT';
          }
          if (state.lock_snapshots) delete state.lock_snapshots[slideId];
        } else if (payload.action === 'fill-policy') {
          if (isLockedState(state, slideId)) throw new Error('このページは固定されています。固定解除してから変更してください。');
          const allowed = new Set(['auto','preserve_source','intentional_whitespace','balanced','content_filled','full_bleed']);
          const mode = String(payload.value || '').trim();
          if (!allowed.has(mode)) throw new Error('valid fill policy is required');
          const planPath = `planning/slide_plans/${slideId}.json`;
          const plan = await store.readJson(projectId, planPath, null);
          if (mode === 'full_bleed' && plan?.layout_request?.family && plan.layout_request.family !== 'full_bleed') {
            throw new Error('full_bleed方針はfull_bleed Layout Familyのページでのみ利用できます。');
          }
          if (!plan) throw new Error('Slide Plan作成後にレイアウト方針を変更できます。');
          if (!plan.layout_request?.family) throw new Error('既存レイアウトを直接流用するページです。レイアウトから見直す場合はCodexへ指示してください。');
          const before = plan.fill_policy || plan.layout_request?.fill_policy || null;
          if (mode === 'auto') {
            delete plan.fill_policy;
          } else {
            plan.fill_policy = {
              mode,
              source:'user',
              reason:['ユーザーがページ単位でレイアウト方針を指定'],
              preserve_empty_zones: ['preserve_source','intentional_whitespace'].includes(mode),
            };
          }
          if (plan.layout_request && Object.prototype.hasOwnProperty.call(plan.layout_request,'fill_policy')) delete plan.layout_request.fill_policy;
          plan.status = 'APPROVED';
          await store.writeJson(projectId, planPath, plan);
          state.slides[slideId].slide_plan = 'APPROVED';
          for (const phase of ['layout','render','qa']) {
            if (state.slides[slideId][phase] === 'LOCKED') state.slides[slideId][phase] = 'STALE_LOCKED';
            else state.slides[slideId][phase] = 'STALE';
          }
          state.deck_harmony = 'STALE';
          const tracePath = store.safeProjectPath(projectId, 'decisions/decision_trace.jsonl');
          await fs.mkdir(path.dirname(tracePath), { recursive: true });
          await fs.appendFile(tracePath, JSON.stringify({
            decision_id:`USER-FILL-${Date.now()}`,
            timestamp:new Date().toISOString(),
            phase:'slide_plan',
            target:{type:'slide',id:slideId},
            decision_type:'fill_policy_override',
            selected:mode === 'auto' ? { mode:'auto', source:'user', reason:['自動判定へ戻す'] } : plan.fill_policy,
            previous:before,
            origin:'user',
            rerun_scope:[`${slideId}:layout`,`${slideId}:render`,`${slideId}:qa`,'deck_harmony'],
          }) + '\n');
        } else if (payload.action === 'message') {
          if (isLockedState(state, slideId)) throw new Error('このページは固定されています。固定解除してから変更してください。');
          const before = slide.primary_message;
          slide.primary_message = String(payload.value || '').trim();
          slide.origin = 'user_override';
          for (const phase of ['slide_plan','image','layout','render','qa']) {
            if (state.slides[slideId][phase] === 'LOCKED') state.slides[slideId][phase] = 'STALE_LOCKED'; else state.slides[slideId][phase] = 'STALE';
          }
          state.deck_harmony = 'STALE';
          const tracePath = store.safeProjectPath(projectId, 'decisions/decision_trace.jsonl');
          await fs.mkdir(path.dirname(tracePath), { recursive: true });
          await fs.appendFile(tracePath, JSON.stringify({ decision_id:`USER-${Date.now()}`, timestamp:new Date().toISOString(), phase:'deck_plan', target:{type:'slide',id:slideId}, decision_type:'primary_message_override', selected:slide.primary_message, previous:before, origin:'user', rerun_scope:[`${slideId}:slide_plan`,`${slideId}:layout`,`${slideId}:qa`,'deck_harmony'] }) + '\n');
        } else {
          throw new Error('unknown slide action');
        }
        await store.writeJson(projectId, 'planning/deck_plan.json', deck);
        await writeState(projectId, state);
        return json(res, 200, { ok: true, slide, state });
      } catch (e) { return json(res, 400, { error: e.message }); }
    }
  }

  const fm = url.pathname.match(/^\/project\/([^/]+)\/file$/);
  if (req.method === 'GET' && fm) {
    try {
      const projectId = decodeURIComponent(fm[1]);
      const rel = url.searchParams.get('path') || '';
      const { target } = await store.fileInfo(projectId, rel);
      return serveFile(res, target);
    } catch (e) { return json(res, 404, { error: e.message }); }
  }
  return false;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  try {
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/project/')) {
      const handled = await handleApi(req, res, url);
      if (handled !== false) return;
    }
    let rel = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\//, '');
    const target = path.resolve(PUBLIC, rel);
    if (!target.startsWith(PUBLIC + path.sep) && target !== PUBLIC) return json(res, 403, { error: 'forbidden' });
    await serveFile(res, target);
  } catch (e) {
    json(res, 500, { error: e.message });
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`PPT Codex App Server client: http://127.0.0.1:${PORT}`);
  console.log('Codex connection is lazy; use the UI Connect button.');
});
