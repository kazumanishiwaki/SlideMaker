import fs from 'node:fs/promises';
import fssync from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
  }
  return value;
}

function cacheKey(request, provider) {
  const payload = {
    provider,
    prompt: request.prompt || '',
    purpose: request.purpose || '',
    visual_kind: request.visual_kind || '',
    aspect_ratio: request.aspect_ratio || '16:9',
    required_text: request.required_text || [],
  };
  return createHash('sha256').update(JSON.stringify(stableValue(payload))).digest('hex');
}

function imageFormat(buffer) {
  if (buffer.length >= 24 && buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    return { extension: '.png', width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
  }
  if (buffer.length >= 12 && buffer.subarray(0, 3).equals(Buffer.from([255, 216, 255]))) {
    return { extension: '.jpg', width: null, height: null };
  }
  if (buffer.length >= 12 && buffer.subarray(0, 4).toString('ascii') === 'RIFF' && buffer.subarray(8, 12).toString('ascii') === 'WEBP') {
    return { extension: '.webp', width: null, height: null };
  }
  throw new Error('image generator returned an unsupported or corrupt image');
}

function validateGeneratedImage(buffer) {
  if (!Buffer.isBuffer(buffer) || buffer.length < 1024) throw new Error('image generator returned an empty or undersized image');
  const format = imageFormat(buffer);
  if (format.width !== null && (format.width < 512 || format.height < 288)) {
    throw new Error(`generated image is too small: ${format.width}x${format.height}`);
  }
  return format;
}

function defaultCacheDir() {
  return path.resolve(
    process.env.NEXTGEN_CACHE || path.join(os.homedir(), '.cache', 'slideharness-next'),
    'images',
  );
}

function defaultImagegenSkillPath() {
  const codexHome = process.env.CODEX_HOME || path.join(os.homedir(), '.codex');
  return path.join(codexHome, 'skills', '.system', 'imagegen', 'SKILL.md');
}

function imageGenerationPrompt(request) {
  const useCase = ['chart', 'flow', 'diagram'].includes(String(request.visual_kind || '').toLowerCase())
    ? 'infographic-diagram'
    : 'productivity-visual';
  const requiredText = Array.isArray(request.required_text) && request.required_text.length
    ? request.required_text.map((value) => JSON.stringify(String(value))).join(', ')
    : 'なし';
  const textConstraint = requiredText === 'なし'
    ? '文字は一切入れない。ロゴ、透かし、疑似文字、判読不能な記号列も入れない。'
    : `次の文字列だけを読みやすく正確に1回ずつ表示する: ${requiredText}。それ以外の文字を追加しない。`;
  return [
    'built-in image_gen を使い、新規のスライド用画像を1点だけ生成してください。API/CLIやシェルは使わないでください。',
    `Use case: ${useCase}`,
    `Asset type: PowerPointスライド内の説明用ビジュアル（${request.purpose || '視覚的な要点説明'}）`,
    `Primary request: ${request.prompt || ''}`,
    `Subject: ${request.visual_kind || '資料の主張を支えるeditorial visual'}`,
    'Style/medium: プレゼンテーション用途の洗練されたeditorial visual。素材感と奥行きは明瞭だが、装飾過多にしない。',
    `Composition/framing: ${request.aspect_ratio || '16:9'}の横長構図。主役を一つに絞り、視線の流れを明確にし、全周8%を安全余白として重要要素を置かない。スライドでトリミング可能な構図にする。`,
    'Lighting/mood: 明瞭で落ち着いたビジネス向け。白飛び、黒つぶれ、過度なグロー、不要な被写界深度を避ける。',
    `Text (verbatim): ${requiredText}`,
    `Constraints: ${textConstraint} スライド本文にない数値、因果関係、ブランド要素を追加しない。輪郭、手、接続、遠近、反復パターンに破綻を残さない。`,
    'Avoid: generic stock-photo look, clip art, decorative clutter, excessive gradients, illegible micro-details, logos, trademarks, watermarks.',
    '生成物はホストがApp ServerのimageGeneration.savedPathから直ちに取り込むため、生成後のコピー、移動、ファイル編集は行わないでください。',
    '生成が完了したら、採用した1点について短く報告して終了してください。',
  ].join('\n');
}

const QUALITY_REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    quality_pass: { type: 'boolean' },
    scores: {
      type: 'object',
      additionalProperties: false,
      properties: {
        prompt_alignment: { type: 'integer', minimum: 1, maximum: 5 },
        composition: { type: 'integer', minimum: 1, maximum: 5 },
        visual_coherence: { type: 'integer', minimum: 1, maximum: 5 },
        slide_usability: { type: 'integer', minimum: 1, maximum: 5 },
        artifact_freedom: { type: 'integer', minimum: 1, maximum: 5 },
      },
      required: ['prompt_alignment', 'composition', 'visual_coherence', 'slide_usability', 'artifact_freedom'],
    },
    blocking_issues: { type: 'array', items: { type: 'string' }, maxItems: 8 },
    improvement_instruction: { type: 'string' },
    review_notes: { type: 'array', items: { type: 'string' }, maxItems: 8 },
  },
  required: ['quality_pass', 'scores', 'blocking_issues', 'improvement_instruction', 'review_notes'],
};

