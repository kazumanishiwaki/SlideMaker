import fs from 'node:fs/promises';
import fssync from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const DEFAULT_PYTHON = '/Users/kazuma/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';

export function resolvePython() {
  const configured = process.env.NEXTGEN_PYTHON;
  if (configured) return configured;
  return fssync.existsSync(DEFAULT_PYTHON) ? DEFAULT_PYTHON : 'python3';
}

export function runCommand(command, args, { cwd, timeoutMs = 180000, onOutput = null } = {}) {
  return new Promise((resolve, reject) => {
    const proc = spawn(command, args, { cwd, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    const stdout = [];
    const stderr = [];
    const timer = setTimeout(() => {
      proc.kill('SIGTERM');
      reject(new Error(`command timed out after ${timeoutMs}ms`));
    }, timeoutMs);
    proc.stdout.on('data', (chunk) => {
      stdout.push(chunk);
      onOutput?.({ stream: 'stdout', text: chunk.toString('utf8') });
    });
    proc.stderr.on('data', (chunk) => {
      stderr.push(chunk);
      onOutput?.({ stream: 'stderr', text: chunk.toString('utf8') });
    });
    proc.on('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
    proc.on('close', (code, signal) => {
      clearTimeout(timer);
      resolve({ code, signal, stdout: Buffer.concat(stdout).toString('utf8'), stderr: Buffer.concat(stderr).toString('utf8') });
    });
  });
}

async function readJsonIfPresent(target) {
  try { return JSON.parse(await fs.readFile(target, 'utf8')); } catch { return null; }
}

export class NextgenPythonCore {
  constructor({ nextgenRoot, store, onEvent = null } = {}) {
    this.nextgenRoot = path.resolve(nextgenRoot);
    this.store = store;
    this.python = resolvePython();
    this.onEvent = onEvent;
  }

  emit(runId, stage, payload = {}) {
    this.onEvent?.({ type: 'core_progress', runId, stage, ...payload });
  }

  async invoke(runId, args, stage, { acceptCodes = [0] } = {}) {
    this.emit(runId, stage, { status: 'running' });
    const started = Date.now();
    let result;
    try {
      result = await runCommand(this.python, ['-m', 'slideharness_next.cli', ...args], {
        cwd: this.nextgenRoot,
        onOutput: (event) => this.emit(runId, stage, event),
      });
    } finally {
      await this.store.appendUsage(runId, {
        kind: 'deterministic',
        stage,
        provider: 'slideharness-next-python',
        duration_ms: Date.now() - started,
        cache_hit: false,
      });
    }
    if (!acceptCodes.includes(result.code)) {
      const error = new Error(result.stderr.trim() || result.stdout.trim() || `${stage} failed with code ${result.code}`);
      error.result = result;
      throw error;
    }
    this.emit(runId, stage, { status: 'completed' });
    return result;
  }

  async prepare(runId) {
    const { state, root, template, sources, designGuide } = await this.store.inputPaths(runId);
    if (!template) throw new Error('template is required');
    if (!sources.length) throw new Error('at least one source is required');
    await this.store.updateState(runId, { ...state, status: 'preparing', stage: 'prepare', error: null });
    const prepared = path.join(root, 'prepared');
    await this.invoke(runId, ['ingest', '--source', ...sources, '--out-dir', prepared], 'ingest');
    if (designGuide) {
      await this.invoke(runId, ['ingest', '--source', designGuide, '--out-dir', path.join(prepared, 'design-guide')], 'ingest-design-guide');
    }
    await this.invoke(runId, ['compile-template', '--template', template, '--out-dir', prepared], 'compile-template');
    const next = await this.store.updateState(runId, (current) => {
      current.status = 'prepared';
      current.stage = 'codex_planning';
      current.error = null;
      return current;
    });
    return next;
  }

  async buildAt(runId, {
    plan,
    output,
    manageState = false,
    stage = 'build-source',
    informationDensity = null,
    decorativeness = null,
    structuredVisualMode = null,
  } = {}) {
    const { state, root, template, sources, assetManifest } = await this.store.inputPaths(runId);
    plan = plan || path.join(root, 'plan', 'deck_spec.json');
    if (!fssync.existsSync(plan)) throw new Error('Codex plan/deck_spec.json is missing');
    output = output || path.join(root, 'output');
    const args = [
      'build-source', '--template', template, '--source', ...sources,
      '--plan', plan, '--out-dir', output,
      '--composition-mode', state.composition_mode,
      '--information-density', informationDensity || state.information_density || 'medium',
      '--decorativeness', decorativeness || state.decorativeness || 'medium',
      '--structured-visual-mode', structuredVisualMode || state.structured_visual_mode || 'native',
      '--no-template-preview',
    ];
    if (state.allow_shadows) args.push('--allow-shadows');
    if (fssync.existsSync(assetManifest)) args.push('--asset-manifest', assetManifest);
    if (manageState) {
      await this.store.updateState(runId, (current) => {
        current.status = 'building';
        current.stage = 'compose_and_qa';
        current.error = null;
        return current;
      });
    }
    const result = await this.invoke(runId, args, stage, { acceptCodes: [0, 2] });
    const summary = await readJsonIfPresent(path.join(output, 'summary.json'));
    const assetRequests = await readJsonIfPresent(path.join(output, 'asset_requests.json')) || [];
    const awaiting = assetRequests.filter((item) => item.status === 'awaiting_image');
    const buildResult = {
      result,
      summary,
      assetRequests,
      awaiting,
      artifact: fssync.existsSync(path.join(output, 'deck.pptx')) ? path.join(output, 'deck.pptx') : null,
      montage: fssync.existsSync(path.join(output, 'render', 'montage.png')) ? path.join(output, 'render', 'montage.png') : null,
      status: awaiting.length ? 'awaiting_images' : (summary?.status === 'PASS' && result.code === 0 ? 'completed' : 'failed'),
    };
    if (!manageState) return buildResult;
    const next = await this.store.updateState(runId, (current) => {
      current.summary = summary;
      current.artifact = buildResult.artifact ? 'output/deck.pptx' : null;
      current.montage = buildResult.montage ? 'output/render/montage.png' : null;
      current.asset_requests = assetRequests;
      current.status = buildResult.status;
      current.stage = awaiting.length ? 'image_resolution' : 'completed';
      if (current.status === 'completed' && !current.revision) current.revision = 1;
      current.error = current.status === 'failed' ? (summary || result.stderr || 'build failed') : null;
      return current;
    });
    return next;
  }

  async build(runId) {
    return this.buildAt(runId, { manageState: true });
  }

  async buildCandidate(runId, plan, output, policy = {}) {
    return this.buildAt(runId, {
      plan,
      output,
      manageState: false,
      stage: 'build-regenerated-slide',
      informationDensity: policy.informationDensity,
      decorativeness: policy.decorativeness,
      structuredVisualMode: policy.structuredVisualMode,
    });
  }

  async isolateSlide(runId, { base, candidate, slideIndex, output, report }) {
    await this.invoke(runId, [
      'isolate-slide', '--base', base, '--candidate', candidate,
      '--slide-index', String(slideIndex), '--out', output, '--report', report,
    ], 'isolate-regenerated-slide');
    return readJsonIfPresent(report);
  }

  async verifyExisting(runId, { pptx, plan, output, compositionMode, informationDensity, decorativeness, structuredVisualMode, allowShadows }) {
    const { template, sources } = await this.store.inputPaths(runId);
    const args = [
      'verify-existing', '--pptx', pptx, '--plan', plan, '--out-dir', output,
      '--composition-mode', compositionMode,
      '--information-density', informationDensity,
      '--decorativeness', decorativeness,
      '--structured-visual-mode', structuredVisualMode || 'native',
    ];
    if (template) args.push('--template', template);
    if (sources?.length) args.push('--source', ...sources);
    if (allowShadows) args.push('--allow-shadows');
    const result = await this.invoke(runId, args, 'verify-regenerated-deck', { acceptCodes: [0, 2] });
    const report = await readJsonIfPresent(path.join(output, 'qa-final-regeneration.json'));
    if (result.code !== 0 || report?.status !== 'PASS') throw new Error('regenerated deck failed final QA');
    return report;
  }

  async check() {
    const checkCommand = async (command, args) => {
      try {
        const result = await runCommand(command, args, { cwd: this.nextgenRoot, timeoutMs: 30000 });
        return { ok: result.code === 0, output: (result.stdout || result.stderr).split('\n')[0].trim() };
      } catch (error) {
        return { ok: false, output: error.message };
      }
    };
    const [result, tesseract, pdftoppm] = await Promise.all([
      runCommand(this.python, ['-c', 'import pptx, PIL, docx, pypdf; print("ok")'], { cwd: this.nextgenRoot, timeoutMs: 30000 }),
      checkCommand('tesseract', ['--version']),
      checkCommand('pdftoppm', ['-v']),
    ]);
    return {
      python: this.python,
      python_ok: result.code === 0 && result.stdout.trim() === 'ok',
      stderr: result.stderr.trim(),
      tesseract,
      pdf_rasterizer: pdftoppm,
      ocr_ready: tesseract.ok && pdftoppm.ok,
    };
  }
}
