import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const ROLE_RULES = {
  template: { extensions: new Set(['.pptx', '.potx']), maxBytes: 50 * 1024 * 1024 },
  source: { extensions: new Set(['.md', '.txt', '.docx', '.pdf', '.pptx']), maxBytes: 25 * 1024 * 1024 },
  'design-guide': { extensions: new Set(['.md', '.txt', '.docx', '.pdf', '.pptx']), maxBytes: 25 * 1024 * 1024 },
  asset: { extensions: new Set(['.png', '.jpg', '.jpeg', '.webp']), maxBytes: 25 * 1024 * 1024 },
};

const THREE_LEVELS = new Set(['low', 'medium', 'high']);
const STRUCTURED_VISUAL_MODES = new Set(['auto', 'native', 'generated-image']);

function safeName(value, fallback = 'file') {
  const base = path.basename(String(value || fallback).normalize('NFKC'));
  const cleaned = base.replace(/[^\p{L}\p{N}._-]+/gu, '-').replace(/^-+|-+$/g, '');
  return cleaned || fallback;
}

async function writeJsonAtomic(target, value) {
  await fs.mkdir(path.dirname(target), { recursive: true });
  const temporary = `${target}.${process.pid}.tmp`;
  await fs.writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  await fs.rename(temporary, target);
}

export class NextgenRunStore {
  constructor(root) {
    this.root = path.resolve(root);
  }

  async init() {
    await fs.mkdir(this.root, { recursive: true });
  }

  runDir(runId) {
    if (!/^run-[a-f0-9-]{36}$/.test(String(runId))) throw new Error('invalid run id');
    return path.join(this.root, runId);
  }

  safePath(runId, relativePath) {
    const root = this.runDir(runId);
    const target = path.resolve(root, String(relativePath || ''));
    if (target !== root && !target.startsWith(`${root}${path.sep}`)) throw new Error('invalid run path');
    return target;
  }

  async createRun({
    name = 'slide-deck',
    instructions = '',
    compositionMode = 'auto',
    informationDensity = 'medium',
    decorativeness = 'medium',
    structuredVisualMode = 'native',
    allowShadows = false,
  } = {}) {
    if (!['auto', 'reconstruct', 'source-slides'].includes(compositionMode)) throw new Error('invalid composition mode');
    if (!THREE_LEVELS.has(informationDensity)) throw new Error('invalid information density');
    if (!THREE_LEVELS.has(decorativeness)) throw new Error('invalid decorativeness');
    if (!STRUCTURED_VISUAL_MODES.has(structuredVisualMode)) throw new Error('invalid structured visual mode');
    const runId = `run-${randomUUID()}`;
    const root = this.runDir(runId);
    for (const directory of ['inputs/sources', 'inputs/assets', 'prepared', 'plan', 'output', 'regeneration', 'versions']) {
      await fs.mkdir(path.join(root, directory), { recursive: true });
    }
    const now = new Date().toISOString();
    const state = {
      schema_version: '0.4.0-app-server.1',
      run_id: runId,
      name: String(name || 'slide-deck').slice(0, 120),
      status: 'created',
      stage: 'upload',
      instructions: String(instructions || '').slice(0, 20000),
      composition_mode: compositionMode,
      information_density: informationDensity,
      decorativeness,
      structured_visual_mode: structuredVisualMode,
      allow_shadows: Boolean(allowShadows),
      files: { template: null, sources: [], design_guide: null, assets: [] },
      codex: { thread_id: null, turn_id: null, model: null },
      revision: 0,
      active_regeneration: null,
      last_regeneration: null,
      artifact: null,
      montage: null,
      summary: null,
      error: null,
      created_at: now,
      updated_at: now,
    };
    await writeJsonAtomic(path.join(root, 'state.json'), state);
    await writeJsonAtomic(path.join(root, 'usage.json'), { schema_version: '0.4.0', entries: [], totals: { calls: 0, duration_ms: 0, cache_hits: 0 } });
    await this.writeRunConfig(runId, state);
    return state;
  }

  async writeRunConfig(runId, state = null) {
    const current = state || await this.readState(runId);
    const designGuide = current.files?.design_guide || null;
    const value = {
      schema_version: '0.4.0',
      composition_mode: current.composition_mode,
      information_density: current.information_density || 'medium',
      decorativeness: current.decorativeness || 'medium',
      structured_visual_mode: current.structured_visual_mode || 'native',
      allow_shadows: current.allow_shadows === true,
      instructions: current.instructions || '',
      design_guide: designGuide ? {
        filename: designGuide.filename,
        path: designGuide.path,
        prepared_path: 'prepared/design-guide/source_units.json',
      } : null,
    };
    await writeJsonAtomic(this.safePath(runId, 'run_config.json'), value);
    return value;
  }

  async listRuns() {
    await this.init();
    const names = await fs.readdir(this.root);
    const states = [];
    for (const name of names.filter((value) => value.startsWith('run-')).sort().reverse()) {
      try { states.push(await this.readState(name)); } catch {}
    }
    return states;
  }