function imageQualityReviewPrompt(request) {
  const exactText = (request.required_text || []).map((value) => JSON.stringify(String(value))).join(', ') || 'なし';
  return [
    '添付画像を、PowerPoint資料へそのまま採用できる最終画像として厳格に審査してください。',
    `元の要求: ${request.prompt || ''}`,
    `用途: ${request.purpose || 'PowerPointスライドの説明用ビジュアル'}`,
    `想定構図: ${request.aspect_ratio || '16:9'}`,
    `必須文字列: ${exactText}`,
    '各項目を1から5で採点し、4未満が一つでもあればquality_passをfalseにしてください。',
    '被写体や構造の破綻、不要な文字・ロゴ・透かし、判読不能な疑似文字、主題不一致、視線誘導の弱さ、過密、重要要素の端切れはblocking_issuesに記録してください。',
    'required_textがない場合、意味のある文字、疑似文字、ロゴが見えれば不合格です。',
    'required_textがある場合、その文字が正確かつ読みやすく、余計な文字がないことを確認してください。',
    '再生成で直すべき点はimprovement_instructionに一つの具体的な指示としてまとめてください。',
    '出力スキーマに従うJSONだけを返してください。',
  ].join('\n');
}

function parseJsonMessage(text) {
  const cleaned = String(text || '').trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  return JSON.parse(cleaned);
}

function normalizedUsage(event) {
  const usage = event?.turn?.usage || event?.usage || {};
  const input = Number(usage.input_tokens ?? usage.inputTokens);
  const output = Number(usage.output_tokens ?? usage.outputTokens);
  return {
    inputTokens: Number.isFinite(input) ? input : 0,
    outputTokens: Number.isFinite(output) ? output : 0,
  };
}

function imageSha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex');
}

async function readImageGenerationResult(item) {
  if (item?.failure) {
    const detail = item.failure.type === 'usageLimitExceeded'
      ? `usage limit exceeded (${item.failure.limitId || 'unknown limit'})`
      : JSON.stringify(item.failure);
    throw new Error(`Codex image generation failed: ${detail}`);
  }
  if (!item?.savedPath) throw new Error('Codex image generation completed without savedPath');
  let buffer;
  try {
    buffer = await fs.readFile(path.resolve(item.savedPath));
  } catch (error) {
    throw new Error(`Codex image generation output is unreadable: ${error.message}`);
  }
  return { buffer, format: validateGeneratedImage(buffer) };
}

export class NullImageGenerator {
  constructor() {
    this.available = false;
    this.provider = 'unconfigured';
  }

  async generate() {
    throw new Error('automatic image generation is not configured');
  }
}

