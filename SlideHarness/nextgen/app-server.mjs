import http from 'node:http';
import fs from 'node:fs/promises';
import fssync from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { CodexAppServerClient } from './app/codex-app-server-client.mjs';
import {
  NextgenRunStore,
  ROLE_RULES,
  THREE_LEVELS,
  STRUCTURED_VISUAL_MODES,
  writeJsonAtomic,
} from './app/run-store.mjs';
import { NextgenPythonCore } from './app/python-core.mjs';
import { createCodexAppServerImageGenerator } from './app/image-generator.mjs';
import { NullPlanCache, PlanCache } from './app/plan-cache.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_WORKSPACE = path.join(here, 'workspace');
const PUBLIC = path.join(here, 'public');
const PLANNER_SKILL = path.join(here, 'skill', 'SKILL.md');

function resolveCodexBin() {
  if (process.env.CODEX_BIN) return process.env.CODEX_BIN;
  const bundled = '/Applications/ChatGPT.app/Contents/Resources/codex';
  return fssync.existsSync(bundled) ? bundled : 'codex';
}

function json(res, status, value) {
  const body = `${JSON.stringify(value)}\n`;
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  });
  res.end(body);
}

async function readBuffer(req, maxBytes) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > maxBytes) throw new Error('request too large');
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

async function readJson(req, maxBytes = 256 * 1024) {
  const body = await readBuffer(req, maxBytes);
  return body.length ? JSON.parse(body.toString('utf8')) : {};
}

function contentType(target) {
  return ({
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.pdf': 'application/pdf',
  })[path.extname(target).toLowerCase()] || 'application/octet-stream';
}

async function serveStatic(res, pathname) {
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const target = path.resolve(PUBLIC, relative);
  if (!target.startsWith(`${PUBLIC}${path.sep}`)) return json(res, 404, { error: 'not found' });
  try {
    const data = await fs.readFile(target);
    res.writeHead(200, { 'content-type': contentType(target), 'cache-control': 'no-store' });
    res.end(data);
  } catch {
    json(res, 404, { error: 'not found' });
  }
}

function planningPrompt(state) {
  const extra = state.instructions ? `\n追加指示:\n${state.instructions}` : '';
  const designGuide = state.files?.design_guide
    ? '\nprepared/design-guide/source_units.json は画像生成を含むデザイン指示書です。内容原稿と混ぜず、全スライドの視覚方針に適用してください。'
    : '';
  return [
    'prepared/planning_request.json, prepared/content_model.json, prepared/source_units.json,',
    'prepared/coverage_requirements.json, prepared/template_system.json, run_config.json を読み、',
    'plan/deck_spec.json を1つだけ作成してください。',
    '入力ファイルと prepared/ の成果物は変更しないでください。PPTX生成やPython実行は行わないでください。',
    '全required source unitを採用し、数値・日付・条件を創作せず、available_recipesだけを使用してください。',
    `情報量は3段階の「${state.information_density || 'medium'}」、装飾性は3段階の「${state.decorativeness || 'medium'}」として設計してください。`,
    `グラフ・フロー図の表現方式は「${state.structured_visual_mode || 'native'}」です。`,
    'metadata.information_density、metadata.decorativeness、metadata.structured_visual_mode に同じ値を記録してください。',
    '完了時は作成したスライド数と採用したrecipeだけを短く報告してください。',
    designGuide,
    extra,
  ].join('\n');
}

function regenerationPrompt(request) {
  return [
    'regeneration/request.json、regeneration/context.json、run_config.json を読み、',
    'regeneration/proposed_slide.json を1つだけ作成してください。',
    'トークンと誤参照を抑えるため、対象外ページのplanやprepared全体は読み込まず、context.json内の対象出典だけを根拠にしてください。',
    `対象は ${request.slide_id} の1ページだけです。slide_idは必ず維持し、ほかのスライドを変更しないでください。`,
    'proposed_slide.json はスライドオブジェクト単体とし、slide_id、title、message、recipe、source_unit_ids、content を含めます。',
    `対象ページの情報量は「${request.information_density}」、装飾性は「${request.decorativeness}」、グラフ・フロー図の表現方式は「${request.structured_visual_mode}」です。`,
    'フィードバックを満たしつつ、元ページのnarrative roleと根拠の対応を維持してください。必要な場合のみavailable_recipes内でrecipeを変更できます。',
    request.structured_visual_mode === 'generated-image'
      ? 'generated_visual用に対象ページ専用の新規asset_idを1つ追加できます。ほかの用途では既存の解決済みassetだけを使用してください。'
      : '既存の解決済みassetだけを使用し、新規の未解決asset_idは追加しないでください。',
    '入力、prepared/、plan/deck_spec.json、output/、state.json は変更しないでください。PPTX生成やPython実行は行わないでください。',
    request.feedback ? `ページ修正指示:\n${request.feedback}` : 'ページ修正指示: 同じ内容を設定値に合わせて再構成する。',
  ].join('\n');
}

