const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const state = { projectId: null, snapshot: null, selectedSlideId: null, selectedRecipeId: null, codexReady: false, pendingApproval: null, agentText: '' };

async function api(url, options = {}) {
  const res = await fetch(url, { headers: { 'content-type': 'application/json', ...(options.headers || {}) }, ...options });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const err=new Error(data.error || `HTTP ${res.status}`); err.data=data; err.status=res.status; throw err; }
  return data;
}

function setScreen(name) {
  $$('.screen').forEach(el => el.classList.toggle('active', el.id === `screen-${name}`));
  $$('.step').forEach(el => el.classList.toggle('active', el.dataset.screen === name));
}

function setCodexStatus(text, kind = 'muted') {
  const badge = $('#codexBadge');
  badge.textContent = text;
  badge.className = `status ${kind}`;
}

for (const id of ['pptFile', 'manuscriptFile', 'designFile']) {
  $(`#${id}`).addEventListener('change', (e) => {
    const out = document.querySelector(`[data-for="${id}"]`);
    out.textContent = e.target.files?.[0]?.name || '未選択';
  });
}
$('#assetFiles').addEventListener('change', (e) => {
  const out = document.querySelector('[data-for="assetFiles"]');
  const files = [...(e.target.files || [])];
  out.textContent = files.length ? `${files.length}件：${files.slice(0, 2).map(file => file.name).join('、')}${files.length > 2 ? '…' : ''}` : '未選択';
});

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function createProjectFromFiles() {
  const ppt = $('#pptFile').files[0], manuscript = $('#manuscriptFile').files[0], design = $('#designFile').files[0];
  if (!ppt || !manuscript || !design) throw new Error('PPTX・原稿・design.md を選択してください。');
  $('#inputStatus').textContent = 'アップロード中…';
  const name = $('#projectName').value || 'slide-project';
  const assets = [...($('#assetFiles').files || [])];
  const fileRows = [['ppt', ppt], ['manuscript', manuscript], ['design', design], ...assets.map(file => ['asset', file])];
  const files = await Promise.all(fileRows.map(async ([role, file]) => ({ role, filename: file.name, base64: await toBase64(file) })));
  const slideCount = Number.parseInt($('#slideCount').value, 10);
  const preferences = {
    reviewMode: $('#reviewMode').value,
    sourceContinuity: $('#sourceContinuity').value,
    targetSlideCount: Number.isFinite(slideCount) ? slideCount : null,
  };
  const created = await api('/api/projects', { method: 'POST', body: JSON.stringify({ name, projectId: name, files, preferences }) });
  state.projectId = created.projectId;
  $('#inputStatus').textContent = '解析中…';
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/analyze`, { method: 'POST', body: '{}' });
  await refreshSnapshot();
  $('#inputStatus').textContent = '';
  enableWork();
  setScreen('work');
}

async function loadDemo() {
  $('#inputStatus').textContent = 'テストケースを解析中…';
  const data = await api('/api/demo/prepare', { method: 'POST', body: '{}' });
  state.projectId = data.projectId;
  state.snapshot = data.snapshot;
  $('#inputStatus').textContent = '';
  enableWork();
  renderWorkspace();
  setScreen('work');
}

function enableWork() {
  $('[data-screen="work"]').disabled = false;
  $('[data-screen="review"]').disabled = false;
}

async function refreshSnapshot() {
  if (!state.projectId) return;
  state.snapshot = await api(`/api/projects/${encodeURIComponent(state.projectId)}/snapshot`);
  renderWorkspace();
}

function getDeckSlides() { return state.snapshot?.deckPlan?.slides || []; }
function getVisual(slideId) { return state.snapshot?.visualPlan?.slides?.find(x => x.slide_id === slideId); }
function getMatch(slideId) { return state.snapshot?.matches?.slides?.find(x => x.slide_id === slideId); }
function getSourceSlide(sourceId) { return state.snapshot?.sourceSlides?.slides?.find(x => x.id === sourceId); }
function getContinuity(slideId) { return state.snapshot?.continuityPlan?.slides?.find(x => x.slide_id === slideId); }
function getLayoutPlan(slideId) { return state.snapshot?.layoutPlans?.find(x => x.slide_id === slideId); }
function getSlidePlanDetail(slideId) { return state.snapshot?.slidePlanDetails?.find(x => x.slide_id === slideId); }
function getImageRecipes(slideId) { return (state.snapshot?.imageRecipes?.recipes || []).filter(x => x.slide_id === slideId); }
function getGeneratedImages(recipeId) { return (state.snapshot?.generatedImages || []).filter(x => x.recipe_id === recipeId).sort((a,b)=>(b.version||0)-(a.version||0)); }
function selectedImageForRecipe(recipe) {
  const selectedId = recipe?.selected_asset_id || state.snapshot?.imageAssetManifest?.selected_by_recipe?.[recipe?.recipe_id];
  return getGeneratedImages(recipe?.recipe_id).find(x => x.asset_id === selectedId) || null;
}
function activeImageRecipe() {
  const recipes = getImageRecipes(state.selectedSlideId);
  return recipes.find(x => x.recipe_id === state.selectedRecipeId) || recipes[0] || null;
}

const FILL_POLICY_LABELS = {
  auto:'自動判定',
  preserve_source:'元PPTの余白を維持',
  intentional_whitespace:'余白を活かす',
  balanced:'バランスよく配置',
  content_filled:'情報を大きく展開',
  full_bleed:'ビジュアルを全面活用',
};
const LAYOUT_FAMILY_LABELS = {
  grid:'カード／項目グリッド',
  process:'工程・フロー',
  statement:'メッセージ中心',
  two_column:'2カラム',
  photo_text:'写真＋テキスト',
  full_bleed:'全面ビジュアル',
  comparison_matrix:'比較表',
  relationship:'関係図',
};
function defaultFillPolicyFor(s, family='') {
  const role=String(s?.role || '').toLowerCase();
  if (['cover','section','statement','quote','closing','cta','single_kpi'].includes(role) || ['statement','cover','section','closing'].includes(family)) return 'intentional_whitespace';
  if (family === 'full_bleed') return 'full_bleed';
  if (family === 'photo_text' || ['photo','case_study','product','visual','illustration','screenshot'].includes(role)) return 'balanced';
  if (['comparison','process','timeline','table','chart','kpi','three_items','four_items','grid','organization','two_column','relationship'].includes(role) || ['grid','process','two_column','comparison_matrix','relationship','timeline','kpi','chart'].includes(family)) return 'content_filled';
  return 'balanced';
}
function effectiveFillPolicy(s, layoutPlan=null) {
  const detail=getSlidePlanDetail(s?.slide_id);
  const raw=layoutPlan?.fill_policy || layoutPlan?.quality?.fill_policy || detail?.fill_policy;
  const mode=typeof raw === 'string' ? raw : raw?.mode;
  return mode || defaultFillPolicyFor(s, layoutPlan?.family || detail?.family || '');
}
function explicitFillPolicy(s) {
  const raw=getSlidePlanDetail(s?.slide_id)?.fill_policy;
  const mode=typeof raw === 'string' ? raw : raw?.mode;
  return mode || 'auto';
}
function latestDecisionFor(slideId, decisionType=null) {
  const rows=state.snapshot?.decisionTrace || [];
  return [...rows].reverse().find(row => row?.target?.id === slideId && (!decisionType || row.decision_type === decisionType)) || null;
}

function sampleRenderFor(slideId) {
  const selections = state.snapshot?.sampleSelection?.slides || [];
  const idx = selections.findIndex(x => x.slide_id === slideId);
  if (idx < 0) return null;
  const file = state.snapshot?.sampleRenders?.[idx];
  if (!file) return null;
  return `/project/${encodeURIComponent(state.projectId)}/file?path=${encodeURIComponent(`render/output_validation/sample_deck/${file}`)}`;
}

function finalRenderFor(slideId) {
  const slides = getDeckSlides().slice().sort((a,b)=>(a.order||9999)-(b.order||9999));
  const idx=slides.findIndex(x=>x.slide_id===slideId);
  if (idx<0) return null;
  const file=state.snapshot?.finalRenders?.[idx];
  if (!file) return null;
  return `/project/${encodeURIComponent(state.projectId)}/file?path=${encodeURIComponent(`render/output_validation/presentation_final/${file}`)}`;
}

function slideState(slideId) { return state.snapshot?.state?.slides?.[slideId] || {}; }
function slideIsLocked(slideId) { return Object.values(slideState(slideId)).some(v => v === 'LOCKED' || v === 'STALE_LOCKED'); }

function qaIssuesFor(slideId) {
  const finalChecks=(state.snapshot?.finalQa?.checks || []).filter(c => c.slide_id === slideId && c.result === 'fail');
  const sampleChecks=(state.snapshot?.sampleQa?.checks || []).filter(c => c.slide_id === slideId && c.result === 'fail');
  const imageChecks=(state.snapshot?.imageQa?.checks || []).filter(c => c.slide_id === slideId && c.result === 'fail');
  const deckImageChecks=(state.snapshot?.deckImageCoherence?.checks || []).filter(c => c.result === 'fail' && (c.slide_id === slideId || (c.slide_pairs || []).some(pair => pair.includes(slideId))));
  if (state.snapshot?.finalQa) return [...finalChecks, ...imageChecks, ...deckImageChecks];
  return [...sampleChecks, ...imageChecks, ...deckImageChecks];
}

function renderWorkspace() {
  if (!state.snapshot) return;
  $('#projectLabel').textContent = state.snapshot.project?.name || state.projectId;
  const ui = state.snapshot.state?.project?.ui_state || 'structure_review';
  $('#uiStateBadge').textContent = ({ structure_review:'構成確認', sample_review:'代表ページ', page_review:'ページ確認' })[ui] || ui;
  const structureMode = ui === 'structure_review';
  $('#approveStructure').hidden = !structureMode;
  $('#askCodexStructure').hidden = !structureMode;
  $('#planSamples').hidden = structureMode;
  const sampleIds = state.snapshot?.sampleSelection?.slides?.map(x => x.slide_id) || [];
  $('#composeSamples').hidden = structureMode || sampleIds.length === 0 || !sampleIds.every(id => state.snapshot?.slidePlans?.includes(`${id}.json`));
  $('#fixSampleQa').hidden = structureMode || state.snapshot?.sampleQa?.status !== 'fail';
  const samplePassed = state.snapshot?.sampleQa?.status === 'pass';
  $('#planFullDeck').hidden = structureMode || !samplePassed;
  const slides = getDeckSlides();
  const planNames = new Set(state.snapshot?.slidePlans || []);
  const currentPhase = (v) => v === 'APPROVED' || v === 'LOCKED';
  const finalReady = slides.length > 0 && slides.every(s => {
    const ss=slideState(s.slide_id);
    const imageRecipes=getImageRecipes(s.slide_id);
    const imagesReady=!imageRecipes.length || (
      currentPhase(ss.image)
      && imageRecipes.every(recipe => Boolean((recipe?.target?.source_object_id || recipe?.target?.layout_slot_id) && recipe?.target?.bbox) && Boolean(recipe.selected_asset_id))
    );
    return planNames.has(`${s.slide_id}.json`) && imagesReady && ['deck_plan','slide_plan'].every(p => currentPhase(ss[p]));
  });
  $('#exportPptx').disabled = !finalReady;
  if (!state.selectedSlideId && slides.length) state.selectedSlideId = slides[0].slide_id;
  const list = $('#slideList'); list.innerHTML = '';
  for (const s of slides) {
    const btn = document.createElement('button');
    btn.className = `slide-item ${s.slide_id === state.selectedSlideId ? 'active' : ''}`;
    const match = getMatch(s.slide_id)?.selected;
    const srcPage = match?.page_number;
    const thumb = srcPage ? `/project/${encodeURIComponent(state.projectId)}/file?path=${encodeURIComponent(`render/source_renders/SRC-S${String(srcPage).padStart(3,'0')}.png`)}` : '';
    const qaIssues = qaIssuesFor(s.slide_id);
    const locked = slideIsLocked(s.slide_id);
    const imagePending = getImageRecipes(s.slide_id).some(recipe => Boolean((recipe?.target?.source_object_id || recipe?.target?.layout_slot_id) && recipe?.target?.bbox) && !recipe.selected_asset_id);
    const stateMark = locked ? '🔒' : (qaIssues.length || imagePending ? '!' : (s.status === 'APPROVED' ? '✓' : '·'));
    btn.innerHTML = `<span class="thumb">${thumb ? `<img src="${thumb}" alt="" />` : ''}</span><span class="slide-meta"><b>${s.slide_id}</b><span>${escapeHtml(s.primary_message || '')}</span></span><span class="state-dot ${qaIssues.length || imagePending ? 'qa-fail' : ''}">${stateMark}</span>`;
    btn.onclick = () => { state.selectedSlideId = s.slide_id; renderWorkspace(); };
    list.appendChild(btn);
  }
  renderSelectedSlide();
  renderReview();
}

function escapeHtml(s='') { return String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function renderSelectedSlide() {
  const s = getDeckSlides().find(x => x.slide_id === state.selectedSlideId);
  if (!s) return;
  const visual = getVisual(s.slide_id)?.visual_intent || {};
  const match = getMatch(s.slide_id);
  const selected = match?.selected || match?.candidates?.[0];
  const source = selected ? getSourceSlide(selected.source_slide_id) : null;
  $('#slideRole').textContent = String(s.role || 'slide').toUpperCase();
  $('#slideMessage').textContent = s.primary_message || '';
  $('#messageEditor').value = s.primary_message || '';
  const locked = slideIsLocked(s.slide_id);
  $('#messageEditor').disabled = locked;
  $('#lockSlide').textContent = locked ? '固定を解除' : 'このページを固定';
  $('#visualType').value = [visual.selected_type, visual.variant].filter(Boolean).join(' / ') || '未定';
  const layoutPlan = getLayoutPlan(s.slide_id);
  const planDetail = getSlidePlanDetail(s.slide_id);
  const fillMode=effectiveFillPolicy(s,layoutPlan);
  $('#fillPolicy').value=explicitFillPolicy(s);
  $('#fillPolicy').disabled=locked || !planDetail?.family;
  const quality=layoutPlan?.quality;
  const unsupportedFullBleed = fillMode === 'full_bleed' && (layoutPlan?.family || planDetail?.family) !== 'full_bleed';
  $('#fillPolicyNote').textContent = unsupportedFullBleed
    ? 'ビジュアル全面活用はfull_bleed Layout Familyのページでのみ利用できます。'
    : (quality
      ? `実効方針：${FILL_POLICY_LABELS[fillMode] || fillMode}。意図への適合：${quality.status === 'pass' ? '適正' : '要調整'}${quality.intentional_whitespace ? '。空白はメッセージを強調する表現として保持します。' : ''}`
      : (planDetail?.family
        ? `現在の実効方針：${FILL_POLICY_LABELS[fillMode] || fillMode}。変更すると、このページのレイアウト以降だけ再生成対象になります。`
        : (planDetail ? '既存レイアウトを直接流用するページです。レイアウトから見直す場合は自然言語で指示してください。' : 'Slide Plan作成後にページ単位で指定できます。')));
  $('#sourceSlide').value = selected ? `${selected.page_number || ''}ページ / ${selected.recommended_mode || ''}${layoutPlan ? ` / ${LAYOUT_FAMILY_LABELS[layoutPlan.family] || layoutPlan.family}` : ''}` : '未定';
  $('#changeSummary').innerHTML = buildChangeSummary(selected, source) + buildContinuitySummary(s.slide_id);
  $('#rationale').innerHTML = buildRationale(s, visual, match, layoutPlan) + buildContinuityRationale(s.slide_id);
  renderImageSection(s.slide_id, locked);

  const preview = $('#slidePreview');
  const sampleImg = finalRenderFor(s.slide_id) || sampleRenderFor(s.slide_id);
  if (sampleImg) {
    preview.className = 'slide-preview actual-preview';
    const issues = qaIssuesFor(s.slide_id);
    const isFinal=Boolean(finalRenderFor(s.slide_id));
    preview.innerHTML = `<img class="actual-slide-image" src="${sampleImg}" alt="${escapeHtml(s.slide_id)} render" /><span class="render-badge">${isFinal ? 'FINAL RENDER' : 'SAMPLE RENDER'}</span>${issues.length ? `<span class="qa-badge">QA ${issues.length}件</span>` : ''}`;
  } else if (selected?.page_number) {
    const img = `/project/${encodeURIComponent(state.projectId)}/file?path=${encodeURIComponent(`render/source_renders/SRC-S${String(selected.page_number).padStart(3,'0')}.png`)}`;
    preview.className = 'slide-preview';
    preview.innerHTML = `<div class="preview-card"><div><div class="eyebrow">PROPOSED MESSAGE</div><h3>${escapeHtml(s.primary_message || '')}</h3></div><div class="preview-grid"><div class="preview-chip">Visual<br><b>${escapeHtml(visual.selected_type || 'no_visual')}</b></div><div class="preview-chip">Source<br><b>PPT ${selected.page_number}</b></div><div class="preview-chip">Mode<br><b>${escapeHtml(selected.recommended_mode || 'ADAPT')}</b></div></div></div><img class="source-ghost" src="${img}" alt="" style="position:absolute;inset:0;opacity:.06;z-index:0" />`;
    preview.querySelector('.preview-card').style.zIndex = 1;
  } else {
    preview.className = 'slide-preview empty';
    preview.innerHTML = '<div class="preview-placeholder">元PPT候補を選定中</div>';
  }
}

function projectFileUrl(relativePath) {
  if (!relativePath || !state.projectId) return null;
  return `/project/${encodeURIComponent(state.projectId)}/file?path=${encodeURIComponent(relativePath)}`;
}

function imageMetricSummary(asset) {
  const before=asset?.raw_metrics || asset?.process?.grading?.before || {};
  const after=asset?.metrics || asset?.process?.grading?.after || {};
  const parts=[];
  const row=(label,key,digits=2) => {
    if (before[key] == null || after[key] == null) return;
    const a=Number(before[key]).toFixed(digits), b=Number(after[key]).toFixed(digits);
    if (a !== b) parts.push(`${label} ${a}→${b}`);
  };
  row('明度','brightness'); row('彩度','saturation'); row('色温度','warmth'); row('細部','edge_density');
  return parts.join(' / ');
}

function renderImageSection(slideId, locked=false) {
  const section=$('#imageSection');
  const recipes=getImageRecipes(slideId);
  if (!recipes.length) {
    section.hidden=true;
    state.selectedRecipeId=null;
    return;
  }
  section.hidden=false;
  if (!recipes.some(recipe => recipe.recipe_id === state.selectedRecipeId)) state.selectedRecipeId=recipes[0].recipe_id;
  const ready=recipes.filter(recipe => Boolean(recipe.selected_asset_id)).length;
  const status=$('#imageStatus');
  status.textContent = ready === recipes.length ? `${ready}/${recipes.length} 準備済み` : `${ready}/${recipes.length} 要準備`;
  status.className = `status ${ready === recipes.length ? 'ready' : 'warn'}`;
  const art=state.snapshot?.deckArtDirection || {};
  const metrics=art.target_metrics || {};
  const artParts=[];
  if (metrics.brightness != null) artParts.push(`明度 ${Number(metrics.brightness).toFixed(2)}`);
  if (metrics.saturation != null) artParts.push(`彩度 ${Number(metrics.saturation).toFixed(2)}`);
  if (metrics.warmth != null) artParts.push(`色温度 ${Number(metrics.warmth).toFixed(2)}`);
  $('#imageArtDirection').textContent=`デック共通トーン：${artParts.length ? artParts.join(' / ') : '元PPTの画像から自動抽出'}。図解・グラフは画像化せずPowerPoint図形を優先します。`;

  const qaChecks=state.snapshot?.imageQa?.checks || [];
  const list=$('#imageRecipeList');
  list.innerHTML=recipes.map((recipe, index) => {
    const selected=selectedImageForRecipe(recipe);
    const candidates=getGeneratedImages(recipe.recipe_id);
    const active=recipe.recipe_id === state.selectedRecipeId;
    const target=recipe.target || {};
    const bbox=target.bbox || {};
    const qa=qaChecks.filter(check => check.recipe_id === recipe.recipe_id && check.result === 'fail');
    const sourceUrl=projectFileUrl(target.source_media_path);
    const candidateHtml=candidates.slice(0, 8).map(asset => `<button class="image-candidate ${asset.asset_id === selected?.asset_id ? 'selected' : ''}" data-image-action="select" data-recipe-id="${escapeHtml(recipe.recipe_id)}" data-asset-id="${escapeHtml(asset.asset_id)}" title="v${asset.version || 1} / ${escapeHtml(asset.provider || '')}"><img src="${escapeHtml(asset.processedUrl || asset.rawUrl || '')}" alt="" /><span>v${asset.version || 1}</span></button>`).join('');
    const sourcePanel=sourceUrl ? `<figure><img src="${escapeHtml(sourceUrl)}" alt="元PPTの参照画像" /><figcaption>元PPT</figcaption></figure>` : '';
    const selectedPanel=selected?.processedUrl ? `<figure><img src="${escapeHtml(selected.processedUrl)}" alt="調和処理後の画像" /><figcaption>適用画像</figcaption></figure>` : `<div class="image-preview image-empty">画像を指定・生成してください</div>`;
    const treatment=imageMetricSummary(selected);
    const lineage=selected?.lineage?.source_object_id || target.source_object_id || target.layout_slot_id;
    const lineageLabel=target.layout_slot_id && !target.source_object_id ? 'Layout Engine生成枠' : '元PPT';
    return `<article class="image-recipe-card ${active ? 'active' : ''}" data-image-action="activate" data-recipe-id="${escapeHtml(recipe.recipe_id)}">
      <div class="image-recipe-head"><b>画像${index + 1}</b><span>${escapeHtml(recipe.status || 'NEEDS_ASSET')}</span></div>
      <div class="image-compare ${sourceUrl ? '' : 'single'}">${sourcePanel}${selectedPanel}</div>
      <div class="image-meta">${escapeHtml(recipe.medium || 'photo')} / ${bbox.w && bbox.h ? `${Number(bbox.w).toFixed(1)}×${Number(bbox.h).toFixed(1)}in` : '対象枠確認中'} / 余白：${escapeHtml(recipe.composition?.negative_space || 'none')}</div>
      ${lineage ? `<div class="image-lineage">${escapeHtml(lineageLabel)}：${escapeHtml(lineage)} / ${target.layout_slot_id && !target.source_object_id ? 'ページ意図から決定した枠・縦横比・文字用余白を使用' : '写真枠・位置・重なり順を保持'}</div>` : ''}
      ${treatment ? `<div class="image-treatment">調和処理：${escapeHtml(treatment)}</div>` : ''}
      ${candidateHtml ? `<div class="image-candidates">${candidateHtml}</div>` : ''}
      ${qa.length ? `<div class="image-qa-warn">${escapeHtml(qa.map(x => x.check_id).join('、'))}</div>` : ''}
    </article>`;
  }).join('');
  list.onclick=async (event) => {
    const target=event.target.closest('[data-image-action]');
    if (!target) return;
    event.preventDefault();
    event.stopPropagation();
    if (target.dataset.imageAction === 'activate') {
      state.selectedRecipeId=target.dataset.recipeId;
      renderImageSection(slideId, locked);
      return;
    }
    if (target.dataset.imageAction === 'select') {
      if (locked) return alert('固定中のページです。固定を解除してから画像を変更してください。');
      await runImageAction('select', { recipeId:target.dataset.recipeId, assetId:target.dataset.assetId });
    }
  };
  const active=activeImageRecipe();
  const hasActive=Boolean(active);
  $('#imagePrompt').value=active?.prompt_seed || active?.message || '';
  $('#imageNegativeSpace').value=active?.composition?.negative_space || 'none';
  for (const id of ['imagePrompt','imageNegativeSpace','saveImageRecipe','replacementImageFile','uploadReplacementImage','autoSelectImage','generateImageOpenAI']) {
    const el=$(`#${id}`); if (el) el.disabled=locked || !hasActive;
  }
}

