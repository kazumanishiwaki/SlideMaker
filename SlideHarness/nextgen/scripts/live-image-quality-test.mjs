#!/usr/bin/env node
import fs from 'node:fs/promises';
import fssync from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { CodexAppServerClient } from '../app/codex-app-server-client.mjs';
import { CodexAppServerImageGenerator } from '../app/image-generator.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const nextgenRoot = path.resolve(here, '..');
const outputDir = path.join(nextgenRoot, 'examples', 'image-quality-test');
const bundledCodex = '/Applications/ChatGPT.app/Contents/Resources/codex';
const codexBin = process.env.CODEX_BIN || (fssync.existsSync(bundledCodex) ? bundledCodex : 'codex');

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

await fs.mkdir(outputDir, { recursive: true });
const client = new CodexAppServerClient({ codexBin, cwd: nextgenRoot });
const generator = new CodexAppServerImageGenerator({
  client,
  cacheDir: path.join(nextgenRoot, 'cache', 'live-image-quality-test'),
  maxAttempts: Number(process.env.NEXTGEN_IMAGE_MAX_ATTEMPTS || 2),
});
const request = {
  asset_id: 'LIVE-QUALITY-TEST',
  purpose: 'PowerPoint proposal slide hero visual',
  visual_kind: 'editorial modular presentation system',
  aspect_ratio: '16:9',
  required_text: [],
  prompt: [
    'A refined editorial visual of a modular presentation-production system transforming a raw manuscript into structured layouts, editable native charts, and a polished slide deck.',
    'Show one clear left-to-right transformation with a strong focal hierarchy, premium restrained materials, and crop-safe open margins.',
    'No people and no interface screenshot.',
  ].join(' '),
};

try {
  const result = await generator.generate({ request, runDir: outputDir });
  const base = `generated-slide-visual-${timestamp()}`;
  const extension = path.extname(result.filename) || '.png';
  const imagePath = path.join(outputDir, `${base}${extension}`);
  const reportPath = path.join(outputDir, `${base}.quality.json`);
  await fs.writeFile(imagePath, result.buffer, { flag: 'wx' });
  await fs.writeFile(reportPath, `${JSON.stringify({
    schema_version: '0.4.0',
    request,
    provider: result.provider,
    model: result.model,
    cache_hit: result.cacheHit,
    cache_key: result.cacheKey,
    attempts: result.attempts,
    quality_review: result.qualityReview,
    input_tokens: result.inputTokens,
    output_tokens: result.outputTokens,
    image_path: imagePath,
  }, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' });
  process.stdout.write(`${JSON.stringify({
    status: 'PASS',
    image_path: imagePath,
    report_path: reportPath,
    attempts: result.attempts,
    scores: result.qualityReview?.scores || null,
    minimum_score: result.qualityReview?.minimum_score || null,
    input_tokens: result.inputTokens,
    output_tokens: result.outputTokens,
  }, null, 2)}\n`);
} finally {
  client.proc?.kill();
}
