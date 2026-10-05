import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { createNextgenServer } from '../app-server.mjs';
import { PlanCache } from '../app/plan-cache.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, '../..');
const TEMPLATE = path.join(ROOT, 'nextgen/examples/test-case/inputs/source.pptx');
const SOURCE = path.join(ROOT, 'nextgen/examples/source-pipeline/brief.md');
const PLAN = path.join(ROOT, 'nextgen/examples/source-pipeline/output/deck_spec.json');
const GENERATED_IMAGE = path.join(ROOT, 'nextgen/examples/representative/assets/generated-template-system.png');

class FakeCodexClient extends EventEmitter {
  constructor() {
    super();
    this.available = false;
    this.turnCounter = 0;
  }
  async start() { this.available = true; }
  async accountRead() { return { account: { type: 'chatgpt', planType: 'test' } }; }
  async modelList() { return { data: [{ model: 'gpt-5.6-sol' }] }; }
  async modelProviderCapabilitiesRead() { return { imageGeneration: true, namespaceTools: true, webSearch: false }; }
  async startThread() { return { thread: { id: 'thr_nextgen_fake' } }; }
  async resumeThread({ threadId }) { return { thread: { id: threadId } }; }
  async startTurn({ cwd, text }) {
    this.turnCounter += 1;
    const turnId = `turn_nextgen_fake_${this.turnCounter}`;
    if (text.includes('regeneration/proposed_slide.json')) {
      const request = JSON.parse(await fs.readFile(path.join(cwd, 'regeneration', 'request.json'), 'utf8'));
      const plan = JSON.parse(await fs.readFile(path.join(cwd, 'plan', 'deck_spec.json'), 'utf8'));
      const proposed = structuredClone(plan.slides.find((slide) => slide.slide_id === request.slide_id));
      if (request.structured_visual_mode === 'generated-image') {
        const sourceItems = proposed.content?.steps || proposed.content?.cards || proposed.content?.columns || [];
        const facts = sourceItems.map((item) => `${item.heading || item.title || ''}: ${item.body || item.text || ''}`).join('; ');
        proposed.recipe = 'generated_visual';
        proposed.content = {
          visual: {
            type: 'flow',
            asset_id: `${proposed.slide_id}-generated-flow`,
            purpose: 'Rich generated flow diagram',
            prompt: `Create a rich flow diagram. Preserve these exact labels: ${facts}`,
            required_text: ['Le'],
          },
        };
      } else if (Array.isArray(proposed.content?.columns)) {
        proposed.content.columns.reverse();
      }
      await fs.writeFile(path.join(cwd, 'regeneration', 'proposed_slide.json'), `${JSON.stringify(proposed, null, 2)}\n`);
    } else {
      await fs.copyFile(PLAN, path.join(cwd, 'plan', 'deck_spec.json'));
    }
    setTimeout(() => this.emit('turn_completed', { turn: { id: turnId, status: 'completed' } }), 20);
    return { turn: { id: turnId, status: 'inProgress' } };
  }
  respondToServerRequest() {}
}

class FakeImageGenerator {
  constructor() {
    this.available = true;
    this.provider = 'fake-image-generator';
    this.calls = [];
    this.failNext = false;
  }
  async generate({ request }) {
    this.calls.push(request);
    if (this.failNext) {
      this.failNext = false;
      throw new Error('simulated host image generation failure');
    }
    return {
      buffer: await fs.readFile(GENERATED_IMAGE),
      filename: `${request.asset_id}.png`,
      provider: this.provider,
      cacheHit: false,
      cacheKey: 'test-cache-key',
      attempts: 1,
      inputTokens: 12,
      outputTokens: 6,
      qualityReview: {
        status: 'PASS',
        attempt: 1,
        scores: { prompt_alignment: 5, composition: 4, visual_coherence: 5, slide_usability: 4, artifact_freedom: 5 },
        minimum_score: 4,
        blocking_issues: [],
        review_notes: ['test quality pass'],
        rejected_attempts: [],
      },
    };
  }
}

async function request(base, pathname, options = {}) {
  const response = await fetch(`${base}${pathname}`, options);
  const data = await response.json();
  assert.ok(response.ok, `${response.status}: ${JSON.stringify(data)}`);
  return data;
}

async function waitForRun(base, runId, timeoutMs = 90000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const run = await request(base, `/api/runs/${runId}`);
    if (['completed', 'failed', 'awaiting_images'].includes(run.status)) return run;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error('timed out waiting for App Server run');
}