async function runImageAction(action, payload={}) {
  if (!state.projectId) return;
  const recipe=payload.recipeId ? getImageRecipes(state.selectedSlideId).find(x => x.recipe_id === payload.recipeId) : activeImageRecipe();
  if (!recipe && action !== 'validate') throw new Error('画像レシピがありません。');
  const status=$('#imageStatus');
  status.textContent='処理中…'; status.className='status muted';
  const body={ action, recipeId:recipe?.recipe_id, ...payload };
  const data=await api(`/api/projects/${encodeURIComponent(state.projectId)}/image-action`, { method:'POST', body:JSON.stringify(body) });
  state.snapshot=data.snapshot || state.snapshot;
  renderWorkspace();
  return data;
}

function buildChangeSummary(selected, source) {
  if (!selected) return '候補未選定';
  const mode = selected.recommended_mode || 'ADAPT';
  const assets = (state.snapshot?.sourceAssets?.assets || []).filter(a => a.source_slide_id === selected.source_slide_id);
  const count = (kind) => assets.filter(a => a.classification === kind).length;
  const review = assets.filter(a => a.status === 'REVIEW_REQUIRED' || a.classification === 'unknown').length;
  const rows = [
    `ブランド装飾：${count('template_chrome')}件を保持`,
    `本文画像：${count('content_visual')}件を差し替え候補`,
    `フレーム：${count('container_or_frame')}件を外形保持`,
  ];
  const uncertain = assets.find(a => a.status === 'REVIEW_REQUIRED' || a.classification === 'unknown');
  if (review) {
    rows.push(`<span class="warn-text">画像判定：${review}件は要確認</span>`);
    if (uncertain) rows.push(`<div class="asset-review"><small>${escapeHtml(uncertain.source_object_id || uncertain.id)}</small><div class="mini-actions"><button class="asset-choice" data-asset-id="${escapeHtml(uncertain.id)}" data-classification="template_chrome">装飾として残す</button><button class="asset-choice" data-asset-id="${escapeHtml(uncertain.id)}" data-classification="content_visual">内容画像として差し替え</button></div></div>`);
  }
  return `<b>${mode}</b><br>${rows.join('<br>')}`;
}
function buildContinuitySummary(slideId) {
  const p=getContinuity(slideId);
  if (!p) return '';
  const src=p.source_lineage?.[0]?.source_slide_id || 'deck';
  const inherited=[...(p.inherited?.macro||[]),...(p.inherited?.middle||[]),...(p.inherited?.micro||[])];
  return `<div class="continuity-summary"><br><b>元PPTとの連続性</b><br>${escapeHtml(src)}を中心に再構成<br>継承要素：${inherited.length}件</div>`;
}