async function writePlanningTask(store, runId, state) {
  const text = `# Codex planning task\n\n${planningPrompt(state)}\n`;
  await fs.writeFile(store.safePath(runId, 'PLAN_TASK.md'), text, 'utf8');
}

async function readJsonFile(target) {
  return JSON.parse(await fs.readFile(target, 'utf8'));
}

async function writeRegenerationContext(store, runId, request) {
  const sourceUnits = await readJsonFile(store.safePath(runId, 'prepared/source_units.json'));
  const allowed = new Set(request.current_slide?.source_unit_ids || []);
  const units = (sourceUnits.units || []).filter((unit) => allowed.has(unit.unit_id));
  const context = {
    schema_version: '0.4.0',
    request_id: request.request_id,
    slide_id: request.slide_id,
    current_slide: request.current_slide,
    source_unit_ids: [...allowed],
    source_units: units,
    exact_fact_count: units.reduce((sum, unit) => sum + (unit.facts || []).length, 0),
    design_guide_path: request.design_guide_path,
  };
  await writeJsonAtomic(store.safePath(runId, 'regeneration/context.json'), context);
  return context;
}

function validateLevel(value, fallback = 'medium') {
  const normalized = String(value || fallback);
  if (!THREE_LEVELS.has(normalized)) throw new Error('level must be low, medium, or high');
  return normalized;
}

function validateStructuredVisualMode(value, fallback = 'native') {
  const normalized = String(value || fallback);
  if (!STRUCTURED_VISUAL_MODES.has(normalized)) throw new Error('structured visual mode must be auto, native, or generated-image');
  return normalized;
}

