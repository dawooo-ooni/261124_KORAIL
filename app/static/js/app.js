/* 점심메뉴 추천기 — 메인 화면 스크립트
   원본 아티팩트의 화면·흐름을 유지하고, 메뉴 데이터·추천 로직·저장은 서버 API(/api/...)로 옮겼다. */
(function(){
'use strict';

/* ---------- 공통 ---------- */
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const won = p => Number(p).toLocaleString('ko-KR')+'원';
const TASTE_LABEL = {'매운맛':'매운맛','담백':'담백한 맛','기름진':'기름진 맛','가벼움':'가벼운 식사','든든':'든든한 식사'};
const DEFAULT_F = () => ({cat:[],taste:[],like:[],avoid:[],soup:'any',budget:'all',weather:'',sit:[]});
const reduceMotion = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const IDLE_SPOT = `<div class="big">🎲</div><div><b>랜덤 뽑기</b>를 누르면 지금 조건에 맞는 메뉴 하나를 뽑아 드려요.</div><div style="font-size:13px">조건을 하나도 고르지 않아도 바로 뽑을 수 있어요.</div>`;

const state = {
  groups: [],
  f: DEFAULT_F(),
  list: null,                        // /api/recommendations 응답
  cands: {items:[], best:{}},        // /api/candidates 응답
  history: [],
  current: null,                     // 스포트라이트 메뉴 {menu, match_pct, reason, recent}
  rolling: false
};

class ApiError extends Error {
  constructor(code, message, status){ super(message); this.code = code; this.status = status; }
}
async function api(method, url, body){
  const opt = {method, headers:{'Accept':'application/json'}, credentials:'same-origin'};
  if(body !== undefined){ opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(url, opt); }
  catch(e){ throw new ApiError('NETWORK', '서버에 연결할 수 없어요. 서버가 켜져 있는지 확인해 주세요.', 0); }
  let data = null;
  try { data = await res.json(); } catch(e) { /* 본문 없음 */ }
  if(!res.ok){
    const er = (data && data.error) || {};
    throw new ApiError(er.code || 'ERROR', er.message || '요청을 처리하지 못했어요.', res.status);
  }
  return data;
}
function fail(e){
  if(window.console) console.error(e);
  toast(e && e.message ? e.message : '문제가 생겼어요. 다시 시도해 주세요.');
}
let toastT;
function toast(msg){
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 2200);
}
function parseDT(iso){        // "2026-11-24T12:30:05" (서울 시각) → 부품
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(iso || '') || [];
  return {y:+m[1], mo:+m[2], d:+m[3], h:+(m[4]||0), mi:+(m[5]||0)};
}
const pad2 = n => String(n).padStart(2,'0');
const candIds = () => state.cands.items.map(x => x.menu.id);

/* ---------- 조건 패널 ---------- */
function renderFilters(){
  const box = $('#filters'); box.innerHTML = '';
  state.groups.forEach(g => {
    const sec = document.createElement('div'); sec.className = 'group';
    const h = document.createElement('h3'); h.textContent = g.title; sec.appendChild(h);
    const chips = document.createElement('div'); chips.className = 'chips';
    if(g.all){
      chips.appendChild(chip('전체', state.f[g.key].length === 0, () => { state.f[g.key] = []; changed(); }, g.cls));
    }
    g.opts.forEach(([val, label]) => {
      const on = g.type === 'multi' ? state.f[g.key].includes(val) : state.f[g.key] === val;
      chips.appendChild(chip(label, on, () => {
        if(g.type === 'multi'){
          const arr = state.f[g.key]; const i = arr.indexOf(val);
          if(i >= 0) arr.splice(i, 1); else arr.push(val);
        } else {
          state.f[g.key] = (g.toggle && state.f[g.key] === val) ? '' : val;
        }
        changed();
      }, g.cls));
    });
    sec.appendChild(chips); box.appendChild(sec);
  });
}
function chip(label, on, fn, cls){
  const b = document.createElement('button'); b.type = 'button';
  b.className = 'chip' + (cls ? ' ' + cls : '') + (on ? ' on' : ''); b.textContent = label;
  b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.onclick = fn; return b;
}

// 조건을 바꿀 때마다 300ms 디바운스 후 서버에 저장하고 추천·후보 비교를 갱신
let saveT = null;
function changed(){
  renderFilters();
  clearTimeout(saveT);
  saveT = setTimeout(async () => {
    try {
      await api('PUT', '/api/preferences', {filters: state.f});
      await Promise.all([loadList(), loadCands()]);
    } catch(e){ fail(e); }
  }, 300);
}

/* ---------- 오늘의 추천 ---------- */
function renderToday(data){
  const box = $('#today');
  const dt = parseDT(data && data.date);
  const days = ['일','월','화','수','목','금','토'];
  const dow = days[new Date(dt.y, dt.mo - 1, dt.d).getDay()];
  const m = data && data.menu;
  if(!m){
    box.innerHTML = `<div class="emo">🍱</div><div class="body"><div class="lbl">🍱 오늘의 추천 메뉴</div><div class="name">메뉴 준비 중</div><p class="desc">관리자 화면에서 메뉴를 등록해 주세요.</p></div>`;
    return;
  }
  const inC = candIds().includes(m.id);
  box.innerHTML = `
    <div class="emo">${esc(m.emoji)}</div>
    <div class="body">
      <div class="lbl">🍱 오늘의 추천 메뉴 · ${dt.mo}월 ${dt.d}일 (${dow})</div>
      <div class="name">${esc(m.name)}</div>
      <p class="desc">${esc(m.description)}</p>
      <div class="row">
        <button class="btn sm light" type="button" data-add="${m.id}" ${inC ? 'disabled' : ''}>${inC ? '✓ 후보에 있음' : '＋ 후보에 담기'}</button>
        <span class="meta">${esc(m.category)} · ${won(m.price)} · 오늘 하루 동안 그대로예요</span>
      </div>
    </div>`;
}
let todayData = null;

/* ---------- 추천 목록 ---------- */
function tagsHTML(m, recent){
  let h = (m.tastes || []).map(t => `<span class="tag${t === '매운맛' ? ' hot' : ''}">${esc(TASTE_LABEL[t] || t)}</span>`).join('');
  if(m.has_soup) h += '<span class="tag">국물</span>';
  if(recent) h += '<span class="tag recent">최근에 먹었어요</span>';
  return h;
}
let listSeq = 0;
async function loadList(){
  const seq = ++listSeq;
  const body = {filters: state.f};
  if(state.current && !state.rolling) body.focus_id = state.current.menu.id;
  const data = await api('POST', '/api/recommendations', body);
  if(seq !== listSeq) return;               // 더 최근 요청이 있으면 무시
  state.list = data;
  if(data.focus && state.current && !state.rolling && data.focus.menu.id === state.current.menu.id){
    state.current = data.focus; renderSpot(false);
  }
  renderList();
}
function renderList(){
  const data = state.list; if(!data) return;
  const {items, relaxed, total} = data;
  $('#notice').innerHTML = relaxed ? `<div class="notice">😅 지금 조건(음식 종류·예산·피하고 싶은 것)에 딱 맞는 메뉴가 없어요. <b>조건을 조금 완화해 보세요.</b> 아래는 조건에 가장 가까운 메뉴예요.</div>` : '';
  const shown = items.slice(0, 8);
  $('#listSub').textContent = relaxed ? '가장 가까운 메뉴 3개' : `조건에 맞는 메뉴 ${total}개 중 상위 ${shown.length}개`;
  $('#poolHint').textContent = relaxed ? '조건을 완화하면 더 많은 메뉴에서 뽑을 수 있어요' : `지금 조건에서 ${total}개 메뉴 중 뽑아요`;
  const ids = candIds();
  if(!shown.length){ $('#cards').innerHTML = '<div class="empty-box">추천할 메뉴가 없어요. 관리자 화면에서 메뉴를 확인해 주세요.</div>'; return; }
  $('#cards').innerHTML = shown.map((x, idx) => {
    const m = x.menu; const inC = ids.includes(m.id);
    return `<article class="mcard">
      <div class="head"><span class="emo">${esc(m.emoji)}</span>
        <div><div class="name">${esc(m.name)}</div><div class="meta">${esc(m.category)} · ${won(m.price)} · 약 ${m.time_min}분</div></div>
        ${idx < 3 && !relaxed ? `<span class="rank">TOP ${idx + 1}</span>` : ''}
      </div>
      <div class="tags">${tagsHTML(m, x.recent)}</div>
      <p class="desc">${esc(m.description)}</p>
      <div class="reason">💡 ${esc(x.reason)}</div>
      <div class="foot">
        <span class="score">${x.match_pct === null ? '' : '조건 일치 ' + x.match_pct + '%'}</span>
        <button class="btn sm ${inC ? 'ghost' : 'primary'}" type="button" data-add="${m.id}" ${inC ? 'disabled' : ''}>${inC ? '✓ 후보에 있음' : '＋ 후보에 담기'}</button>
      </div>
    </article>`;
  }).join('');
}

/* ---------- 랜덤 뽑기 (서버 추첨 → 클라이언트 슬롯 애니메이션) ---------- */
async function draw(excludeCurrent){
  if(state.rolling) return;
  state.rolling = true; setButtons();
  let data;
  try {
    data = await api('POST', '/api/draw', {
      filters: state.f,
      exclude_id: excludeCurrent && state.current ? state.current.menu.id : null
    });
  } catch(e){ state.rolling = false; setButtons(); return fail(e); }
  const pick = {menu: data.menu, match_pct: data.match_pct, reason: data.reason, recent: data.recent};
  const names = data.roll || [];
  const finish = () => { state.rolling = false; state.current = pick; renderSpot(true); };
  if(reduceMotion() || names.length < 2){ finish(); return; }
  const spot = $('#spot'); spot.className = 'spot rolling';
  spot.innerHTML = `<div class="emo" id="rE">🎲</div><div class="body"><div class="name" id="rN">두구두구…</div><div class="meta">메뉴를 고르는 중이에요</div></div>`;
  const rE = $('#rE'), rN = $('#rN');
  let delay = 45, elapsed = 0;
  (function tick(){
    const r = names[Math.floor(Math.random() * names.length)];
    rE.textContent = r.emoji; rN.textContent = r.name;
    elapsed += delay; delay *= 1.13;
    if(elapsed < 1500) setTimeout(tick, delay);
    else setTimeout(finish, 220);
  })();
}
function renderSpot(animate){
  const cur = state.current;
  const spot = $('#spot');
  if(!cur){ spot.className = 'spot idle'; spot.innerHTML = IDLE_SPOT; setButtons(); return; }
  const m = cur.menu; const inC = candIds().includes(m.id);
  spot.className = 'spot' + (animate ? ' pop' : '');
  spot.innerHTML = `
    <div class="emo">${esc(m.emoji)}</div>
    <div class="body">
      <div class="meta">🎯 이번에 뽑힌 메뉴</div>
      <div class="name">${esc(m.name)}</div>
      <div class="meta">${esc(m.category)} · ${won(m.price)} · 약 ${m.time_min}분 ${cur.match_pct === null ? '' : '· 조건 일치 ' + cur.match_pct + '%'}</div>
      <div class="tags">${tagsHTML(m, cur.recent)}</div>
      <div class="reason">📝 ${esc(m.description)}<br>💡 <b>추천 사유</b> · ${esc(cur.reason)}</div>
      <div class="row">
        <button class="btn sm ${inC ? 'ghost' : 'primary'}" type="button" data-add="${m.id}" ${inC ? 'disabled' : ''}>${inC ? '✓ 후보에 있음' : '＋ 후보에 담기'}</button>
        <button class="btn sm ghost" type="button" data-decide="${m.id}">✅ 바로 결정</button>
      </div>
    </div>`;
  setButtons();
}
function setButtons(){
  $('#drawBtn').disabled = state.rolling;
  $('#redrawBtn').disabled = state.rolling || !state.current;
}

/* ---------- 후보 비교 ---------- */
async function loadCands(){
  state.cands = await api('GET', '/api/candidates');
  renderCompare();
}
async function addCand(id){
  try {
    state.cands = await api('POST', '/api/candidates', {menu_id: +id});
    const it = state.cands.items.find(x => x.menu.id === +id);
    toast((it ? it.menu.name : '메뉴') + '을(를) 후보에 담았어요');
    refreshAll();
  } catch(e){ fail(e); }
}
async function removeCand(id){
  try { state.cands = await api('DELETE', '/api/candidates/' + (+id)); refreshAll(); }
  catch(e){ fail(e); }
}
function renderCompare(){
  const box = $('#compare');
  const items = state.cands.items || [];
  $('#candSub').textContent = `${items.length}/3 · 후보 중 하나를 골라 결정하세요`;
  if(!items.length){
    box.innerHTML = `<div class="empty-box">🧺 마음에 드는 메뉴를 <b>‘후보에 담기’</b>로 최대 3개까지 모아 나란히 비교해 보세요.</div>`;
    return;
  }
  const best = state.cands.best || {};
  const isBest = (key, id) => (best[key] || []).includes(id);
  const B = '<span class="best">최고</span>';
  const rows = [
    ['메뉴', items.map(x => `<div class="ch"><span class="e">${esc(x.menu.emoji)}</span><span class="n">${esc(x.menu.name)}</span><span class="tag">${esc(x.menu.category)}</span></div>`), true],
    ['가격', items.map(x => won(x.menu.price) + (isBest('price', x.menu.id) ? B : ''))],
    ['맛', items.map(x => esc((x.menu.tastes || []).map(t => TASTE_LABEL[t] || t).join(', ')) + (x.menu.has_soup ? ' · 국물' : ''))],
    ['포만감', items.map(x => `<span class="dots">${'●'.repeat(x.menu.fullness)}<i>${'●'.repeat(5 - x.menu.fullness)}</i></span>` + (isBest('fullness', x.menu.id) ? B : ''))],
    ['소요 시간', items.map(x => `약 ${x.menu.time_min}분` + (isBest('time', x.menu.id) ? B : ''))],
    ['조건 일치도', items.map(x => x.match_pct === null ? '<span style="color:var(--muted)">조건 미설정</span>' : `${x.match_pct}%` + (isBest('match', x.menu.id) ? B : ''))],
    ['결정', items.map(x => `<button class="btn sm primary" type="button" data-decide="${x.menu.id}">이걸로 결정!</button><button class="btn sm ghost" type="button" data-remove="${x.menu.id}">빼기</button>`)]
  ];
  let html = `<div class="compare-wrap"><div class="compare" style="grid-template-columns:110px repeat(${items.length},minmax(150px,1fr))">`;
  rows.forEach(([label, cells, isHead], ri) => {
    const last = ri === rows.length - 1 ? ' last' : '';
    html += `<div class="rh${last}">${label}</div>`;
    cells.forEach(c => html += `<div class="${isHead ? 'ch' : ''}${last}">${c}</div>`);
  });
  html += '</div></div>';
  box.innerHTML = html;
}

/* ---------- 최종 결정 ---------- */
let deciding = false;
async function decide(id){
  if(deciding) return;
  deciding = true;
  let dec;
  try { dec = (await api('POST', '/api/decisions', {menu_id: +id, filters: state.f})).decision; }
  catch(e){ deciding = false; return fail(e); }
  deciding = false;
  const m = dec.menu;
  const t = parseDT(dec.decided_at);
  const timeStr = `${t.mo}월 ${t.d}일 ${t.h < 12 ? '오전' : '오후'} ${((t.h + 11) % 12) + 1}:${pad2(t.mi)}`;
  $('#modal').innerHTML = `
    <div class="lbl">🎉 오늘의 점심은</div>
    <div class="emo">${esc(m.emoji)}</div>
    <h2 class="name" id="finalName">${esc(m.name)}</h2>
    <div class="meta">${esc(m.category)} · ${won(dec.price)} · 약 ${m.time_min}분</div>
    <div class="reason" style="text-align:left">📝 ${esc(m.description)}<br>💡 <b>추천 사유</b> · ${esc(dec.reason)}</div>
    <div class="time">🕛 ${timeStr} 결정</div>
    <div class="row">
      <button class="btn primary" type="button" id="restartBtn">🔁 처음부터 다시</button>
      <button class="btn ghost" type="button" id="closeBtn">닫기</button>
    </div>`;
  $('#overlay').classList.add('show');
  $('#restartBtn').onclick = restart;
  $('#closeBtn').onclick = closeModal;
  $('#restartBtn').focus();
  confetti();
  state.cands = {items: [], best: {}};        // 서버에서도 결정 시 후보를 비운다
  renderCompare();
  try { await Promise.all([loadHistory(), loadList()]); refreshAll(); } catch(e){ fail(e); }
}
function closeModal(){ $('#overlay').classList.remove('show'); }
async function restart(){
  closeModal();
  clearTimeout(saveT);
  state.f = DEFAULT_F();
  state.current = null;
  renderFilters(); renderSpot(false);
  window.scrollTo({top: 0, behavior: 'smooth'});
  try {
    await api('PUT', '/api/preferences', {filters: state.f});
    for(const id of candIds()) await api('DELETE', '/api/candidates/' + id);
    await Promise.all([loadList(), loadCands()]);
    refreshAll();
  } catch(e){ fail(e); }
}
function confetti(){
  if(reduceMotion()) return;
  const box = document.createElement('div'); box.className = 'confetti';
  const em = ['🎉','🎊','✨','🍚','🥢','🧡','⭐'];
  for(let i = 0; i < 46; i++){
    const s = document.createElement('span');
    s.textContent = em[i % em.length];
    s.style.left = Math.random() * 100 + 'vw';
    s.style.fontSize = (16 + Math.random() * 20) + 'px';
    s.style.animationDuration = (1.8 + Math.random() * 1.6) + 's';
    s.style.animationDelay = (Math.random() * .5) + 's';
    box.appendChild(s);
  }
  document.body.appendChild(box);
  setTimeout(() => box.remove(), 4200);
}

/* ---------- 최근 결정 (최근 5개) ---------- */
async function loadHistory(){
  state.history = (await api('GET', '/api/decisions?limit=5&page=1')).items;
  renderHistory();
}
function renderHistory(){
  const box = $('#history');
  if(!state.history.length){ box.innerHTML = '<div class="empty">아직 결정한 메뉴가 없어요.</div>'; return; }
  box.innerHTML = '<ol>' + state.history.map(h => {
    const d = parseDT(h.decided_at);
    return `<li><span>${esc(h.emoji)} ${esc(h.menu_name)}</span><small>${d.mo}/${d.d} ${pad2(d.h)}:${pad2(d.mi)}</small></li>`;
  }).join('') + '</ol>';
}

/* ---------- 갱신 ---------- */
function refreshAll(){
  renderList(); renderCompare();
  if(todayData) renderToday(todayData);
  if(state.current && !state.rolling) renderSpot(false);
}

document.addEventListener('click', e => {
  const a = e.target.closest('[data-add]'); if(a){ addCand(a.dataset.add); return; }
  const r = e.target.closest('[data-remove]'); if(r){ removeCand(r.dataset.remove); return; }
  const d = e.target.closest('[data-decide]'); if(d){ decide(d.dataset.decide); return; }
});
$('#drawBtn').onclick = () => draw(false);
$('#redrawBtn').onclick = () => draw(true);
$('#resetFilters').onclick = () => { state.f = DEFAULT_F(); changed(); toast('조건을 초기화했어요'); };
$('#overlay').addEventListener('click', e => { if(e.target.id === 'overlay') closeModal(); });
document.addEventListener('keydown', e => { if(e.key === 'Escape') closeModal(); });

async function init(){
  setButtons();
  $('#cards').innerHTML = '<div class="skeleton">메뉴를 불러오는 중…</div>';
  try {
    const [meta, pref, today, cands, hist] = await Promise.all([
      api('GET', '/api/meta'),
      api('GET', '/api/preferences'),
      api('GET', '/api/today'),
      api('GET', '/api/candidates'),
      api('GET', '/api/decisions?limit=5&page=1')
    ]);
    state.groups = meta.groups;
    state.f = Object.assign(DEFAULT_F(), pref.filters);
    state.cands = cands;
    state.history = hist.items;
    todayData = today;
    renderToday(today); renderFilters(); renderCompare(); renderHistory();
    await loadList();
  } catch(e){
    fail(e);
    $('#cards').innerHTML = '<div class="empty-box">데이터를 불러오지 못했어요. 잠시 후 새로고침해 주세요.</div>';
  }
}
init();
})();