function buildContinuityRationale(slideId) {
  const p=getContinuity(slideId);
  if (!p) return '';
  const fmt=(xs)=> (xs||[]).map(x=>`・${escapeHtml(String(x))}`).join('<br>') || '—';
  return `<br><br><b>継承したデザインDNA</b><br><small>Macro</small><br>${fmt(p.inherited?.macro)}<br><small>Component</small><br>${fmt(p.inherited?.middle)}<br><small>Micro</small><br>${fmt(p.inherited?.micro)}<br><small>変更</small><br>${fmt(p.changed)}`;
}

function buildRationale(s, visual, match, layoutPlan = null) {
  const cands = match?.candidates || [];
  const candidateHtml = cands.map((c,i) => `${i+1}. 元PPT ${c.page_number} — ${Math.round((c.total_score||0)*100)}%`).join('<br>');
  const mode=effectiveFillPolicy(s,layoutPlan);
  const detail=getSlidePlanDetail(s?.slide_id);
  const policy=layoutPlan?.fill_policy || layoutPlan?.quality?.fill_policy || detail?.fill_policy || null;
  const reasons=(typeof policy === 'object' && Array.isArray(policy?.reason) ? policy.reason : []).filter(Boolean);
  const reasonHtml=reasons.length ? `<br><b>方針を選んだ理由</b><br>${reasons.map(x=>`・${escapeHtml(String(x))}`).join('<br>')}` : '';
  const decision=latestDecisionFor(s?.slide_id,'effective_fill_policy');
  const decisionHtml=decision ? `<br><small>判断記録：${escapeHtml(decision.origin || 'system')} / confidence ${Math.round((decision.confidence || 0)*100)}%</small>` : '';
  const imageSlots=layoutPlan?.image_slots || [];
  const imageSlotHtml=imageSlots.length ? `<br>画像枠：${imageSlots.map(slot => `${escapeHtml(slot.slot_id || '')} / ${Number(slot.aspect_ratio || 0).toFixed(2)}:1`).join('、')}` : '';
  const geometryHint=layoutPlan?.geometry?.image_position ? `<br>画像位置：${escapeHtml(layoutPlan.geometry.image_position)}` : (layoutPlan?.geometry?.overlay_position ? `<br>文字パネル：${escapeHtml(layoutPlan.geometry.overlay_position)}` : '');
  const lineage=layoutPlan?.image_lineage;
  const imageLineageHtml=lineage ? `<br><b>画像とテンプレートの接続</b><br>Recipe：${escapeHtml(lineage.recipe_id || '—')}<br>文字側：${escapeHtml(lineage.resolved_text_side || '自動')}<br>元写真枠：${lineage.source_frame_reused ? '再利用' : '新規枠'}${lineage.negative_space && lineage.negative_space !== 'none' ? `<br>画像内の余白：${escapeHtml(lineage.negative_space)}` : ''}` : '';
  const fit = layoutPlan?.quality ? `<br><br><b>Layout Engine</b><br>方式：${escapeHtml(LAYOUT_FAMILY_LABELS[layoutPlan.family] || layoutPlan.family || '')}<br>密度：${escapeHtml(layoutPlan.density || '')}<br>レイアウト方針：${escapeHtml(FILL_POLICY_LABELS[mode] || mode)}<br>意図への適合：${Math.round((layoutPlan.quality.score || 0)*100)}% / ${layoutPlan.quality.status === 'pass' ? '適正' : '要調整'}${layoutPlan.quality.intentional_whitespace ? '<br><span>余白はメッセージを強調するため意図的に保持しています。</span>' : ''}${imageSlotHtml}${geometryHint}${imageLineageHtml}${reasonHtml}${decisionHtml}` : `${reasonHtml}${decisionHtml}`;
  return `役割：${escapeHtml(s.role || '')}<br>表現：${escapeHtml(visual.selected_type || '')}<br><br><b>元PPT候補</b><br>${candidateHtml || '—'}${fit}<br><br><span>重要な判断はDecision Traceにも追記され、再実行範囲と一緒に保持されます。</span>`;
}

