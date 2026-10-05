import fs from 'node:fs/promises';
import fssync from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import crypto from 'node:crypto';

export class ProjectStore {
  constructor({ root, engineCli }) {
    this.root = path.resolve(root);
    this.engineCli = path.resolve(engineCli);
  }

  sanitizeId(value) {
    return String(value || 'project')
      .normalize('NFKC')
      .replace(/[^a-zA-Z0-9_-]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || `project-${Date.now()}`;
  }

  projectDir(projectId) {
    return path.join(this.root, this.sanitizeId(projectId));
  }

  async list() {
    await fs.mkdir(this.root, { recursive: true });
    const entries = await fs.readdir(this.root, { withFileTypes: true });
    const out = [];
    for (const e of entries) {
      if (!e.isDirectory()) continue;
      const p = path.join(this.root, e.name, 'project.json');
      try {
        out.push(JSON.parse(await fs.readFile(p, 'utf8')));
      } catch {}
    }
    return out;
  }

  async saveUploadedFile({ projectId, role, filename, base64 }) {
    const projectDir = this.projectDir(projectId);
    const staging = path.join(projectDir, '.staging');
    await fs.mkdir(staging, { recursive: true });
    const ext = path.extname(filename || '') || (role === 'design' ? '.md' : '');
    const safeName = `${role}${ext}`;
    const dst = path.join(staging, safeName);
    const buf = Buffer.from(base64, 'base64');
    if (buf.length > 80 * 1024 * 1024) throw new Error('File too large (80MB max per file)');
    await fs.writeFile(dst, buf);
    return dst;
  }

  async createFromUploads({ projectId, name, files, preferences = {} }) {
    const id = this.sanitizeId(projectId || name || `project-${Date.now()}`);
    const projectDir = this.projectDir(id);
    await fs.rm(projectDir, { recursive: true, force: true });
    await fs.mkdir(projectDir, { recursive: true });

    const required = {};
    const assetUploads = [];
    for (const file of files || []) {
      if (file.role === 'asset') assetUploads.push(file);
      else required[file.role] = await this.saveUploadedFile({ projectId: id, ...file });
    }
    if (!required.ppt || !required.manuscript || !required.design) {
      throw new Error('ppt / manuscript / design are required');
    }
    await this.runPython(['init', '--project', projectDir, '--ppt', required.ppt, '--manuscript', required.manuscript, '--design', required.design]);

    const uploadedAssets = [];
    if (assetUploads.length) {
      const assetDir = path.join(projectDir, 'inputs', 'assets');
      await fs.mkdir(assetDir, { recursive: true });
      for (let index = 0; index < assetUploads.length; index += 1) {
        const file = assetUploads[index];
        const ext = path.extname(file.filename || '').toLowerCase() || '.png';
        if (!['.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'].includes(ext)) continue;
        const base = this.sanitizeId(path.basename(file.filename || `asset-${index + 1}`, ext)) || `asset-${index + 1}`;
        const buffer = Buffer.from(file.base64 || '', 'base64');
        if (buffer.length > 30 * 1024 * 1024) throw new Error(`Image too large: ${file.filename}`);
        const dst = path.join(assetDir, `${String(index + 1).padStart(2, '0')}-${base}${ext}`);
        await fs.writeFile(dst, buffer);
        uploadedAssets.push(path.relative(projectDir, dst).split(path.sep).join('/'));
      }
    }

    await fs.rm(path.join(projectDir, '.staging'), { recursive: true, force: true });
    const metaPath = path.join(projectDir, 'project.json');
    const meta = JSON.parse(await fs.readFile(metaPath, 'utf8'));
    meta.name = name || id;
    meta.preferences = {
      review_mode: preferences.reviewMode || 'detailed',
      source_continuity: preferences.sourceContinuity || 'balanced',
      target_slide_count: preferences.targetSlideCount || null,
    };
    meta.uploaded_assets = uploadedAssets;
    await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));
    return { projectId: id, projectDir, meta };
  }

  runPython(args, timeoutMs = 180000) {
    return new Promise((resolve, reject) => {
      const proc = spawn('python3', [this.engineCli, ...args], { cwd: path.dirname(this.engineCli) });
      let stdout = '';
      let stderr = '';
      const timer = setTimeout(() => { proc.kill('SIGKILL'); reject(new Error('slide-engine timed out')); }, timeoutMs);
      proc.stdout.on('data', (d) => stdout += d);
      proc.stderr.on('data', (d) => stderr += d);
      proc.on('error', (e) => { clearTimeout(timer); reject(e); });
      proc.on('close', (code) => {
        clearTimeout(timer);
        if (code === 0) resolve({ stdout, stderr });
        else reject(new Error(stderr || `slide-engine exited ${code}`));
      });
    });
  }

  async analyze(projectId) {
    const projectDir = this.projectDir(projectId);
    return this.runPython(['analyze', '--project', projectDir], 240000);
  }

  async buildSkeleton(projectId) {
    const projectDir = this.projectDir(projectId);
    const result = await this.runPython(['build-skeleton', '--project', projectDir], 240000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async compilePlans(projectId) {
    const projectDir = this.projectDir(projectId);
    const result = await this.runPython(['compile-plans', '--project', projectDir], 120000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async planLayouts(projectId, { slides = null } = {}) {
    const projectDir = this.projectDir(projectId);
    const args = ['plan-layouts', '--project', projectDir];
    if (slides?.length) args.push('--slides', slides.join(','));
    const result = await this.runPython(args, 180000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async compose(projectId, { slides = null, output = 'presentation_draft.pptx' } = {}) {
    const projectDir = this.projectDir(projectId);
    const args = ['compose', '--project', projectDir, '--output', output];
    if (slides?.length) args.push('--slides', slides.join(','));
    const result = await this.runPython(args, 300000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async validateOutput(projectId, relativePptx, kind = 'draft') {
    const projectDir = this.projectDir(projectId);
    const result = await this.runPython(['validate', '--project', projectDir, '--pptx', relativePptx, '--kind', kind], 300000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async validateDeck(projectId) {
    const projectDir = this.projectDir(projectId);
    const result = await this.runPython(['validate-deck', '--project', projectDir], 120000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }


  async saveImageUpload(projectId, { recipeId, filename, base64 }) {
    if (!recipeId || !base64) throw new Error('recipeId / base64 are required');
    const projectDir = this.projectDir(projectId);
    const ext = path.extname(filename || '').toLowerCase() || '.png';
    if (!['.png','.jpg','.jpeg','.webp'].includes(ext)) throw new Error('unsupported image extension');
    const safeRecipe = this.sanitizeId(recipeId);
    const dir = path.join(projectDir, 'inputs', 'assets');
    await fs.mkdir(dir, { recursive: true });
    const dst = path.join(dir, `${safeRecipe}-${Date.now()}${ext}`);
    const buf = Buffer.from(base64, 'base64');
    if (buf.length > 30 * 1024 * 1024) throw new Error('Image too large (30MB max)');
    await fs.writeFile(dst, buf);
    return path.relative(projectDir, dst).split(path.sep).join('/');
  }

  async generateImages(projectId, { provider = 'auto', slides = null, recipes = null, quality = process.env.OPENAI_IMAGE_QUALITY || null, model = process.env.OPENAI_IMAGE_MODEL || 'gpt-image-2', manual = {}, allowMock = false } = {}) {
    const projectDir = this.projectDir(projectId);
    const args = ['generate-images', '--project', projectDir, '--provider', provider, '--model', model];
    if (slides?.length) args.push('--slides', slides.join(','));
    if (recipes?.length) args.push('--recipes', recipes.join(','));
    if (quality) args.push('--quality', quality);
    for (const [recipeId, rel] of Object.entries(manual || {})) args.push('--manual', `${recipeId}=${rel}`);
    if (allowMock) args.push('--allow-mock');
    const result = await this.runPython(args, provider === 'openai' || provider === 'auto' ? 420000 : 180000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async selectImage(projectId, recipeId, assetId) {
    const projectDir = this.projectDir(projectId);
    const result = await this.runPython(['select-image', '--project', projectDir, '--recipe', recipeId, '--asset', assetId], 120000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async updateImageRecipe(projectId, recipeId, { prompt = null, negativeSpace = null, focalPoint = null } = {}) {
    const projectDir = this.projectDir(projectId);
    const args = ['update-image-recipe', '--project', projectDir, '--recipe', recipeId];
    if (prompt !== null) args.push('--prompt', String(prompt));
    if (negativeSpace !== null) args.push('--negative-space', String(negativeSpace));
    if (focalPoint !== null) {
      const value = focalPoint === 'auto' ? 'auto' : Array.isArray(focalPoint) ? focalPoint.join(',') : String(focalPoint);
      args.push('--focal-point', value);
    }
    const result = await this.runPython(args, 120000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async validateImages(projectId) {
    const projectDir = this.projectDir(projectId);
    const result = await this.runPython(['validate-images', '--project', projectDir], 120000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async refreshContinuity(projectId) {
    const projectDir = this.projectDir(projectId);
    const result = await this.runPython(['refresh-continuity', '--project', projectDir], 180000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async applyFeedback(projectId, { slideId, kind, value }) {
    const projectDir = this.projectDir(projectId);
    const args = ['feedback', '--project', projectDir, '--slide', slideId, '--kind', kind, '--value', typeof value === 'string' ? value : JSON.stringify(value)];
    if (typeof value !== 'string') args.push('--json');
    const result = await this.runPython(args, 120000);
    let parsed = null;
    try { parsed = JSON.parse(result.stdout); } catch {}
    return { ...result, parsed };
  }

  async readJson(projectId, relativePath, fallback = null) {
    const safe = this.safeProjectPath(projectId, relativePath);
    try { return JSON.parse(await fs.readFile(safe, 'utf8')); } catch { return fallback; }
  }

  async writeJson(projectId, relativePath, value) {
    const safe = this.safeProjectPath(projectId, relativePath);
    await fs.mkdir(path.dirname(safe), { recursive: true });
    await fs.writeFile(safe, JSON.stringify(value, null, 2) + '\n');
  }

  safeProjectPath(projectId, relativePath) {
    const base = this.projectDir(projectId);
    const target = path.resolve(base, relativePath);
    if (!target.startsWith(base + path.sep) && target !== base) throw new Error('Invalid project path');
    return target;
  }

  async fileInfo(projectId, relativePath) {
    const target = this.safeProjectPath(projectId, relativePath);
    const stat = await fs.stat(target);
    return { target, stat };
  }

  async snapshot(projectId) {
    const [project, state, manuscript, slides, assets, template, designFingerprint, componentCatalog, deckPlan, slidePlanBundle, visualPlan, matches, continuityPlan, deckArtDirection, imageRecipes, imageAssetManifest, continuityQa, imageQa, deckImageCoherence, sampleSelection, sampleQa, qa, deckHarmony, finalQa] = await Promise.all([
      this.readJson(projectId, 'project.json', {}),
      this.readJson(projectId, 'state/project_state.json', {}),
      this.readJson(projectId, 'analysis/manuscript_analysis.json', {}),
      this.readJson(projectId, 'analysis/source_slides.json', {}),
      this.readJson(projectId, 'analysis/source_assets.json', {}),
      this.readJson(projectId, 'analysis/template_profile.json', {}),
      this.readJson(projectId, 'analysis/design_fingerprint.json', {}),
      this.readJson(projectId, 'analysis/component_catalog.json', {}),
      this.readJson(projectId, 'planning/deck_plan.json', null),
      this.readJson(projectId, 'planning/slide_plans.json', null),
      this.readJson(projectId, 'planning/visual_plan.json', null),
      this.readJson(projectId, 'planning/slide_matching.json', null),
      this.readJson(projectId, 'planning/continuity_plan.json', null),
      this.readJson(projectId, 'planning/deck_art_direction.json', null),
      this.readJson(projectId, 'planning/image_recipes.json', null),
      this.readJson(projectId, 'render/generated_assets/manifest.json', null),
      this.readJson(projectId, 'qa/continuity_qa.json', null),
      this.readJson(projectId, 'qa/image_harmony.json', null),
      this.readJson(projectId, 'qa/deck_image_coherence.json', null),
      this.readJson(projectId, 'planning/sample_selection.json', null),
      this.readJson(projectId, 'qa/sample_deck_qa.json', null),
      this.readJson(projectId, 'qa/deck_qa.json', null),
      this.readJson(projectId, 'qa/deck_harmony.json', null),
      this.readJson(projectId, 'qa/presentation_final_qa.json', null),
    ]);
    const sourceRendersDir = this.safeProjectPath(projectId, 'render/source_renders');
    let sourceRenders = [];
    try {
      sourceRenders = (await fs.readdir(sourceRendersDir)).filter(f => f.endsWith('.png')).sort();
    } catch {}
    let slidePlans = [];
    let slidePlanDetails = [];
    try {
      slidePlans = (await fs.readdir(this.safeProjectPath(projectId, 'planning/slide_plans'))).filter(f => f.endsWith('.json')).sort();
      for (const f of slidePlans) {
        const doc=await this.readJson(projectId, `planning/slide_plans/${f}`, null);
        if (doc) slidePlanDetails.push({
          slide_id:doc.slide_id,
          fill_policy:doc.fill_policy || doc.layout_request?.fill_policy || null,
          family:doc.layout_request?.family || null,
          density:doc.layout_request?.density || null,
          text_side:doc.layout_request?.text_side || null,
          image_recipe_id:doc.layout_request?.image_recipe_id || null,
          image_position:doc.layout_request?.image_position || null,
          overlay_position:doc.layout_request?.overlay_position || null,
          composer_support:doc.composer_support || null,
          status:doc.status || null,
        });
      }
    } catch {}
    let layoutPlans = [];
    try {
      const files=(await fs.readdir(this.safeProjectPath(projectId, 'render/layout_plans'))).filter(f => f.endsWith('.json')).sort();
      for (const f of files) {
        const doc=await this.readJson(projectId, `render/layout_plans/${f}`, null);
        if (doc) layoutPlans.push({ slide_id:doc.slide_id, family:doc.family, density:doc.density, fill_policy:doc.fill_policy || doc.quality?.fill_policy || null, quality:doc.quality, image_slots:doc.image_slots || [], image_lineage:doc.image_lineage || null, geometry:doc.geometry || null, planned_only:Boolean(doc.planned_only), file:f });
      }
    } catch {}
    let sampleRenders = [];
    try { sampleRenders = (await fs.readdir(this.safeProjectPath(projectId, 'render/output_validation/sample_deck'))).filter(f => f.endsWith('.png')).sort(); } catch {}
    let finalRenders = [];
    try { finalRenders = (await fs.readdir(this.safeProjectPath(projectId, 'render/output_validation/presentation_final'))).filter(f => f.endsWith('.png')).sort(); } catch {}
    let decisionTrace = [];
    try {
      const raw=await fs.readFile(this.safeProjectPath(projectId, 'decisions/decision_trace.jsonl'),'utf8');
      decisionTrace=raw.split(/\r?\n/).filter(Boolean).slice(-200).map(line=>{ try { return JSON.parse(line); } catch { return null; } }).filter(Boolean);
    } catch {}
    const generatedImages = (imageAssetManifest?.assets || []).map(asset => ({
      ...asset,
      rawUrl: asset.raw_path ? `/project/${encodeURIComponent(projectId)}/file?path=${encodeURIComponent(asset.raw_path)}` : null,
      processedUrl: asset.processed_path ? `/project/${encodeURIComponent(projectId)}/file?path=${encodeURIComponent(asset.processed_path)}` : null,
    }));
    return { project, state, manuscript, sourceSlides: slides, sourceAssets: assets, template, designFingerprint, componentCatalog, deckPlan, slidePlanBundle, visualPlan, matches, continuityPlan, deckArtDirection, imageRecipes, imageAssetManifest, generatedImages, continuityQa, imageQa, deckImageCoherence, sampleSelection, slidePlans, slidePlanDetails, layoutPlans, sampleQa, qa, deckHarmony, finalQa, sourceRenders, sampleRenders, finalRenders, decisionTrace };
  }
}