export async function createNextgenServer({
  workspace = process.env.NEXTGEN_WORKSPACE || DEFAULT_WORKSPACE,
  codexBin = resolveCodexBin(),
  codexClient = null,
  imageGenerator = null,
  planCache = null,
} = {}) {
  const store = new NextgenRunStore(workspace);
  await store.init();
  const clients = new Set();
  const activeTurns = new Map();
  const pendingApprovals = new Map();
  const broadcast = (event) => {
    const payload = `data: ${JSON.stringify(event)}\n\n`;
    for (const client of clients) {
      try { client.write(payload); } catch {}
    }
  };
  const core = new NextgenPythonCore({ nextgenRoot: here, store, onEvent: broadcast });
  const codex = codexClient || new CodexAppServerClient({ codexBin, cwd: here });
  const images = imageGenerator || createCodexAppServerImageGenerator(codex);
  const cachedPlans = planCache === false ? new NullPlanCache() : (planCache || new PlanCache());

  async function generateAwaitingImages(runId, requests) {
    const awaiting = (requests || []).filter((item) => item.status === 'awaiting_image');
    if (!awaiting.length) return [];
    if (typeof images.ensureAvailable === 'function') await images.ensureAvailable();
    if (!images.available) throw new Error('automatic image generation is not configured');
    await store.updateState(runId, (current) => {
      current.status = 'generating_images';
      current.stage = 'image_generation';
      current.image_generation_error = null;
      return current;
    });
    const generated = [];
    for (const request of awaiting) {
      const started = Date.now();
      let result;
      try {
        result = await images.generate({ runId, request, runDir: store.runDir(runId) });
        let qualityReviewPath = null;
        if (result.qualityReview) {
          const safeAssetId = String(request.asset_id || 'generated-image').replace(/[^0-9A-Za-z._-]+/g, '-');
          qualityReviewPath = `image-generation/${safeAssetId}.quality.json`;
          await writeJsonAtomic(store.safePath(runId, qualityReviewPath), {
            schema_version: '0.4.0',
            asset_id: request.asset_id,
            provider: result.provider || images.provider || 'automatic-image-generator',
            model: result.model || null,
            attempts: result.attempts || 1,
            ...result.qualityReview,
          });
        }
        await store.writeUpload(runId, 'asset', result.filename || `${request.asset_id}.png`, result.buffer, {
          assetId: request.asset_id,
          provider: result.provider || images.provider || 'automatic-image-generator',
        });
        generated.push({
          asset_id: request.asset_id,
          provider: result.provider || images.provider || 'automatic-image-generator',
          model: result.model || null,
          attempts: result.attempts || 1,
          quality_minimum_score: result.qualityReview?.minimum_score || null,
          quality_review_path: qualityReviewPath,
          cache_hit: result.cacheHit === true,
          cache_key: result.cacheKey || null,
        });
      } finally {
        await store.appendUsage(runId, {
          kind: 'generative-image',
          stage: 'image_generation',
          provider: result?.provider || images.provider || 'automatic-image-generator',
          model: result?.model || null,
          duration_ms: Date.now() - started,
          cache_hit: result?.cacheHit === true,
          input_tokens: Number(result?.inputTokens),
          output_tokens: Number(result?.outputTokens),
          reason: `asset_id=${request.asset_id}`,
        });
      }
    }
    await store.updateState(runId, (current) => {
      const generatedIds = new Set(generated.map((item) => item.asset_id));
      current.generated_assets = [
        ...(current.generated_assets || []).filter((item) => !generatedIds.has(item.asset_id)),
        ...generated,
      ];
      return current;
    });
    return generated;
  }

  async function buildWithAutomaticImages(runId, { cachePlan = false, planCacheKey = null } = {}) {
    let built = await core.build(runId);
    if (built.status === 'awaiting_images') {
      try {
        if (typeof images.ensureAvailable === 'function') await images.ensureAvailable();
        if (!images.available) throw new Error('automatic image generation is not configured');
        const originalRequests = built.asset_requests;
        await generateAwaitingImages(runId, built.asset_requests);
        built = await core.build(runId);
        if (built.status === 'failed' && built.summary?.generated_image_qa === 'FAIL') {
          return store.updateState(runId, (current) => {
            current.status = 'awaiting_images';
            current.stage = 'image_resolution';
            current.asset_requests = originalRequests.map((item) => item.status === 'awaiting_image'
              ? { ...item, reason: 'automatic_generated_image_failed_qa' }
              : item);
            current.image_generation_error = '自動生成画像が品質検査に合格しませんでした。画像を差し替えてください。';
            current.error = null;
            return current;
          });
        }
        built = await store.updateState(runId, (current) => {
          current.image_generation_error = null;
          return current;
        });
      } catch (error) {
        return store.updateState(runId, (current) => {
          current.status = 'awaiting_images';
          current.stage = 'image_resolution';
          current.image_generation_error = error.message;
          current.error = null;
          return current;
        });
      }
    }
    if (cachePlan && built.status === 'completed' && cachedPlans.available) {
      const key = planCacheKey || await cachedPlans.keyForRun(store, runId, PLANNER_SKILL);
      const plan = await readJsonFile(store.safePath(runId, 'plan/deck_spec.json'));
      await cachedPlans.save(key, plan, built.summary);
    }
    return built;
  }

  async function applyRegeneration(context) {
    const { runId, request } = context;
    const state = await store.readState(runId);
    const currentRevision = Number(state.revision || 1);
    if (currentRevision !== request.expected_revision) {
      throw new Error(`revision conflict: expected ${request.expected_revision}, current ${currentRevision}`);
    }
    const root = store.runDir(runId);
    const currentPlanPath = path.join(root, 'plan', 'deck_spec.json');
    const currentDeckPath = path.join(root, 'output', 'deck.pptx');
    const proposedPath = path.join(root, 'regeneration', 'proposed_slide.json');
    const currentPlan = await readJsonFile(currentPlanPath);
    const proposed = await readJsonFile(proposedPath);
    const slideIndex = (currentPlan.slides || []).findIndex((slide) => slide.slide_id === request.slide_id);
    if (slideIndex < 0) throw new Error(`target slide ${request.slide_id} no longer exists`);
    if (!proposed || Array.isArray(proposed) || proposed.slide_id !== request.slide_id) {
      throw new Error('proposed slide must be one object with the unchanged target slide_id');
    }
    for (const field of ['title', 'message', 'recipe', 'source_unit_ids', 'content']) {
      if (!(field in proposed)) throw new Error(`proposed slide is missing ${field}`);
    }

    const candidatePlan = structuredClone(currentPlan);
    candidatePlan.slides[slideIndex] = proposed;
    candidatePlan.metadata = { ...(candidatePlan.metadata || {}) };
    candidatePlan.metadata.slide_policies = { ...(candidatePlan.metadata.slide_policies || {}) };
    candidatePlan.metadata.slide_policies[request.slide_id] = {
      information_density: request.information_density,
      decorativeness: request.decorativeness,
      structured_visual_mode: request.structured_visual_mode,
      regenerated_from_revision: currentRevision,
    };

    const work = path.join(root, 'regeneration', request.request_id);
    const candidatePlanPath = path.join(work, 'candidate-deck-spec.json');
    const candidateOutput = path.join(work, 'candidate-output');
    const finalOutput = path.join(work, 'final-output');
    const isolatedDeck = path.join(finalOutput, 'deck.pptx');
    const isolationReport = path.join(finalOutput, 'qa-page-isolation.json');
    await fs.mkdir(work, { recursive: true });
    await writeJsonAtomic(candidatePlanPath, candidatePlan);
    const candidate = await core.buildCandidate(runId, candidatePlanPath, candidateOutput, {
      informationDensity: request.information_density,
      decorativeness: request.decorativeness,
      structuredVisualMode: request.structured_visual_mode,
    });
    if (candidate.status !== 'completed') {
      if (candidate.awaiting?.length) {
        if (context.imagesResolved !== true) {
          try {
            await generateAwaitingImages(runId, candidate.assetRequests);
            return applyRegeneration({ ...context, imagesResolved: true });
          } catch (error) {
            await store.updateState(runId, (current) => {
              current.image_generation_error = error.message;
              return current;
            });
          }
        }
        return store.updateState(runId, (current) => {
          current.status = 'regeneration_awaiting_images';
          current.stage = 'image_resolution';
          current.asset_requests = candidate.assetRequests;
          current.active_regeneration = request;
          current.image_generation_error = current.image_generation_error || (images.available ? 'automatic image generation did not resolve the request' : null);
          current.error = null;
          return current;
        });
      }
      if (context.imagesResolved === true && candidate.summary?.generated_image_qa === 'FAIL') {
        return store.updateState(runId, (current) => {
          current.status = 'regeneration_awaiting_images';
          current.stage = 'image_resolution';
          current.asset_requests = (candidate.assetRequests || []).map((item) => item.kind === 'generated_image'
            ? { ...item, status: 'awaiting_image', reason: 'automatic_generated_image_failed_qa' }
            : item);
          current.active_regeneration = request;
          current.image_generation_error = '自動生成画像が品質検査に合格しませんでした。画像を差し替えてください。';
          current.error = null;
          return current;
        });
      }
      const detail = candidate.summary ? JSON.stringify(candidate.summary) : candidate.result?.stderr || '';
      throw new Error(`regenerated slide candidate failed composition or QA${detail ? `: ${detail}` : ''}`);
    }
    await fs.cp(candidateOutput, finalOutput, { recursive: true, force: true });
    await core.isolateSlide(runId, {
      base: currentDeckPath,
      candidate: candidate.artifact,
      slideIndex,
      output: isolatedDeck,
      report: isolationReport,
    });
    await core.verifyExisting(runId, {
      pptx: isolatedDeck,
      plan: candidatePlanPath,
      output: finalOutput,
      compositionMode: candidate.summary.composition_mode,
      informationDensity: request.information_density,
      decorativeness: request.decorativeness,
      structuredVisualMode: state.structured_visual_mode || 'native',
      allowShadows: state.allow_shadows === true,
    });

    const versionDir = path.join(root, 'versions', `rev-${String(currentRevision).padStart(4, '0')}`);
    await fs.mkdir(versionDir, { recursive: true });
    await Promise.all([
      fs.copyFile(currentPlanPath, path.join(versionDir, 'deck_spec.json')),
      fs.copyFile(currentDeckPath, path.join(versionDir, 'deck.pptx')),
    ]);
    const currentSummary = path.join(root, 'output', 'summary.json');
    if (fssync.existsSync(currentSummary)) await fs.copyFile(currentSummary, path.join(versionDir, 'summary.json'));

    const summaryPath = path.join(finalOutput, 'summary.json');
    const finalSummary = await readJsonFile(summaryPath);
    finalSummary.deck = path.join(root, 'output', 'deck.pptx');
    finalSummary.montage = path.join(root, 'output', 'render', 'montage.png');
    finalSummary.page_isolation_qa = 'PASS';
    finalSummary.regenerated_slide_id = request.slide_id;
    finalSummary.revision = currentRevision + 1;
    await writeJsonAtomic(summaryPath, finalSummary);

    const previousOutput = path.join(work, 'previous-output');
    const outputDir = path.join(root, 'output');
    await fs.rename(outputDir, previousOutput);
    try {
      await fs.rename(finalOutput, outputDir);
      await writeJsonAtomic(currentPlanPath, candidatePlan);
    } catch (error) {
      if (fssync.existsSync(outputDir)) await fs.rename(outputDir, path.join(work, 'failed-final-output'));
      await fs.rename(previousOutput, outputDir);
      throw error;
    }

    return store.updateState(runId, (current) => {
      current.status = 'completed';
      current.stage = 'completed';
      current.revision = currentRevision + 1;
      current.summary = finalSummary;
      current.artifact = 'output/deck.pptx';
      current.montage = 'output/render/montage.png';
      current.active_regeneration = null;
      current.last_regeneration = {
        request_id: request.request_id,
        slide_id: request.slide_id,
        slide_number: slideIndex + 1,
        from_revision: currentRevision,
        to_revision: currentRevision + 1,
        status: 'PASS',
        non_target_unchanged: true,
        qa_report: 'output/qa-page-isolation.json',
      };
      current.error = null;
      return current;
    });
  }

  for (const event of ['status', 'stderr', 'notification', 'agent_delta', 'protocol_error']) {
    codex.on(event, broadcast);
  }
  codex.on('server_request', async (event) => {
    const turnId = event?.params?.turnId;
    const active = activeTurns.get(turnId);
    const runId = typeof active === 'string' ? active : active?.runId || null;
    pendingApprovals.set(String(event.requestId), { ...event, runId });
    if (runId) {
      await store.updateState(runId, (current) => {
        current.pending_approval = {
          request_id: String(event.requestId),
          method: event.method,
          params: event.params || {},
        };
        return current;
      });
    }
    broadcast({ ...event, runId });
  });
  codex.on('turn_completed', async (event) => {
    const turnId = event?.turn?.id || event?.turnId;
    const active = activeTurns.get(turnId);
    if (!active) return;
    const context = typeof active === 'string' ? { runId: active, kind: 'plan' } : active;
    const { runId } = context;
    activeTurns.delete(turnId);
    try {
      const usage = event?.turn?.usage || event?.usage || {};
      await store.appendUsage(runId, {
        kind: 'generative-text',
        stage: context.kind === 'regenerate' ? 'codex_regeneration' : 'codex_planning',
        provider: 'signed-in-codex-host',
        model: context.model || null,
        duration_ms: context.startedAt ? Date.now() - context.startedAt : 0,
        input_tokens: Number(usage.input_tokens ?? usage.inputTokens),
        output_tokens: Number(usage.output_tokens ?? usage.outputTokens),
        reason: context.kind,
      });
      const status = event?.turn?.status || 'completed';
      if (status !== 'completed') throw new Error(`Codex planning turn ended with status ${status}`);
      let completed;
      if (context.kind === 'regenerate') {
        completed = await applyRegeneration(context);
      } else {
        await store.updateState(runId, (current) => {
          current.status = 'plan_ready';
          current.stage = 'compose_and_qa';
          return current;
        });
        broadcast({ type: 'run_status', runId, status: 'plan_ready' });
        completed = await buildWithAutomaticImages(runId, {
          cachePlan: true,
          planCacheKey: context.planCacheKey || null,
        });
      }
      broadcast({ type: 'run_status', runId, status: completed.status, state: completed });
    } catch (error) {
      const failed = await store.updateState(runId, (current) => {
        if (context.kind === 'regenerate' && current.artifact) {
          const activeRegeneration = current.active_regeneration;
          current.status = 'completed';
          current.stage = 'completed';
          current.active_regeneration = null;
          current.last_regeneration = {
            ...(activeRegeneration || {}),
            status: 'FAIL',
            error: error.message,
          };
          current.error = `ページ再生成は適用されませんでした: ${error.message}`;
        } else {
          current.status = 'failed';
          current.error = error.message;
        }
        return current;
      });
      broadcast({ type: 'run_status', runId, status: failed.status, state: failed });
    }
  });

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
    try {
      if (req.method === 'GET' && url.pathname === '/api/health') {
        return json(res, 200, {
          status: 'ready',
          service: 'slideharness-next-app-server',
          codex_ready: codex.available,
          api_key_required: false,
          shadow_policy: 'disabled_by_default',
          automatic_image_generation_ready: (images.ready ?? images.available) === true,
          image_generation_provider: images.provider || null,
          exact_plan_cache_ready: cachedPlans.available === true,
        });
      }
      if (req.method === 'GET' && url.pathname === '/api/events') {
        res.writeHead(200, {
          'content-type': 'text/event-stream',
          'cache-control': 'no-cache',
          connection: 'keep-alive',
        });
        res.write(': connected\n\n');
        clients.add(res);
        req.on('close', () => clients.delete(res));
        return;
      }
      if (req.method === 'POST' && url.pathname === '/api/codex/connect') {
        await codex.start();
        const [account, models, capabilities] = await Promise.all([
          codex.accountRead(),
          codex.modelList(),
          typeof codex.modelProviderCapabilitiesRead === 'function'
            ? codex.modelProviderCapabilitiesRead()
            : Promise.resolve(null),
        ]);
        if (typeof images.applyProviderCapabilities === 'function') {
          images.applyProviderCapabilities(capabilities);
        }
        let imageGenerationError = null;
        if (typeof images.ensureAvailable === 'function') {
          try {
            await images.ensureAvailable();
          } catch (error) {
            imageGenerationError = error.message;
          }
        }
        return json(res, 200, {
          status: 'ready',
          account,
          models,
          capabilities,
          image_generation_ready: (images.ready ?? images.available) === true,
          image_generation_error: imageGenerationError,
          api_key_required: false,
        });
      }
      if (req.method === 'GET' && url.pathname === '/api/runs') {
        return json(res, 200, { runs: await store.listRuns() });
      }
      if (req.method === 'POST' && url.pathname === '/api/runs') {
        const body = await readJson(req);
        return json(res, 201, await store.createRun({
          name: body.name,
          instructions: body.instructions,
          compositionMode: body.compositionMode,
          informationDensity: validateLevel(body.informationDensity),
          decorativeness: validateLevel(body.decorativeness),
          structuredVisualMode: validateStructuredVisualMode(body.structuredVisualMode),
          allowShadows: body.allowShadows === true,
        }));
      }
      const uploadMatch = url.pathname.match(/^\/api\/runs\/(run-[a-f0-9-]{36})\/files\/(template|source|design-guide)$/);
      if (req.method === 'PUT' && uploadMatch) {
        const [, runId, role] = uploadMatch;
        const filename = url.searchParams.get('filename') || req.headers['x-filename'];
        const buffer = await readBuffer(req, ROLE_RULES[role].maxBytes);
        const result = await store.writeUpload(runId, role, filename, buffer);
        return json(res, 201, result.state);
      }
      const assetMatch = url.pathname.match(/^\/api\/runs\/(run-[a-f0-9-]{36})\/assets\/([^/]+)$/);
      if (req.method === 'PUT' && assetMatch) {
        const [, runId, encodedAssetId] = assetMatch;
        const filename = url.searchParams.get('filename') || req.headers['x-filename'];
        const buffer = await readBuffer(req, ROLE_RULES.asset.maxBytes);
        const result = await store.writeUpload(runId, 'asset', filename, buffer, { assetId: decodeURIComponent(encodedAssetId) });
        const uploadedState = result.state;
        const rebuilt = uploadedState.status === 'regeneration_awaiting_images' && uploadedState.active_regeneration
          ? await applyRegeneration({ runId, kind: 'regenerate', request: uploadedState.active_regeneration })
          : await buildWithAutomaticImages(runId, { cachePlan: true });
        broadcast({ type: 'run_status', runId, status: rebuilt.status, state: rebuilt });
        return json(res, 201, rebuilt);
      }
      const slidesMatch = url.pathname.match(/^\/api\/runs\/(run-[a-f0-9-]{36})\/slides$/);
      if (req.method === 'GET' && slidesMatch) {
        const runId = slidesMatch[1];
        const state = await store.readState(runId);
        const plan = await readJsonFile(store.safePath(runId, 'plan/deck_spec.json'));
        return json(res, 200, {
          run_id: runId,
          revision: Number(state.revision || 1),
          slides: (plan.slides || []).map((slide, index) => ({
            slide_number: index + 1,
            slide_id: slide.slide_id,
            title: slide.title,
            message: slide.message,
            recipe: slide.recipe,
            policy: {
              information_density: state.information_density || 'medium',
              decorativeness: state.decorativeness || 'medium',
              structured_visual_mode: state.structured_visual_mode || 'native',
              ...(plan.metadata?.slide_policies?.[slide.slide_id] || {}),
            },
          })),
        });
      }
      const regenerateMatch = url.pathname.match(/^\/api\/runs\/(run-[a-f0-9-]{36})\/regenerate$/);
      if (req.method === 'POST' && regenerateMatch) {
        const runId = regenerateMatch[1];
        const body = await readJson(req);
        let state = await store.readState(runId);
        if (state.status !== 'completed' || !state.artifact) throw new Error('a completed deck is required before page regeneration');
        if (state.active_regeneration) throw new Error('another page regeneration is already active');
        const plan = await readJsonFile(store.safePath(runId, 'plan/deck_spec.json'));
        const target = (plan.slides || []).find((slide) => slide.slide_id === body.slideId);
        if (!target) throw new Error('target slide id was not found');
        const currentRevision = Number(state.revision || 1);
        const expectedRevision = Number(body.expectedRevision ?? currentRevision);
        if (expectedRevision !== currentRevision) throw new Error(`revision conflict: expected ${expectedRevision}, current ${currentRevision}`);
        const request = {
          schema_version: '0.4.0',
          request_id: `regen-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`,
          expected_revision: expectedRevision,
          slide_id: target.slide_id,
          current_slide: target,
          feedback: String(body.feedback || '').slice(0, 12000),
          information_density: validateLevel(body.informationDensity, state.information_density || 'medium'),
          decorativeness: validateLevel(body.decorativeness, state.decorativeness || 'medium'),
          structured_visual_mode: validateStructuredVisualMode(body.structuredVisualMode, state.structured_visual_mode || 'native'),
          design_guide_path: state.files?.design_guide ? 'prepared/design-guide/source_units.json' : null,
        };
        await writeJsonAtomic(store.safePath(runId, 'regeneration/request.json'), request);
        await writeRegenerationContext(store, runId, request);
        try { await fs.unlink(store.safePath(runId, 'regeneration/proposed_slide.json')); } catch {}
        await codex.start();
        let threadId = state.codex.thread_id;
        if (threadId) {
          try { await codex.resumeThread({ threadId }); } catch { threadId = null; }
        }
        if (!threadId) {
          const started = await codex.startThread({ cwd: store.runDir(runId), model: body.model || 'gpt-5.6-sol', serviceName: 'slideharness_next_local' });
          threadId = started.thread.id;
        }
        const turn = await codex.startTurn({
          threadId,
          cwd: store.runDir(runId),
          text: regenerationPrompt(request),
          skillPath: PLANNER_SKILL,
          skillName: 'slideharness-next-planner',
          model: body.model || 'gpt-5.6-sol',
          effort: body.effort || 'high',
        });
        const turnId = turn.turn.id;
        activeTurns.set(turnId, { runId, kind: 'regenerate', request, model: body.model || 'gpt-5.6-sol', startedAt: Date.now() });
        state = await store.updateState(runId, (current) => {
          current.status = 'regenerating';
          current.stage = 'codex_regeneration';
          current.codex = { thread_id: threadId, turn_id: turnId, model: body.model || 'gpt-5.6-sol' };
          current.active_regeneration = request;
          current.error = null;
          current.pending_approval = null;
          return current;
        });
        return json(res, 202, state);
      }
      const runMatch = url.pathname.match(/^\/api\/runs\/(run-[a-f0-9-]{36})(?:\/(prepare|plan|build))?$/);
      if (runMatch) {
        const [, runId, action] = runMatch;
        if (req.method === 'GET' && !action) return json(res, 200, await store.readState(runId));
        if (req.method === 'POST' && action === 'prepare') {
          const prepared = await core.prepare(runId);
          await writePlanningTask(store, runId, prepared);
          broadcast({ type: 'run_status', runId, status: prepared.status, state: prepared });
          return json(res, 200, prepared);
        }
        if (req.method === 'POST' && action === 'plan') {
          const body = await readJson(req);
          let state = await store.readState(runId);
          if (!['prepared', 'failed', 'planning'].includes(state.status)) throw new Error('run must be prepared before Codex planning');
          const planCacheKey = cachedPlans.available && body.useCache !== false
            ? await cachedPlans.keyForRun(store, runId, PLANNER_SKILL)
            : null;
          if (planCacheKey) {
            const cached = await cachedPlans.load(planCacheKey);
            if (cached) {
              await writeJsonAtomic(store.safePath(runId, 'plan/deck_spec.json'), cached.plan);
              await store.appendUsage(runId, {
                kind: 'cache',
                stage: 'codex_planning',
                provider: 'exact-plan-cache',
                duration_ms: 0,
                cache_hit: true,
                reason: `qa-pass plan ${planCacheKey}`,
              });
              await store.updateState(runId, (current) => {
                current.status = 'plan_ready';
                current.stage = 'compose_and_qa';
                current.plan_cache = { key: planCacheKey, hit: true, qa_status: cached.qa_status };
                current.error = null;
                return current;
              });
              const built = await buildWithAutomaticImages(runId);
              if (built.status !== 'failed') {
                broadcast({ type: 'run_status', runId, status: built.status, state: built });
                return json(res, 200, built);
              }
              await cachedPlans.invalidate(planCacheKey);
              state = await store.updateState(runId, (current) => {
                current.status = 'prepared';
                current.stage = 'codex_planning';
                current.plan_cache = { key: planCacheKey, hit: true, invalidated: true };
                current.error = null;
                return current;
              });
            }
          }
          await codex.start();
          let threadId = state.codex.thread_id;
          if (threadId) {
            try { await codex.resumeThread({ threadId }); } catch { threadId = null; }
          }
          if (!threadId) {
            const started = await codex.startThread({ cwd: store.runDir(runId), model: body.model || 'gpt-5.6-sol', serviceName: 'slideharness_next_local' });
            threadId = started.thread.id;
          }
          const turn = await codex.startTurn({
            threadId,
            cwd: store.runDir(runId),
            text: planningPrompt(state),
            skillPath: PLANNER_SKILL,
            skillName: 'slideharness-next-planner',
            model: body.model || 'gpt-5.6-sol',
            effort: body.effort || 'high',
          });
          const turnId = turn.turn.id;
          activeTurns.set(turnId, { runId, kind: 'plan', model: body.model || 'gpt-5.6-sol', startedAt: Date.now(), planCacheKey });
          state = await store.updateState(runId, (current) => {
            current.status = 'planning';
            current.stage = 'codex_planning';
            current.codex = { thread_id: threadId, turn_id: turnId, model: body.model || 'gpt-5.6-sol' };
            current.error = null;
            current.pending_approval = null;
            return current;
          });
          return json(res, 202, state);
        }
        if (req.method === 'POST' && action === 'build') {
          const built = await buildWithAutomaticImages(runId, { cachePlan: true });
          broadcast({ type: 'run_status', runId, status: built.status, state: built });
          return json(res, built.status === 'failed' ? 422 : 200, built);
        }
      }
      const fileMatch = url.pathname.match(/^\/api\/runs\/(run-[a-f0-9-]{36})\/file$/);
      if (req.method === 'GET' && fileMatch) {
        const relative = url.searchParams.get('path') || '';
        if (!relative.startsWith('output/')) throw new Error('only output artifacts are downloadable');
        const target = store.safePath(fileMatch[1], relative);
        const data = await fs.readFile(target);
        res.writeHead(200, {
          'content-type': contentType(target),
          'content-length': data.length,
          'content-disposition': path.extname(target).toLowerCase() === '.pptx' ? `attachment; filename="${path.basename(target)}"` : 'inline',
          'cache-control': 'no-store',
        });
        return res.end(data);
      }
      const approvalMatch = url.pathname.match(/^\/api\/approvals\/(\d+)$/);
      if (req.method === 'POST' && approvalMatch) {
        const requestId = approvalMatch[1];
        if (!pendingApprovals.has(requestId)) throw new Error('approval request is no longer pending');
        const body = await readJson(req);
        const decision = body.decision === 'accept' ? 'accept' : 'decline';
        codex.respondToServerRequest(requestId, { decision });
        const pending = pendingApprovals.get(requestId);
        if (pending?.runId) {
          await store.updateState(pending.runId, (current) => {
            current.pending_approval = null;
            return current;
          });
        }
        pendingApprovals.delete(requestId);
        return json(res, 200, { status: 'submitted', decision });
      }
      if (url.pathname.startsWith('/api/')) return json(res, 404, { error: 'not found' });
      return serveStatic(res, url.pathname);
    } catch (error) {
      json(res, /not found|ENOENT/.test(error.message) ? 404 : 400, { error: error.message });
    }
  });

  return { server, store, core, codex, images, broadcast };
}

export async function checkEnvironment() {
  const store = new NextgenRunStore(process.env.NEXTGEN_WORKSPACE || DEFAULT_WORKSPACE);
  await store.init();
  const core = new NextgenPythonCore({ nextgenRoot: here, store });
  const python = await core.check();
  const codexBin = resolveCodexBin();
  return {
    status: python.python_ok && python.ocr_ready ? 'ready' : 'failed',
    python,
    ocr_ready: python.ocr_ready,
    codex_bin: codexBin,
    codex_bin_present: path.isAbsolute(codexBin) ? fssync.existsSync(codexBin) : null,
    bind: '127.0.0.1',
    port: Number(process.env.NEXTGEN_PORT || 4318),
    api_key_required: false,
  };
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (isMain) {
  if (process.argv.includes('--check')) {
    const result = await checkEnvironment();
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    process.exitCode = result.status === 'ready' ? 0 : 1;
  } else {
    const { server } = await createNextgenServer();
    const port = Number(process.env.NEXTGEN_PORT || 4318);
    server.listen(port, '127.0.0.1', () => {
      process.stdout.write(`SlideHarness Next App Server: http://127.0.0.1:${port}\n`);
    });
  }
}