function renderReview() {
  const grid = $('#reviewGrid'); if (!grid) return;
  grid.innerHTML = '';
  for (const s of getDeckSlides()) {
    const match = getMatch(s.slide_id)?.selected;
    const srcPage = match?.page_number;
    const card = document.createElement('div'); card.className = 'review-card';
    const img = finalRenderFor(s.slide_id) || sampleRenderFor(s.slide_id) || (srcPage ? `/project/${encodeURIComponent(state.projectId)}/file?path=${encodeURIComponent(`render/source_renders/SRC-S${String(srcPage).padStart(3,'0')}.png`)}` : '');
    const issues=qaIssuesFor(s.slide_id);
    card.innerHTML = `<div class="thumb">${img ? `<img src="${img}" alt="" />` : ''}</div><b>${s.slide_id} ${issues.length ? '!' : (s.status === 'APPROVED' ? '✓' : '')}</b><span>${escapeHtml(s.primary_message || '')}</span>${issues.length ? `<small class="warn-text">QA: ${escapeHtml(issues.map(x=>x.check_id).join(', '))}</small>` : ''}`;
    card.onclick = () => { state.selectedSlideId=s.slide_id; setScreen('work'); renderWorkspace(); };
    grid.appendChild(card);
  }
}

function syncEffortPicker(models) {
  const selected = models.find(m => m.model === $('#modelSelect').value) || models[0];
  const efforts = selected?.supportedReasoningEfforts?.map(x => x.reasoningEffort) || ['high','medium','low'];
  $('#effortSelect').innerHTML = efforts.map(x => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join('');
  const preferred = efforts.includes('high') ? 'high' : (selected?.defaultReasoningEffort || efforts[0]);
  if (preferred) $('#effortSelect').value = preferred;
}

async function connectCodex() {
  setCodexStatus('接続中…');
  try {
    const data = await api('/api/codex/connect', { method:'POST', body:'{}' });
    if (data.needsAuth) {
      state.codexReady = false;
      setCodexStatus('ログイン必要', 'warn');
      const login = await api('/api/codex/login', { method:'POST', body:JSON.stringify({ mode:'browser' }) });
      if (login.authUrl) window.open(login.authUrl, '_blank', 'noopener');
      alert('ChatGPTのログイン画面を開きました。完了後、この画面に戻ってください。');
      return data;
    }
    state.codexReady = true;
    const account = data.account?.account;
    setCodexStatus(account?.planType ? `接続済み / ${account.planType}` : '接続済み', 'ready');
    const models = data.models?.data || [];
    if (models.length) {
      $('#modelSelect').innerHTML = models.map(m => `<option value="${m.model}">${escapeHtml(m.displayName || m.model)}</option>`).join('');
      const sol = models.find(m => m.model === 'gpt-5.6-sol'); if (sol) $('#modelSelect').value = sol.model;
      syncEffortPicker(models);
      $('#modelSelect').onchange = () => syncEffortPicker(models);
    }
    return data;
  } catch (e) { setCodexStatus('Codex未検出', 'warn'); alert(e.message); throw e; }
}

async function askCodexStructure() {
  if (!state.projectId) return;
  if (!state.codexReady) await connectCodex();
  if (!state.codexReady) return;
  state.agentText = '';
  $('#agentStream').hidden = false; $('#agentStream').textContent = 'Codex: 構成を精査中…\n';
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/codex/structure`, { method:'POST', body:JSON.stringify({ model:$('#modelSelect').value, effort:$('#effortSelect').value || 'high' }) });
}

async function sendInstruction(textOverride) {
  const text = textOverride || $('#instruction').value.trim();
  if (!text || !state.projectId) return;
  if (!state.codexReady) await connectCodex();
  if (!state.codexReady) return;
  $('#agentStream').hidden = false; $('#agentStream').textContent = 'Codex: '; state.agentText = '';
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/codex/message`, { method:'POST', body:JSON.stringify({ text, slideId: state.selectedSlideId, model:$('#modelSelect').value, effort:$('#effortSelect').value || 'high' }) });
  $('#instruction').value = '';
}



