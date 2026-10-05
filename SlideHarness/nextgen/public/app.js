const $ = (selector) => document.querySelector(selector);
const state = { runId: null, run: null, approvalId: null, poll: null, slides: [], slidesRevision: null };

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function log(message) {
  if (!message) return;
  const output = $('#log');
  output.textContent += `${String(message).trim()}\n`;
  output.scrollTop = output.scrollHeight;
}

function fileUrl(relativePath) {
  return `/api/runs/${encodeURIComponent(state.runId)}/file?path=${encodeURIComponent(relativePath)}`;
}

function renderRun(run) {
  state.run = run;
  $('#runTitle').textContent = run.name || run.run_id;
  $('#runStatus').textContent = String(run.status || 'unknown').toUpperCase();
  $('#runStatus').className = `badge ${run.status === 'completed' ? 'good' : run.status === 'failed' ? 'bad' : ''}`;
  const order = ['upload', 'prepare', 'codex_planning', 'compose_and_qa', 'completed'];
  const normalizedStage = run.stage === 'codex_regeneration'
    ? 'codex_planning'
    : ['image_generation', 'image_resolution'].includes(run.stage) ? 'compose_and_qa' : run.stage;
  const current = Math.max(0, order.indexOf(normalizedStage));
  document.querySelectorAll('#stages li').forEach((item, index) => {
    item.classList.toggle('active', index === current && run.status !== 'completed');
    item.classList.toggle('done', index < current || run.status === 'completed');
  });
  if (run.error) log(typeof run.error === 'string' ? run.error : JSON.stringify(run.error));
  if (run.pending_approval?.request_id) {
    state.approvalId = String(run.pending_approval.request_id);
    $('#approval').hidden = false;
  } else if (!state.approvalId) {
    $('#approval').hidden = true;
  }
  renderImages(run);
  if (run.status === 'completed' && run.artifact) {
    $('#result').hidden = false;
    $('#download').href = fileUrl(run.artifact);
    if (run.montage) $('#montage').src = `${fileUrl(run.montage)}&v=${Date.now()}`;
    $('#regeneration').hidden = false;
    if (state.slidesRevision !== Number(run.revision || 1)) loadSlides().catch((error) => log(error.message));
    const proof = $('#regenerationProof');
    if (run.last_regeneration?.status === 'PASS') {
      proof.hidden = false;
      proof.textContent = `${run.last_regeneration.slide_id} を再生成しました。指定外 ${Math.max(0, state.slides.length - 1)}ページは不変検証 PASS。`;
    } else if (run.last_regeneration?.status === 'FAIL') {
      proof.hidden = false;
      proof.textContent = `再生成は適用されませんでした。元のPPTXを維持しています。`;
    }
  } else if (run.status !== 'completed') {
    $('#regenerate').disabled = true;
  }
}

async function loadSlides() {
  const value = await api(`/api/runs/${encodeURIComponent(state.runId)}/slides`);
  state.slides = value.slides || [];
  state.slidesRevision = value.revision;
  $('#revision').textContent = `REV ${value.revision}`;
  const select = $('#slideSelect');
  const previous = select.value;
  select.innerHTML = '';
  for (const slide of state.slides) {
    const option = document.createElement('option');
    option.value = slide.slide_id;
    option.textContent = `${slide.slide_number}. ${slide.title || slide.slide_id}（${slide.recipe}）`;
    option.dataset.informationDensity = slide.policy?.information_density || state.run.information_density || 'medium';
    option.dataset.decorativeness = slide.policy?.decorativeness || state.run.decorativeness || 'medium';
    option.dataset.structuredVisualMode = slide.policy?.structured_visual_mode || state.run.structured_visual_mode || 'native';
    select.appendChild(option);
  }
  if ([...select.options].some((item) => item.value === previous)) select.value = previous;
  syncRegenerationPolicy();
  $('#regenerate').disabled = false;
}

function syncRegenerationPolicy() {
  const option = $('#slideSelect').selectedOptions[0];
  if (!option) return;
  $('#regenInformationDensity').value = option.dataset.informationDensity || 'medium';
  $('#regenDecorativeness').value = option.dataset.decorativeness || 'medium';
  $('#regenStructuredVisualMode').value = option.dataset.structuredVisualMode || 'native';
}

async function refresh() {
  if (!state.runId) return;
  const run = await api(`/api/runs/${encodeURIComponent(state.runId)}`);
  renderRun(run);
  if (['completed', 'failed', 'awaiting_images', 'regeneration_awaiting_images'].includes(run.status)) {
    clearInterval(state.poll);
    state.poll = null;
  }
}

async function upload(role, file) {
  const target = `/api/runs/${encodeURIComponent(state.runId)}/files/${role}?filename=${encodeURIComponent(file.name)}`;
  return api(target, { method: 'PUT', headers: { 'content-type': file.type || 'application/octet-stream' }, body: file });
}

