import { spawn } from 'node:child_process';
import os from 'node:os';

const python = process.env.PYTHON || 'python3';
const maxJobs = Math.max(1, Number(process.env.PPT_TEST_JOBS || Math.min(4, os.cpus().length || 2)));

const tasks = [
  { name: 'node', command: 'node', args: ['--test', 'tests/app-server-client.test.mjs'] },
  { name: 'compose', command: python, args: ['tests/test_compose.py'] },
  { name: 'layout-engine', command: python, args: ['tests/test_layout_engine.py'] },
  { name: 'skeleton', command: python, args: ['tests/test_skeleton.py'] },
  { name: 'state', command: python, args: ['tests/test_state.py'] },
  { name: 'deck-qa', command: python, args: ['tests/test_validate_deck.py'] },
  { name: 'design-continuity', command: python, args: ['-m','pytest','-q','tests/test_design_continuity.py'] },
  { name: 'image-pipeline', command: python, args: ['tests/test_image_pipeline.py'] },
  { name: 'render-repeat', command: python, args: ['tests/test_render_source.py'] },
  // Run render-heavy cases in separate processes. LibreOffice and Poppler are
  // isolated by the production renderer, so this also exercises App Server-style
  // concurrent conversions without forcing the full suite into a long serial turn.
  {
    name: 'render-qa:intentional-whitespace', command: python,
    args: ['-m', 'unittest', 'tests.test_validate_output.ValidateOutputTests.test_intentional_whitespace_uses_fit_to_intent_qa', '-v'],
  },
  {
    name: 'render-qa:pixel-diff', command: python,
    args: ['-m', 'unittest', 'tests.test_validate_output.ValidateOutputTests.test_pixel_diff_rejects_unplanned_mutation', '-v'],
  },
];

function runTask(task) {
  return new Promise((resolve) => {
    const started = Date.now();
    const child = spawn(task.command, task.args, {
      cwd: process.cwd(),
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', (error) => resolve({ task, code: 1, stdout, stderr: `${stderr}\n${error.stack || error}`, elapsed: Date.now() - started }));
    child.on('close', (code, signal) => resolve({ task, code: code ?? 1, signal, stdout, stderr, elapsed: Date.now() - started }));
  });
}

const pending = [...tasks];
const results = [];

async function worker() {
  while (pending.length) {
    const task = pending.shift();
    const result = await runTask(task);
    results.push(result);
    const status = result.code === 0 ? 'PASS' : 'FAIL';
    console.log(`[${status}] ${task.name} (${(result.elapsed / 1000).toFixed(2)}s)`);
    if (result.code !== 0) {
      if (result.stdout.trim()) console.log(result.stdout.trimEnd());
      if (result.stderr.trim()) console.error(result.stderr.trimEnd());
    }
  }
}

await Promise.all(Array.from({ length: Math.min(maxJobs, tasks.length) }, () => worker()));

const failed = results.filter((result) => result.code !== 0);
const elapsed = results.reduce((max, result) => Math.max(max, result.elapsed), 0);
console.log(`\n${results.length - failed.length}/${results.length} test groups passed; longest group ${(elapsed / 1000).toFixed(2)}s; jobs=${maxJobs}`);
if (failed.length) process.exit(1);