async function planSamples() {
  if (!state.projectId) return;
  if (!state.codexReady) await connectCodex();
  if (!state.codexReady) return;
  state.agentText = '';
  $('#agentStream').hidden = false; $('#agentStream').textContent = 'Codex: 代表ページのSlide Planを作成中…\n';
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/codex/samples`, { method:'POST', body:JSON.stringify({ model:$('#modelSelect').value, effort:$('#effortSelect').value || 'high' }) });
}

async function composeSamples() {
  if (!state.projectId) return;
  const slides = state.snapshot?.sampleSelection?.slides?.map(x => x.slide_id) || [];
  if (!slides.length) throw new Error('sample_selection.json がありません');
  const data = await api(`/api/projects/${encodeURIComponent(state.projectId)}/compose`, { method:'POST', body:JSON.stringify({ slides, output:'sample_deck.pptx' }) });
  if (data.result?.errors) alert(`合成しましたが mutation error が ${data.result.errors} 件あります。compose reportを確認してください。`);
  if (data.qa?.status === 'fail') {
    alert(`QAでblocking errorが ${data.qa.blocking_count || 0} 件あります。PPTXは自動ダウンロードせず、QAレポートを確認してください。`);
    await refreshSnapshot();
    return;
  }
  if (data.download) window.location.href = data.download;
}

async function fixSampleQa() {
  if (!state.projectId) return;
  if (!state.codexReady) await connectCodex();
  if (!state.codexReady) return;
  state.agentText = '';
  $('#agentStream').hidden = false; $('#agentStream').textContent = 'Codex: QA問題のあるSlide Planだけ修正中…\n';
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/codex/fix-qa`, { method:'POST', body:JSON.stringify({ model:$('#modelSelect').value, effort:$('#effortSelect').value || 'high' }) });
}