async function start() {
  const template = $('#template').files[0];
  const sources = [...$('#sources').files];
  const designGuide = $('#designGuide').files[0];
  if (!template || !sources.length) throw new Error('テンプレートと原稿を選択してください。');
  $('#start').disabled = true;
  $('#log').textContent = '';
  const run = await api('/api/runs', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      name: $('#name').value,
      instructions: $('#instructions').value,
      compositionMode: $('#compositionMode').value,
      informationDensity: $('#informationDensity').value,
      decorativeness: $('#decorativeness').value,
      structuredVisualMode: $('#structuredVisualMode').value,
      allowShadows: $('#allowShadows').checked,
    }),
  });
  state.runId = run.run_id;
  renderRun(run);
  log('ファイルを登録しています…');
  await upload('template', template);
  for (const source of sources) await upload('source', source);
  if (designGuide) await upload('design-guide', designGuide);
  log('原稿とテンプレートを解析しています…');
  renderRun(await api(`/api/runs/${encodeURIComponent(state.runId)}/prepare`, { method: 'POST' }));
  log('Codex App Serverへ接続しています…');
  await api('/api/codex/connect', { method: 'POST' });
  log('Codexが構成を作成しています…');
  renderRun(await api(`/api/runs/${encodeURIComponent(state.runId)}/plan`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ model: 'gpt-5.6-sol', effort: 'high' }),
  }));
  state.poll = setInterval(() => refresh().catch((error) => log(error.message)), 2000);
}

async function regenerateSlide() {
  if (!state.runId || !state.run || state.run.status !== 'completed') throw new Error('完成済みのPPTXが必要です。');
  const slideId = $('#slideSelect').value;
  if (!slideId) throw new Error('対象ページを選択してください。');
  $('#regenerate').disabled = true;
  $('#regenerationProof').hidden = true;
  log(`${slideId} だけを再生成しています…`);
  const run = await api(`/api/runs/${encodeURIComponent(state.runId)}/regenerate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      slideId,
      expectedRevision: state.run.revision,
      feedback: $('#regenFeedback').value,
      informationDensity: $('#regenInformationDensity').value,
      decorativeness: $('#regenDecorativeness').value,
      structuredVisualMode: $('#regenStructuredVisualMode').value,
      model: 'gpt-5.6-sol',
      effort: 'high',
    }),
  });
  renderRun(run);
  clearInterval(state.poll);
  state.poll = setInterval(() => refresh().catch((error) => log(error.message)), 2000);
}

function renderImages(run) {
  const root = $('#images');
  root.innerHTML = '';
  if (run.status === 'generating_images') {
    const progress = document.createElement('p');
    progress.textContent = '生成画像を自動作成し、QA後にPPTX生成を再開しています。';
    root.appendChild(progress);
    return;
  }
  const requests = (run.asset_requests || []).filter((item) => item.status === 'awaiting_image');
  if (!requests.length) return;
  const title = document.createElement('h3');
  title.textContent = run.image_generation_error ? '自動生成できなかった画像をアップロード' : '生成画像をアップロード';
  root.appendChild(title);
  if (run.image_generation_error) {
    const note = document.createElement('p');
    note.textContent = run.image_generation_error;
    root.appendChild(note);
  }
  for (const request of requests) {
    const row = document.createElement('div');
    row.className = 'asset-row';
    const info = document.createElement('div');
    const strong = document.createElement('strong');
    strong.textContent = request.asset_id;
    const description = document.createElement('p');
    description.textContent = request.prompt || request.purpose || '画像リクエスト';
    info.append(strong, description);
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.png,.jpg,.jpeg,.webp';
    input.onchange = async () => {
      const file = input.files[0];
      if (!file) return;
      input.disabled = true;
      try {
        const url = `/api/runs/${encodeURIComponent(state.runId)}/assets/${encodeURIComponent(request.asset_id)}?filename=${encodeURIComponent(file.name)}`;
        renderRun(await api(url, { method: 'PUT', headers: { 'content-type': file.type || 'application/octet-stream' }, body: file }));
      } catch (error) { log(error.message); input.disabled = false; }
    };
    row.append(info, input);
    root.appendChild(row);
  }
}

$('#start').addEventListener('click', () => start().catch((error) => {
  log(error.message);
  $('#start').disabled = false;
}));

$('#slideSelect').addEventListener('change', syncRegenerationPolicy);
$('#regenerate').addEventListener('click', () => regenerateSlide().catch((error) => {
  log(error.message);
  $('#regenerate').disabled = false;
}));

document.querySelectorAll('#approval button').forEach((button) => {
  button.addEventListener('click', async () => {
    if (!state.approvalId) return;
    await api(`/api/approvals/${state.approvalId}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ decision: button.dataset.decision }),
    });
    state.approvalId = null;
    $('#approval').hidden = true;
  });
});

const events = new EventSource('/api/events');
events.onmessage = (message) => {
  const event = JSON.parse(message.data);
  if (event.type === 'agent_delta' && event.delta) log(event.delta);
  if (event.type === 'core_progress' && event.text) log(event.text);
  if (event.type === 'run_status' && event.runId === state.runId) {
    if (event.state) renderRun(event.state);
    else refresh().catch((error) => log(error.message));
  }
  if (event.type === 'server_request' && (!event.runId || event.runId === state.runId)) {
    state.approvalId = String(event.requestId);
    $('#approval').hidden = false;
  }
};

api('/api/health').then((health) => {
  $('#serverStatus').textContent = health.codex_ready ? 'Codex接続済み' : 'App Server準備完了';
  $('#serverStatus').className = 'badge good';
}).catch((error) => {
  $('#serverStatus').textContent = '接続エラー';
  $('#serverStatus').className = 'badge bad';
  log(error.message);
});