  async readState(runId) {
    return JSON.parse(await fs.readFile(this.safePath(runId, 'state.json'), 'utf8'));
  }

  async updateState(runId, patch) {
    const current = await this.readState(runId);
    const next = typeof patch === 'function' ? await patch(current) : { ...current, ...patch };
    next.updated_at = new Date().toISOString();
    await writeJsonAtomic(this.safePath(runId, 'state.json'), next);
    return next;
  }

  async writeUpload(runId, role, filename, buffer, { assetId = null, provider = null } = {}) {
    const rule = ROLE_RULES[role];
    if (!rule) throw new Error('invalid upload role');
    if (!Buffer.isBuffer(buffer)) throw new Error('upload body must be binary');
    if (buffer.length === 0 || buffer.length > rule.maxBytes) throw new Error(`${role} file size is out of range`);
    const normalized = safeName(filename, `${role}.bin`);
    const extension = path.extname(normalized).toLowerCase();
    if (!rule.extensions.has(extension)) throw new Error(`${role} file type is unsupported`);
    let relativePath;
    if (role === 'template') relativePath = `inputs/template${extension}`;
    else if (role === 'design-guide') relativePath = `inputs/design-guide${extension}`;
    else if (role === 'source') relativePath = `inputs/sources/${Date.now()}-${normalized}`;
    else relativePath = `inputs/assets/${Date.now()}-${normalized}`;
    const target = this.safePath(runId, relativePath);
    await fs.writeFile(target, buffer, { flag: 'wx' });
    const record = { filename: normalized, path: relativePath, size_bytes: buffer.length };
    if (assetId) record.asset_id = String(assetId).slice(0, 200);
    if (provider) record.provider = String(provider).slice(0, 200);
    const state = await this.updateState(runId, (current) => {
      if (role === 'template') current.files.template = record;
      else if (role === 'design-guide') current.files.design_guide = record;
      else if (role === 'source') current.files.sources.push(record);
      else current.files.assets.push(record);
      if (!(role === 'asset' && current.status === 'regeneration_awaiting_images')) current.status = 'uploading';
      current.error = null;
      return current;
    });
    if (role === 'design-guide') await this.writeRunConfig(runId, state);
    if (role === 'asset' && assetId) await this.writeAssetManifest(runId, state.files.assets);
    return { record, state };
  }

  async writeAssetManifest(runId, assets) {
    const items = (assets || []).filter((item) => item.asset_id).map((item) => ({
      asset_id: item.asset_id,
      path: path.resolve(this.runDir(runId), item.path),
      provider: item.provider || 'signed-in-host-or-user-upload',
    }));
    await writeJsonAtomic(this.safePath(runId, 'inputs/asset_manifest.json'), { assets: items });
    return items;
  }

  async inputPaths(runId) {
    const state = await this.readState(runId);
    const root = this.runDir(runId);
    return {
      state,
      root,
      template: state.files.template ? path.resolve(root, state.files.template.path) : null,
      sources: state.files.sources.map((item) => path.resolve(root, item.path)),
      designGuide: state.files.design_guide ? path.resolve(root, state.files.design_guide.path) : null,
      assetManifest: this.safePath(runId, 'inputs/asset_manifest.json'),
    };
  }

  async appendUsage(runId, entry) {
    const target = this.safePath(runId, 'usage.json');
    let usage;
    try { usage = JSON.parse(await fs.readFile(target, 'utf8')); } catch {
      usage = { schema_version: '0.4.0', entries: [], totals: { calls: 0, duration_ms: 0, cache_hits: 0 } };
    }
    const normalized = {
      timestamp: new Date().toISOString(),
      kind: String(entry.kind || 'unknown'),
      stage: String(entry.stage || ''),
      provider: entry.provider ? String(entry.provider) : null,
      model: entry.model ? String(entry.model) : null,
      duration_ms: Math.max(0, Number(entry.duration_ms || 0)),
      cache_hit: entry.cache_hit === true,
      input_tokens: Number.isFinite(entry.input_tokens) ? entry.input_tokens : null,
      output_tokens: Number.isFinite(entry.output_tokens) ? entry.output_tokens : null,
      reason: entry.reason ? String(entry.reason).slice(0, 500) : null,
    };
    usage.entries.push(normalized);
    usage.totals = {
      calls: usage.entries.length,
      duration_ms: usage.entries.reduce((sum, item) => sum + Number(item.duration_ms || 0), 0),
      cache_hits: usage.entries.filter((item) => item.cache_hit).length,
      input_tokens: usage.entries.reduce((sum, item) => sum + Number(item.input_tokens || 0), 0),
      output_tokens: usage.entries.reduce((sum, item) => sum + Number(item.output_tokens || 0), 0),
    };
    await writeJsonAtomic(target, usage);
    return normalized;
  }
}

export { ROLE_RULES, THREE_LEVELS, STRUCTURED_VISUAL_MODES, safeName, writeJsonAtomic };