export class CodexAppServerImageGenerator {
  constructor({
    client,
    cacheDir,
    skillPath = defaultImagegenSkillPath(),
    model = process.env.NEXTGEN_CODEX_MODEL || 'gpt-5.6-sol',
    effort = process.env.NEXTGEN_IMAGE_EFFORT || 'low',
    reviewEffort = process.env.NEXTGEN_IMAGE_REVIEW_EFFORT || 'low',
    maxAttempts = Number(process.env.NEXTGEN_IMAGE_MAX_ATTEMPTS || 2),
    timeoutMs = 360000,
  } = {}) {
    this.client = client || null;
    this.provider = 'signed-in-codex-app-server-imagegen';
    this.cacheDir = cacheDir ? path.resolve(cacheDir) : defaultCacheDir();
    this.skillPath = path.resolve(skillPath);
    this.model = model;
    this.effort = effort;
    this.reviewEffort = reviewEffort;
    this.maxAttempts = Math.max(1, Math.min(3, Number.isFinite(maxAttempts) ? maxAttempts : 2));
    this.timeoutMs = timeoutMs;
    this.capability = null;
  }

  get available() {
    return Boolean(this.client) && this.capability !== false;
  }

  get ready() {
    return Boolean(this.client?.available && this.capability === true);
  }

  applyProviderCapabilities(capabilities) {
    if (capabilities && typeof capabilities.imageGeneration === 'boolean') {
      this.capability = capabilities.imageGeneration;
    }
    return this.capability;
  }

  async ensureAvailable() {
    if (!this.client) throw new Error('Codex App Server image generation client is unavailable');
    await this.client.ensureStarted();
    if (this.capability === null) {
      const capabilities = await this.client.modelProviderCapabilitiesRead();
      this.capability = capabilities?.imageGeneration === true;
    }
    if (!this.capability) throw new Error('signed-in Codex App Server does not advertise image generation capability');
    if (!fssync.existsSync(this.skillPath)) throw new Error(`imagegen skill is unavailable: ${this.skillPath}`);
    return true;
  }

  async #generateThroughCodex({ request, runDir }) {
    await this.ensureAvailable();
    const cwd = path.resolve(runDir);
    const started = await this.client.startThread({
      cwd,
      model: this.model,
      serviceName: 'slideharness_next_image_generation',
    });
    const threadId = started?.thread?.id;
    if (!threadId) throw new Error('Codex image generation thread did not return an id');

