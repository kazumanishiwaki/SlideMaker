import fs from 'node:fs/promises';
import fssync from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';

import { writeJsonAtomic } from './run-store.mjs';

const INPUTS = [
  'prepared/source_units.json',
  'prepared/content_model.json',
  'prepared/coverage_requirements.json',
  'prepared/template_system.json',
  'prepared/design-guide/source_units.json',
  'run_config.json',
];

function validDeck(value) {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value) && typeof value.title === 'string' && Array.isArray(value.slides) && value.slides.length > 0);
}

export class PlanCache {
  constructor({ cacheDir } = {}) {
    const root = cacheDir || process.env.NEXTGEN_CACHE || path.join(os.homedir(), '.cache', 'slideharness-next');
    this.cacheDir = path.resolve(root, 'plans');
    this.available = true;
  }

  async keyForRun(store, runId, skillPath) {
    const hash = createHash('sha256');
    hash.update('slideharness-next-plan-cache-v1\0');
    for (const relative of INPUTS) {
      const target = store.safePath(runId, relative);
      if (!fssync.existsSync(target)) continue;
      hash.update(relative);
      hash.update('\0');
      hash.update(await fs.readFile(target));
      hash.update('\0');
    }
    hash.update('planner-skill\0');
    hash.update(await fs.readFile(skillPath));
    return hash.digest('hex');
  }

  entryPath(key) {
    if (!/^[a-f0-9]{64}$/.test(String(key))) throw new Error('invalid plan cache key');
    return path.join(this.cacheDir, `${key}.json`);
  }

  async load(key) {
    try {
      const entry = JSON.parse(await fs.readFile(this.entryPath(key), 'utf8'));
      if (entry.qa_status !== 'PASS' || !validDeck(entry.plan)) return null;
      return entry;
    } catch {
      return null;
    }
  }

  async save(key, plan, summary) {
    if (summary?.status !== 'PASS' || !validDeck(plan)) return false;
    await fs.mkdir(this.cacheDir, { recursive: true });
    await writeJsonAtomic(this.entryPath(key), {
      schema_version: '0.4.0',
      key,
      qa_status: 'PASS',
      created_at: new Date().toISOString(),
      summary: {
        slide_count: summary.slide_count,
        recipes: summary.recipes,
        composition_mode: summary.composition_mode,
      },
      plan,
    });
    return true;
  }

  async invalidate(key) {
    try { await fs.unlink(this.entryPath(key)); } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
}

export class NullPlanCache {
  constructor() { this.available = false; }
  async keyForRun() { return null; }
  async load() { return null; }
  async save() { return false; }
  async invalidate() {}
}