async function waitForStatus(base, runId, expected, timeoutMs = 90000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const run = await request(base, `/api/runs/${runId}`);
    if (run.status === expected) return run;
    if (run.status === 'failed') throw new Error(JSON.stringify(run.error));
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`timed out waiting for ${expected}`);
}

async function waitForRegeneration(base, runId, requestId, timeoutMs = 90000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const run = await request(base, `/api/runs/${runId}`);
    if (run.last_regeneration?.request_id === requestId) return run;
    if (run.status === 'failed') throw new Error(JSON.stringify(run.error));
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error('timed out waiting for page regeneration');
}

async function waitForRegenerationState(base, runId, requestId, expectedStatus, timeoutMs = 90000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const run = await request(base, `/api/runs/${runId}`);
    if (run.status === expectedStatus) return run;
    if (run.last_regeneration?.request_id === requestId) return run;
    if (run.status === 'failed') throw new Error(JSON.stringify(run.error));
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`timed out waiting for ${expectedStatus}`);
}

test('Nextgen App Server uploads, delegates planning, builds, and exposes the PPTX', { timeout: 180000 }, async () => {
  const workspace = await fs.mkdtemp(path.join(os.tmpdir(), 'slideharness-next-app-'));
  const fakeCodex = new FakeCodexClient();
  const fakeImages = new FakeImageGenerator();
  const { server } = await createNextgenServer({
    workspace,
    codexClient: fakeCodex,
    imageGenerator: fakeImages,
    planCache: new PlanCache({ cacheDir: path.join(workspace, 'cache') }),
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const health = await request(base, '/api/health');
    assert.equal(health.api_key_required, false);
    assert.equal(health.shadow_policy, 'disabled_by_default');
    assert.equal(health.automatic_image_generation_ready, true);
    const run = await request(base, '/api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        name: 'app-server-test',
        compositionMode: 'auto',
        informationDensity: 'high',
        decorativeness: 'low',
        structuredVisualMode: 'native',
        allowShadows: false,
      }),
    });
    await request(base, `/api/runs/${run.run_id}/files/template?filename=source.pptx`, { method: 'PUT', body: await fs.readFile(TEMPLATE) });
    await request(base, `/api/runs/${run.run_id}/files/source?filename=brief.md`, { method: 'PUT', body: await fs.readFile(SOURCE) });
    await request(base, `/api/runs/${run.run_id}/files/design-guide?filename=design.md`, {
      method: 'PUT',
      body: Buffer.from('# Visual direction\nUse restrained editorial diagrams and no generic filler imagery.\n'),
    });
    const prepared = await request(base, `/api/runs/${run.run_id}/prepare`, { method: 'POST' });
    assert.equal(prepared.status, 'prepared');
    const connection = await request(base, '/api/codex/connect', { method: 'POST' });
    assert.equal(connection.capabilities.imageGeneration, true);
    assert.equal(connection.image_generation_ready, true);
    const planning = await request(base, `/api/runs/${run.run_id}/plan`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-5.6-sol', effort: 'high' }),
    });
    assert.equal(planning.status, 'planning');
    const completed = await waitForRun(base, run.run_id);
    assert.equal(completed.status, 'completed', JSON.stringify(completed.error));
    assert.equal(completed.summary.status, 'PASS');
    assert.equal(completed.summary.shadow_policy, 'disabled_by_default');
    assert.equal(completed.summary.information_density, 'high');
    assert.equal(completed.summary.decorativeness, 'low');
    assert.equal(completed.summary.structured_visual_mode, 'native');
    assert.equal(completed.summary.package_qa, 'PASS');
    assert.equal(completed.summary.provenance_qa, 'PASS');
    assert.equal(completed.summary.visual_qa, 'PASS');
    assert.equal(completed.summary.render_policy, 'required');
    assert.equal(completed.revision, 1);
    assert.equal((await fs.readdir(path.join(workspace, 'cache', 'plans'))).filter((name) => name.endsWith('.json')).length, 1);
    const slides = await request(base, `/api/runs/${run.run_id}/slides`);
    assert.equal(slides.slides.length, 8);
    const regenerating = await request(base, `/api/runs/${run.run_id}/regenerate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        slideId: 'S005',
        expectedRevision: 1,
        feedback: '生成フローをリッチな画像のフロー図にする',
        informationDensity: 'medium',
        decorativeness: 'high',
        structuredVisualMode: 'generated-image',
      }),
    });
    assert.equal(regenerating.status, 'regenerating');
    const regenerated = await waitForRegeneration(base, run.run_id, regenerating.active_regeneration.request_id);
    assert.equal(regenerated.status, 'completed', JSON.stringify(regenerated.error));
    assert.equal(regenerated.last_regeneration.status, 'PASS', JSON.stringify(regenerated, null, 2));
    assert.equal(regenerated.revision, 2);
    assert.equal(regenerated.last_regeneration.non_target_unchanged, true);
    assert.equal(fakeImages.calls.length, 1);
    assert.equal(fakeImages.calls[0].asset_id, 'S005-generated-flow');
    assert.equal(regenerated.generated_assets[0].quality_minimum_score, 4);
    const qualityReview = JSON.parse(await fs.readFile(path.join(workspace, run.run_id, regenerated.generated_assets[0].quality_review_path), 'utf8'));
    assert.equal(qualityReview.status, 'PASS');
    const isolation = JSON.parse(await fs.readFile(path.join(workspace, run.run_id, 'output', 'qa-page-isolation.json'), 'utf8'));
    const packageQa = JSON.parse(await fs.readFile(path.join(workspace, run.run_id, 'output', 'qa-package.json'), 'utf8'));
    const provenanceQa = JSON.parse(await fs.readFile(path.join(workspace, run.run_id, 'output', 'qa-provenance.json'), 'utf8'));
    const visualQa = JSON.parse(await fs.readFile(path.join(workspace, run.run_id, 'output', 'qa-visual.json'), 'utf8'));
    const generatedImageQa = JSON.parse(await fs.readFile(path.join(workspace, run.run_id, 'output', 'qa-generated-image.json'), 'utf8'));
    const usage = JSON.parse(await fs.readFile(path.join(workspace, run.run_id, 'usage.json'), 'utf8'));
    assert.equal(packageQa.status, 'PASS');
    assert.equal(provenanceQa.status, 'PASS');
    assert.equal(visualQa.status, 'PASS');
    assert.equal(generatedImageQa.status, 'PASS');
    assert.ok(usage.entries.some((entry) => entry.kind === 'generative-image'));
    assert.ok(usage.entries.some((entry) => entry.kind === 'generative-text'));
    assert.equal(isolation.non_target_unchanged, true);
    assert.equal(isolation.non_target_slide_count, 7);
    const regeneratedSlides = await request(base, `/api/runs/${run.run_id}/slides`);
    assert.equal(regeneratedSlides.slides.find((slide) => slide.slide_id === 'S005').recipe, 'generated_visual');
    fakeImages.failNext = true;
    const fallbackRequest = await request(base, `/api/runs/${run.run_id}/regenerate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        slideId: 'S006',
        expectedRevision: 2,
        feedback: '画像生成失敗時の手動フォールバックを確認する',
        informationDensity: 'medium',
        decorativeness: 'high',
        structuredVisualMode: 'generated-image',
      }),
    });
    const awaitingFallback = await waitForRegenerationState(base, run.run_id, fallbackRequest.active_regeneration.request_id, 'regeneration_awaiting_images');
    assert.equal(awaitingFallback.status, 'regeneration_awaiting_images', JSON.stringify(awaitingFallback, null, 2));
    assert.equal(awaitingFallback.active_regeneration.request_id, fallbackRequest.active_regeneration.request_id);
    assert.match(awaitingFallback.image_generation_error, /simulated host image generation failure/);
    const fallbackAsset = awaitingFallback.asset_requests.find((item) => item.status === 'awaiting_image');
    assert.equal(fallbackAsset.asset_id, 'S006-generated-flow');
    assert.equal(awaitingFallback.revision, 2);
    assert.ok(awaitingFallback.artifact, 'the last valid deck remains available during manual fallback');
    const artifact = await fetch(`${base}/api/runs/${run.run_id}/file?path=${encodeURIComponent(completed.artifact)}`);
    assert.equal(artifact.status, 200);
    assert.ok((await artifact.arrayBuffer()).byteLength > 100000);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    if (process.env.KEEP_NEXTGEN_TEST_WORKSPACE !== '1') await fs.rm(workspace, { recursive: true, force: true });
  }
});