    const imageItems = [];
    let expectedTurnId = null;
    let cleanup = () => {};
    const completed = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error('Codex image generation turn timed out'));
      }, this.timeoutMs);
      const onItem = (event) => {
        if (event?.threadId !== threadId || event?.item?.type !== 'imageGeneration') return;
        if (expectedTurnId && event.turnId !== expectedTurnId) return;
        imageItems.push(event.item);
      };
      const onTurn = (event) => {
        const eventTurnId = event?.turn?.id || event?.turnId;
        if (event?.threadId !== threadId) return;
        if (expectedTurnId && eventTurnId !== expectedTurnId) return;
        cleanup();
        resolve(event);
      };
      cleanup = () => {
        clearTimeout(timer);
        this.client.off('item_completed', onItem);
        this.client.off('turn_completed', onTurn);
      };
      this.client.on('item_completed', onItem);
      this.client.on('turn_completed', onTurn);
    });

    let turn;
    let completion;
    try {
      turn = await this.client.startTurn({
        threadId,
        cwd,
        text: imageGenerationPrompt(request),
        skillPath: this.skillPath,
        skillName: 'imagegen',
        model: this.model,
        effort: this.effort,
        approvalPolicy: 'never',
      });
      expectedTurnId = turn?.turn?.id;
      if (!expectedTurnId) throw new Error('Codex image generation turn did not return an id');
      completion = await completed;
      const status = completion?.turn?.status || 'completed';
      if (status !== 'completed') throw new Error(`Codex image generation turn ended with status ${status}`);
    } finally {
      cleanup();
      if (!turn?.turn?.id) completed.catch(() => {});
    }

    const item = [...imageItems].reverse().find((candidate) => candidate.savedPath && !candidate.failure)
      || imageItems.at(-1);
    if (!item) throw new Error('Codex image generation turn completed without an imageGeneration item');
    return { item, usage: normalizedUsage(completion), ...(await readImageGenerationResult(item)) };
  }

  async #reviewThroughCodex({ request, imagePath, runDir }) {
    const cwd = path.resolve(runDir);
    const started = await this.client.startThread({
      cwd,
      model: this.model,
      serviceName: 'slideharness_next_image_quality_review',
    });
    const threadId = started?.thread?.id;
    if (!threadId) throw new Error('Codex image quality review thread did not return an id');

    const messages = [];
    let expectedTurnId = null;
    let cleanup = () => {};
    const completed = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error('Codex image quality review timed out'));
      }, this.timeoutMs);
      const onItem = (event) => {
        if (event?.threadId !== threadId || event?.item?.type !== 'agentMessage') return;
        if (expectedTurnId && event.turnId !== expectedTurnId) return;
        messages.push(event.item.text || '');
      };
      const onTurn = (event) => {
        const eventTurnId = event?.turn?.id || event?.turnId;
        if (event?.threadId !== threadId) return;
        if (expectedTurnId && eventTurnId !== expectedTurnId) return;
        cleanup();
        resolve(event);
      };
      cleanup = () => {
        clearTimeout(timer);
        this.client.off('item_completed', onItem);
        this.client.off('turn_completed', onTurn);
      };
      this.client.on('item_completed', onItem);
      this.client.on('turn_completed', onTurn);
    });

    let turn;
    let completion;
    try {
      turn = await this.client.startTurn({
        threadId,
        cwd,
        text: imageQualityReviewPrompt(request),
        model: this.model,
        effort: this.reviewEffort,
        approvalPolicy: 'never',
        additionalInput: [{ type: 'localImage', path: path.resolve(imagePath), detail: 'high' }],
        outputSchema: QUALITY_REVIEW_SCHEMA,
        sandboxPolicy: { type: 'readOnly', networkAccess: false },
      });
      expectedTurnId = turn?.turn?.id;
      if (!expectedTurnId) throw new Error('Codex image quality review turn did not return an id');
      completion = await completed;
      const status = completion?.turn?.status || 'completed';
      if (status !== 'completed') throw new Error(`Codex image quality review ended with status ${status}`);
    } finally {
      cleanup();
      if (!turn?.turn?.id) completed.catch(() => {});
    }

    if (!messages.length) throw new Error('Codex image quality review completed without a JSON result');
    const review = parseJsonMessage(messages.at(-1));
    const scoreKeys = ['prompt_alignment', 'composition', 'visual_coherence', 'slide_usability', 'artifact_freedom'];
    const scores = review?.scores || {};
    const scoreValues = scoreKeys.map((key) => Number(scores[key]));
    if (scoreValues.some((value) => !Number.isInteger(value) || value < 1 || value > 5)) {
      throw new Error('Codex image quality review returned invalid scores');
    }
    const blockingIssues = Array.isArray(review.blocking_issues)
      ? review.blocking_issues.map(String).filter(Boolean)
      : [];
    const computedPass = review.quality_pass === true
      && blockingIssues.length === 0
      && scoreValues.every((value) => value >= 4);
    return {
      ...review,
      blocking_issues: blockingIssues,
      computed_pass: computedPass,
      minimum_score: Math.min(...scoreValues),
      usage: normalizedUsage(completion),
    };
  }

  async generate({ request, runDir }) {
    await fs.mkdir(this.cacheDir, { recursive: true });
    const key = cacheKey(request, this.provider);
    const metadataPath = path.join(this.cacheDir, `${key}.json`);
    let cacheMetadata = null;
    try {
      cacheMetadata = JSON.parse(await fs.readFile(metadataPath, 'utf8'));
    } catch {}
    for (const extension of ['.png', '.jpg', '.webp']) {
      const cached = path.join(this.cacheDir, `${key}${extension}`);
      if (!fssync.existsSync(cached)) continue;
      const buffer = await fs.readFile(cached);
      validateGeneratedImage(buffer);
      if (cacheMetadata?.status !== 'PASS' || cacheMetadata.image_sha256 !== imageSha256(buffer)) continue;
      return {
        buffer,
        filename: `${request.asset_id}${extension}`,
        provider: this.provider,
        model: this.model,
        cacheHit: true,
        cacheKey: key,
        attempts: cacheMetadata.attempts || 1,
        qualityReview: cacheMetadata.quality_review,
        inputTokens: 0,
        outputTokens: 0,
      };
    }

    let attemptRequest = structuredClone(request);
    let accepted = null;
    let totalInputTokens = 0;
    let totalOutputTokens = 0;
    const rejectedReviews = [];
    for (let attempt = 1; attempt <= this.maxAttempts; attempt += 1) {
      const generated = await this.#generateThroughCodex({ request: attemptRequest, runDir });
      totalInputTokens += generated.usage.inputTokens;
      totalOutputTokens += generated.usage.outputTokens;
      const review = await this.#reviewThroughCodex({
        request,
        imagePath: generated.item.savedPath,
        runDir,
      });
      totalInputTokens += review.usage.inputTokens;
      totalOutputTokens += review.usage.outputTokens;
      if (review.computed_pass) {
        accepted = { ...generated, review, attempt };
        break;
      }
      rejectedReviews.push({
        attempt,
        scores: review.scores,
        blocking_issues: review.blocking_issues,
        improvement_instruction: review.improvement_instruction,
      });
      attemptRequest = {
        ...request,
        prompt: [
          request.prompt || '',
          `Targeted correction for the next variant: ${review.improvement_instruction || review.blocking_issues.join('; ')}`,
          'Keep every original requirement unchanged and correct only the quality problems above.',
        ].join('\n'),
      };
    }
    if (!accepted) {
      const issues = rejectedReviews.at(-1)?.blocking_issues || [];
      throw new Error(`Codex image quality review rejected ${this.maxAttempts} attempt(s): ${issues.join('; ') || 'minimum quality score was not met'}`);
    }

    const cached = path.join(this.cacheDir, `${key}${accepted.format.extension}`);
    await fs.writeFile(cached, accepted.buffer);
    const qualityReview = {
      status: 'PASS',
      attempt: accepted.attempt,
      scores: accepted.review.scores,
      minimum_score: accepted.review.minimum_score,
      blocking_issues: accepted.review.blocking_issues,
      review_notes: accepted.review.review_notes,
      rejected_attempts: rejectedReviews,
    };
    await fs.writeFile(metadataPath, `${JSON.stringify({
      schema_version: '0.4.0',
      status: 'PASS',
      provider: this.provider,
      model: this.model,
      image_sha256: imageSha256(accepted.buffer),
      attempts: accepted.attempt,
      quality_review: qualityReview,
      created_at: new Date().toISOString(),
    }, null, 2)}\n`, 'utf8');
    return {
      buffer: accepted.buffer,
      filename: `${request.asset_id}${accepted.format.extension}`,
      provider: this.provider,
      model: this.model,
      cacheHit: false,
      cacheKey: key,
      attempts: accepted.attempt,
      qualityReview,
      inputTokens: totalInputTokens,
      outputTokens: totalOutputTokens,
      revisedPrompt: accepted.item.revisedPrompt || null,
    };
  }
}

export function createCodexAppServerImageGenerator(client) {
  if (!client) return new NullImageGenerator();
  return new CodexAppServerImageGenerator({ client });
}

export { QUALITY_REVIEW_SCHEMA, cacheKey, imageGenerationPrompt, imageQualityReviewPrompt, validateGeneratedImage };
