import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { PlanCache } from '../app/plan-cache.mjs';
import { NextgenRunStore, writeJsonAtomic } from '../app/run-store.mjs';


test('exact plan cache reuses only QA-PASS plans for identical prepared inputs', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'slideharness-plan-cache-'));
  try {
    const store = new NextgenRunStore(path.join(root, 'workspace'));
    await store.init();
    const state = await store.createRun({ name: 'cache-test' });
    const skill = path.join(root, 'SKILL.md');
    await fs.writeFile(skill, '# Planner v1\n', 'utf8');
    await writeJsonAtomic(store.safePath(state.run_id, 'prepared/source_units.json'), { units: [{ id: 'U1', text: 'same source' }] });
    await writeJsonAtomic(store.safePath(state.run_id, 'prepared/content_model.json'), { title: 'Same' });
    const cache = new PlanCache({ cacheDir: path.join(root, 'cache') });
    const key = await cache.keyForRun(store, state.run_id, skill);
    const plan = { title: 'Cached', slides: [{ slide_id: 'S001', recipe: 'cover' }] };

    assert.equal(await cache.save(key, plan, { status: 'FAIL' }), false);
    assert.equal(await cache.load(key), null);
    assert.equal(await cache.save(key, plan, { status: 'PASS', slide_count: 1, recipes: ['cover'], composition_mode: 'reconstruct' }), true);
    assert.deepEqual((await cache.load(key)).plan, plan);

    await writeJsonAtomic(store.safePath(state.run_id, 'prepared/source_units.json'), { units: [{ id: 'U1', text: 'changed source' }] });
    const changedKey = await cache.keyForRun(store, state.run_id, skill);
    assert.notEqual(changedKey, key);
    assert.equal(await cache.load(changedKey), null);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
