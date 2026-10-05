import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CodexAppServerClient } from '../app/codex-app-server-client.mjs';
const here = path.dirname(fileURLToPath(import.meta.url));

async function waitFor(predicate, timeoutMs=2500) {
  const started=Date.now();
  while (Date.now()-started < timeoutMs) {
    if (predicate()) return;
    await new Promise(r=>setTimeout(r,20));
  }
  throw new Error('timed out waiting for fake Codex event');
}

test('Codex App Server client initializes, lists models, streams, and answers approval', async () => {
  const client = new CodexAppServerClient({codexBin:path.join(here,'fake-codex.mjs'),cwd:path.resolve(here,'..')});
  const deltas=[]; const items=[]; const completed=[]; let approval;
  client.on('agent_delta', x=>deltas.push(x));
  client.on('item_completed', x=>items.push(x));
  client.on('turn_completed', x=>completed.push(x));
  client.on('server_request', x=>{ approval=x; client.respondToServerRequest(String(x.requestId),{decision:'accept'}); });
  try {
    await client.start();
    assert.equal(client.available,true);
    const models=await client.modelList();
    assert.equal(models.data[0].model,'gpt-5.6-sol');
    const capabilities=await client.modelProviderCapabilitiesRead();
    assert.equal(capabilities.imageGeneration,true);
    const account=await client.accountRead();
    assert.equal(account.account.type,'chatgpt');
    const login=await client.loginChatGPT();
    assert.equal(login.type,'chatgpt');
    const thread=await client.startThread({cwd:path.resolve(here,'..')});
    assert.equal(thread.thread.id,'thr_fake');
    const turn=await client.startTurn({threadId:'thr_fake',cwd:path.resolve(here,'..'),text:'test',skillPath:path.resolve(here,'../skill/SKILL.md')});
    assert.equal(turn.turn.id,'turn_fake');
    await waitFor(()=>deltas.length>0 && items.length>0 && approval && completed.length>0);
    assert.equal(deltas[0].delta,'mock delta');
    assert.equal(approval.method,'item/commandExecution/requestApproval');
    assert.equal(items[0].item.type,'agentMessage');
    assert.equal(completed.length,1);
  } finally {
    client.proc?.kill();
  }
});
