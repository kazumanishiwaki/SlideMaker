import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { CodexAppServerImageGenerator } from '../app/image-generator.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.resolve(here, '../examples/representative/assets/generated-template-system.png');

class FakeCodexImageClient extends EventEmitter {
  constructor({ reviews = null } = {}) {
    super();
    this.available = false;
    this.turns = [];
    this.threadCounter = 0;
    this.reviews = reviews || [{
      quality_pass: true,
      scores: { prompt_alignment: 5, composition: 4, visual_coherence: 5, slide_usability: 4, artifact_freedom: 5 },
      blocking_issues: [],
      improvement_instruction: '',
      review_notes: ['presentation-ready'],
    }];
    this.reviewCounter = 0;
  }

  async ensureStarted() { this.available = true; }
  async modelProviderCapabilitiesRead() {
    return { imageGeneration: true, namespaceTools: true, webSearch: false };
  }
  async startThread() {
    this.threadCounter += 1;
    return { thread: { id: `thr_image_fake_${this.threadCounter}` } };
  }
  async startTurn(options) {
    this.turns.push(options);
    const turnId = `turn_image_fake_${this.turns.length}`;
    const isReview = options.additionalInput?.some((item) => item.type === 'localImage');
    const review = isReview
      ? this.reviews[Math.min(this.reviewCounter++, this.reviews.length - 1)]
      : null;
    setTimeout(() => this.emit('item_completed', isReview ? {
      threadId: options.threadId,
      turnId,
      item: {
        id: 'review_fake',
        type: 'agentMessage',
        text: JSON.stringify(review),
      },
    } : {
      threadId: options.threadId,
      turnId,
      item: {
        id: 'image_fake',
        type: 'imageGeneration',
        status: 'completed',
        result: 'generated',
        savedPath: FIXTURE,
        revisedPrompt: 'Editorial visual, no text',
      },
    }), 5);
    setTimeout(() => this.emit('turn_completed', {
      threadId: options.threadId,
      turn: { id: turnId, status: 'completed', usage: { inputTokens: 10, outputTokens: 5 } },
    }), 10);
    return { turn: { id: turnId, status: 'inProgress' } };
  }
}


test('Codex App Server image generator consumes native imageGeneration savedPath and caches it', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'slideharness-image-codex-'));
  try {
    const client = new FakeCodexImageClient();
    const generator = new CodexAppServerImageGenerator({
      client,
      cacheDir: path.join(root, 'cache'),
      skillPath: path.resolve(here, '../skill/SKILL.md'),
    });
    const request = {
      asset_id: 'S002-visual',
      purpose: 'slide hero',
      visual_kind: 'editorial',
      prompt: 'A modular presentation system',
      aspect_ratio: '16:9',
      required_text: [],
    };
    const first = await generator.generate({ request, runDir: root });
    const second = await generator.generate({ request, runDir: root });
    assert.equal(first.cacheHit, false);
    assert.equal(second.cacheHit, true);
    assert.equal(first.provider, 'signed-in-codex-app-server-imagegen');
    assert.equal(client.turns.length, 2);
    assert.equal(client.turns[0].skillName, 'imagegen');
    assert.equal(client.turns[0].approvalPolicy, 'never');
    assert.equal(client.turns[1].additionalInput[0].type, 'localImage');
    assert.ok(client.turns[1].outputSchema);
    assert.match(client.turns[0].text, /App ServerのimageGeneration\.savedPath/);
    assert.equal(first.qualityReview.status, 'PASS');
    assert.equal(first.qualityReview.minimum_score, 4);
    assert.equal(first.inputTokens, 20);
    assert.equal(first.outputTokens, 10);
    assert.equal(second.qualityReview.status, 'PASS');
    assert.ok(first.buffer.length > 100000);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});

test('Codex image quality gate retries one rejected variant before caching PASS', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'slideharness-image-retry-'));
  try {
    const client = new FakeCodexImageClient({ reviews: [
      {
        quality_pass: false,
        scores: { prompt_alignment: 4, composition: 3, visual_coherence: 4, slide_usability: 3, artifact_freedom: 5 },
        blocking_issues: ['weak hierarchy'],
        improvement_instruction: 'Create one clear focal point and more open margins.',
        review_notes: [],
      },
      {
        quality_pass: true,
        scores: { prompt_alignment: 5, composition: 5, visual_coherence: 4, slide_usability: 5, artifact_freedom: 5 },
        blocking_issues: [],
        improvement_instruction: '',
        review_notes: ['corrected'],
      },
    ] });
    const generator = new CodexAppServerImageGenerator({
      client,
      cacheDir: path.join(root, 'cache'),
      skillPath: path.resolve(here, '../skill/SKILL.md'),
      maxAttempts: 2,
    });
    const result = await generator.generate({
      request: { asset_id: 'S003-visual', prompt: 'One clear modular system', aspect_ratio: '16:9', required_text: [] },
      runDir: root,
    });
    assert.equal(result.attempts, 2);
    assert.equal(result.qualityReview.rejected_attempts.length, 1);
    assert.equal(client.turns.length, 4);
    assert.match(client.turns[2].text, /Targeted correction/);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