async function planFullDeck() {
  if (!state.projectId) return;
  if (!state.codexReady) await connectCodex();
  if (!state.codexReady) return;
  state.agentText = '';
  $('#agentStream').hidden = false; $('#agentStream').textContent = 'Codex: 代表ページのルールを基準に残り全ページを設計中…\n';
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/codex/full-deck`, { method:'POST', body:JSON.stringify({ model:$('#modelSelect').value, effort:$('#effortSelect').value || 'high' }) });
}

async function exportFinal() {
  if (!state.projectId) return;
  try {
    const data = await api(`/api/projects/${encodeURIComponent(state.projectId)}/export-final`, { method:'POST', body:'{}' });
    const warnings = data.harmony?.warning_count || 0;
    if (warnings) alert(`最終PPTXはblocking QA 0で生成されました。Deck Harmonyにwarningが ${warnings} 件あります。`);
    await refreshSnapshot();
    if (data.download) window.location.href = data.download;
  } catch (e) {
    await refreshSnapshot();
    if (e.data?.qa) setScreen('review');
    throw e;
  }
}

async function exportSkeleton() {
  if (!state.projectId) return;
  const data = await api(`/api/projects/${encodeURIComponent(state.projectId)}/build-skeleton`, { method:'POST', body:'{}' });
  if (data.download) window.location.href = data.download;
}

function subscribeEvents() {
  const es = new EventSource('/api/events');
  es.onmessage = async (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'codex_status' && data.status === 'ready') { setCodexStatus('Codex起動済み','ready'); }
    if (data.type === 'codex_notification' && (data.method === 'account/login/completed' || data.method === 'account/updated')) {
      setTimeout(() => connectCodex().catch(()=>{}), 300);
    }
    if (data.type === 'agent_delta') {
      const delta = data.delta || data.text || '';
      state.agentText += delta;
      $('#agentStream').hidden = false;
      $('#agentStream').textContent = state.agentText;
      $('#agentStream').scrollTop = $('#agentStream').scrollHeight;
    }
    if (data.type === 'turn_completed') {
      await refreshSnapshot();
      setTimeout(() => { $('#agentStream').hidden = true; }, 1800);
    }
    if (data.type === 'server_request') showApproval(data);
  };
}

function showApproval(data) {
  state.pendingApproval = data;
  $('#approvalDetail').textContent = `${data.method}\n\n${JSON.stringify(data.params, null, 2)}`;
  $('#approvalModal').hidden = false;
}
async function answerApproval(decision) {
  if (!state.pendingApproval) return;
  await api(`/api/approvals/${state.pendingApproval.requestId}`, { method:'POST', body:JSON.stringify({ decision }) });
  state.pendingApproval = null; $('#approvalModal').hidden = true;
}

$('#createProject').onclick = () => createProjectFromFiles().catch(e => { $('#inputStatus').textContent=''; alert(e.message); });
$('#loadDemo').onclick = () => loadDemo().catch(e => { $('#inputStatus').textContent=''; alert(e.message); });
$('#connectCodex').onclick = connectCodex;
$('#askCodexStructure').onclick = () => askCodexStructure().catch(e => alert(e.message));
$('#planSamples').onclick = () => planSamples().catch(e => alert(e.message));
$('#composeSamples').onclick = () => composeSamples().catch(e => alert(e.message));
$('#fixSampleQa').onclick = () => fixSampleQa().catch(e => alert(e.message));
$('#planFullDeck').onclick = () => planFullDeck().catch(e => alert(e.message));
$('#sendInstruction').onclick = () => sendInstruction().catch(e => alert(e.message));
$('#alternateSlide').onclick = () => sendInstruction('このページだけ別案を作ってください。Primary Messageと原稿上の事実は変えず、Visual Type・元PPT候補・Layout Variant・表示文の範囲で別案にしてください。').catch(e=>alert(e.message));
$('#acceptSlide').onclick = async () => {
  if(!state.projectId||!state.selectedSlideId)return;
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/slide-action`,{method:'POST',body:JSON.stringify({action:'approve',slideId:state.selectedSlideId})});
  await refreshSnapshot();
};
$('#lockSlide').onclick = async () => {
  if(!state.projectId||!state.selectedSlideId)return;
  const action = slideIsLocked(state.selectedSlideId) ? 'unlock' : 'lock';
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/slide-action`,{method:'POST',body:JSON.stringify({action,slideId:state.selectedSlideId})});
  await refreshSnapshot();
};
$('#uploadReplacementImage').onclick = async () => {
  try {
    const file=$('#replacementImageFile').files?.[0];
    if (!file) return alert('画像ファイルを選択してください。');
    const recipe=activeImageRecipe();
    await runImageAction('upload', { recipeId:recipe?.recipe_id, filename:file.name, base64:await toBase64(file) });
    $('#replacementImageFile').value='';
  } catch (e) { alert(e.message); }
};
$('#saveImageRecipe').onclick = async () => {
  try {
    const recipe=activeImageRecipe();
    if (!recipe) return;
    await runImageAction('update-recipe', {
      recipeId:recipe.recipe_id,
      prompt:$('#imagePrompt').value.trim(),
      negativeSpace:$('#imageNegativeSpace').value,
    });
  } catch (e) { alert(e.message); }
};
$('#autoSelectImage').onclick = () => runImageAction('generate', { provider:'auto' }).catch(e => alert(e.message));
$('#generateImageOpenAI').onclick = () => runImageAction('generate', { provider:'openai', quality:'medium', model:'gpt-image-2' }).catch(e => alert(e.message));

$('#fillPolicy').addEventListener('change', async () => {
  if(!state.projectId||!state.selectedSlideId)return;
  if ($('#fillPolicy').value === 'full_bleed') {
    const family=getSlidePlanDetail(state.selectedSlideId)?.family;
    if (family !== 'full_bleed') {
      alert('ビジュアル全面活用はfull_bleed Layout Familyのページでのみ利用できます。');
      renderSelectedSlide();
      return;
    }
  }
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/slide-action`,{
    method:'POST',
    body:JSON.stringify({action:'fill-policy',slideId:state.selectedSlideId,value:$('#fillPolicy').value})
  });
  await refreshSnapshot();
});
$('#messageEditor').addEventListener('change', async () => {
  if(!state.projectId||!state.selectedSlideId)return;
  await api(`/api/projects/${encodeURIComponent(state.projectId)}/slide-action`,{method:'POST',body:JSON.stringify({action:'message',slideId:state.selectedSlideId,value:$('#messageEditor').value})});
  await refreshSnapshot();
});
$('#approveStructure').onclick = async () => { if(!state.projectId)return; await api(`/api/projects/${encodeURIComponent(state.projectId)}/approve-structure`,{method:'POST',body:'{}'}); await refreshSnapshot(); alert('構成を承認しました。次は代表ページ試作へ進めます。'); };
$('#exportSkeleton').onclick = () => exportSkeleton().catch(e=>alert(e.message));
$('#exportPptx').onclick = () => exportFinal().catch(e=>alert(e.message));
$('#approvalAccept').onclick = () => answerApproval('accept');
$('#approvalDecline').onclick = () => answerApproval('decline');
$('#toggleChanges').onclick = () => $('#changeSummary').classList.toggle('expanded');

$('#changeSummary').addEventListener('click', async (event) => {
  const btn = event.target.closest('.asset-choice');
  if (!btn || !state.projectId) return;
  btn.disabled = true;
  try {
    await api(`/api/projects/${encodeURIComponent(state.projectId)}/asset-action`, {
      method:'POST',
      body:JSON.stringify({ assetId:btn.dataset.assetId, classification:btn.dataset.classification }),
    });
    await refreshSnapshot();
  } catch (e) { alert(e.message); btn.disabled = false; }
});
$$('.step').forEach(b => b.onclick = () => { if(!b.disabled) setScreen(b.dataset.screen); });

subscribeEvents();
