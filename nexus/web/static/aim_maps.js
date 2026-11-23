// Practice › Aim on maps (web/drills.py).
// 4.51 "Your deaths": your deaths as drills. One card per spot: the same angle killing you again is "×2", "×3". The
// drills of new matches are worked out on the server in the background; the page asks again until they're all there.
// 4.52 the general drills on a map's real spots (from the fights in all its replays): hold an angle, attacking,
// tracking, clear a site. The spots on a plan of the map, a list, and the chosen spot's options (how they peek,
// difficulty, gun, reps) -> /profiles/<pid>/aim/play/<mode>/<map>/<spot>.
// 4.54 entry (on the sites' spots), retake and post-plant (on the spots after a plant: the spike, where attackers
// played it, the defenders' ways back in).
(function () {
  'use strict';
  const C = window.NEXUS_DRILLS;
  if (!C) return;
  const $ = id => document.getElementById(id);
  const T = s => (window.vcT ? window.vcT(s) : s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const TABS = ['deaths', 'hold', 'attack', 'track', 'clear', 'entry', 'retake', 'postplant'];
  // the tab from the address or a button: always one of our own names (never the text itself)
  const tabOf = v => {
    switch (v) {
      case 'deaths': return 'deaths';
      case 'hold': return 'hold';
      case 'attack': return 'attack';
      case 'track': return 'track';
      case 'clear': return 'clear';
      case 'entry': return 'entry';
      case 'retake': return 'retake';
      case 'postplant': return 'postplant';
      default: return null;
    }
  };
  let tab = tabOf(location.hash.slice(1)) || 'deaths';

  // ------------------------------------------------------------------------------------------ your deaths (4.51)
  let data = null, timer = 0;
  const f = {map: '', from: '10', first: false};
  try { Object.assign(f, JSON.parse(localStorage.getItem('nexus.drills.f') || '{}')); } catch (e) {}
  const saveF = () => { try { localStorage.setItem('nexus.drills.f', JSON.stringify(f)); } catch (e) {} };
  $('am-from').value = f.from; $('am-first').checked = !!f.first;

  async function load() {
    clearTimeout(timer);
    try {
      const r = await fetch(`${C.api}?from=${encodeURIComponent(f.from)}`, {credentials: 'same-origin'});
      data = await r.json();
      if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
      render();
      if (data.pending) timer = setTimeout(load, 2500);
    } catch (e) { $('am-msg').textContent = e.message; }
  }
  const short = a => String(a || '?').replace(/[^A-Za-z/]/g, '').slice(0, 3).toUpperCase();
  function render() {
    const d = data;
    $('am-n').textContent = '· ' + d.deaths;
    if (tab !== 'deaths') return;
    const sel = $('am-map'), keep = f.map;
    sel.innerHTML = `<option value="">${esc(T('All maps'))}</option>` + d.maps.map(m => `<option value="${esc(m)}" translate="no">${esc(m)}</option>`).join('');
    sel.value = d.maps.includes(keep) ? keep : '';
    const spots = d.spots.filter(s => (!sel.value || s.map === sel.value) && (!f.first || s.first === 'killer'));
    const beaten = spots.filter(s => s.beaten).length;
    $('am-stats').innerHTML = `<div><b>${d.deaths}</b><small>${esc(T('deaths with a replay'))}</small></div>` +
      `<div><b>${spots.length}</b><small>${esc(T('spots'))}${sel.value ? ' · <span translate="no">' + esc(sel.value) + '</span>' : ''}</small></div>` +
      `<div><b class="good">${beaten} / ${spots.length}</b><small>${esc(T('beaten (faster than him)'))}</small></div>`;
    const msg = [];
    if (d.pending) msg.push(`${T('Working out the drills of')} ${d.pending} ${T(d.pending === 1 ? 'match…' : 'matches…')}`);
    if (d.no_map && d.no_map.length) msg.push(`${T('Not on maps built from the game\'s files yet:')} ${d.no_map.join(', ')}`);
    $('am-msg').textContent = msg.join(' · ');
    $('am-grid').innerHTML = spots.map(card).join('');
    const empty = $('am-empty');
    empty.hidden = spots.length > 0 || d.pending > 0;
    empty.innerHTML = `<p class="muted">${esc(T('No drills yet. They come from your deaths in matches with a replay file, on maps built from the game\'s files.'))}</p>`;
    const all = $('am-all');
    all.hidden = spots.length < 2;
    if (spots.length >= 2) {
      const ids = spots.map(s => s.ids[0]);
      all.href = spots[0].url + '?queue=' + ids.slice(1).join(',');
      all.textContent = `${T('Play all')} ${spots.length} ${T('in a row')}`;
    }
  }
  function card(s) {
    const tags = [];
    if (s.first === 'killer') tags.push(`<span class="bad">${esc(T('he saw you first'))}</span>`);
    else if (s.first === 'same') tags.push(`<span>${esc(T('saw each other at once'))}</span>`);
    else if (s.first === 'victim') tags.push(`<span>${esc(T('you saw him first'))}</span>`);
    if (s.unseen) tags.push(`<span class="bad">${esc(T('never saw the killer'))}</span>`);
    if ((s.open_to || 0) > 1) tags.push(`<span class="bad">${esc(T('open to'))} ${s.open_to}</span>`);
    const best = s.best !== null && s.best !== undefined
      ? `<span class="${s.beaten ? 'good' : 'bad'}">${esc(T('your best'))} ${s.best.toFixed(2)} s</span>`
      : `<span>${esc(T('not played yet'))}</span>`;
    return `<article class="am-card">
      <div class="am-top"><span class="am-where" translate="no">${esc(s.map)} · ${esc(s.where || '?')}</span>${s.count > 1 ? `<span class="am-rep">×${s.count}</span>` : ''}</div>
      <div class="am-who"><span class="am-ag" translate="no"><img src="/agent-icon/${encodeURIComponent(s.killer_agent || '')}" alt="" onerror="this.replaceWith(document.createTextNode('${esc(short(s.killer_agent))}'))"></span>
        <span class="am-k"><b translate="no">${esc(s.killer_agent)} · ${esc(s.weapon)}</b><small>${s.kwhere ? esc(T('from')) + ' <span translate="no">' + esc(s.kwhere) + '</span> · ' : ''}<span translate="no">${esc(s.killer_name)}</span> · ${esc(T('round'))} ${s.round + 1}</small></span>
        <span class="am-his"><b>${s.his !== null && s.his !== undefined ? s.his.toFixed(2) + ' s' : '–'}</b><small>${esc(T('his time'))}</small></span></div>
      <div class="am-tags">${tags.join('')}${best}</div>
      <div class="am-btns"><a class="btn primary" href="${esc(s.url)}">${esc(T('Play drill'))}</a></div>
    </article>`;
  }
  $('am-map').addEventListener('change', e => { f.map = e.target.value; saveF(); render(); });
  $('am-from').addEventListener('change', e => { f.from = e.target.value; saveF(); load(); });
  $('am-first').addEventListener('change', e => { f.first = e.target.checked; saveF(); if (data) render(); });

  // ------------------------------------------------------------------------------------------ general drills (4.52)
  const INTRO = {
    hold: ['Hold an angle', 'You hold where defenders fight in your replays; enemies peek from the real corner: wide swings, jiggles, crouch and jump peeks, sometimes two at once. Kill each before he has you for his reaction time.'],
    attack: ['Attacking: you peek', 'You move (your keys, the game\'s speeds) and take the spot from defenders on the places they hold in your replays. Stop before you shoot: shots while moving go wide, and the drill shows how fast you stopped.'],
    track: ['Tracking', 'An enemy strafes left and right (ADAD) where the fights happen. Stay on his head for 30 seconds.'],
    clear: ['Clear a site', 'Walk the attackers\' route onto a site. Each hiding place defenders used is checked the moment it opens: was your crosshair on it, at head height? Some have an enemy.'],
    entry: ['Entry', 'First onto the site on the attackers\' route. Defenders wait on the places they hid in your replays, and one of them swings you when you get close. Take the site: the time from the start until the last one is down.'],
    retake: ['Retake', 'The spike is down. You come back in on the defenders\' real way, the attackers play it from the places they used in your replays. Kill them and defuse before it goes off (hold your defuse key, 7 s; half of it stays).'],
    postplant: ['Post-plant', 'You play the spike from the places attackers used after planting. The retakers come in on their real routes at their real speed and go for the spike. Kill each before he has you, and before anyone defuses.']};
  const fromTo = (a, b) => (a === b ? a : `${a} ${T('from')} ${b}`);
  function title(s) {                       // a spot's name in this tab
    switch (tab) {
      case 'hold': return `${T('Hold:')} ${fromTo(s.az, s.dz)}`;
      case 'attack': return `${T('Take:')} ${fromTo(s.dz, s.az)}`;
      case 'track': return `${T('Tracking at')} ${s.az}`;
      case 'entry': return `${T('Entry:')} ${fromTo(s.dz, s.az)}`;
      case 'retake': return `${T('Retake')} ${s.dz}`;
      case 'postplant': return `${T('Post-plant')} ${s.dz}`;
      default: return `${T('Clear:')} ${fromTo(s.dz, s.az)}`;
    }
  }
  const STYLE = {wide: 'Wide swing', jiggle: 'Jiggle peek', crouch: 'Crouch peek', jump: 'Jump peek', two: 'Two at once'};
  const DIFF = {easy: 'Easy', medium: 'Medium', hard: 'Hard', pro: 'Pro'};
  const REPS = {hold: [10, 20, 30], attack: [3, 5, 10], track: [1, 3, 5], clear: [1, 3, 5], entry: [3, 5, 10],
                retake: [3, 5, 10], postplant: [5, 10, 20]};
  const SITES = new Set(['clear', 'entry']), SPIKE = new Set(['retake', 'postplant']);
  const FOES = new Set(['entry', 'retake', 'postplant']);       // how many enemies: 1, 2 or 3
  let G = null, gTimer = 0, sel = null;
  const g = {map: '', styles: ['wide', 'jiggle', 'crouch'], diff: 'medium', gun: 'Vandal', reps: {}, foes: 2, util: true, agent: ''};
  // 4.56: the enemies' utility (what their side threw around these fights in your replays)
  const ENEMY = {hold: 'a', attack: 'd', entry: 'd', retake: 'a', postplant: 'd'};
  // 4.58: your agent (their C, Q and E in the drill; ultimates aren't in the drills)
  function agentPick() {
    if (!ENEMY[tab] || !C.agents) return '';
    const kit = C.agents[g.agent] || null;
    return `<fieldset class="am-opt"><legend>${esc(T('Your agent'))}</legend><select id="am-g-agent"><option value="">${esc(T('none (no abilities)'))}</option>${
      Object.keys(C.agents).map(a => `<option value="${esc(a)}" ${a === g.agent ? 'selected' : ''} translate="no">${esc(a)}</option>`).join('')}</select>
      ${kit ? `<small class="muted">${Object.entries(kit).map(([k, n]) => `${k} <span translate="no">${esc(n)}</span>`).join(' · ')}</small>` : ''}</fieldset>`;
  }
  const UTIL_NAME = {smoke: 'smokes', flash: 'flashes', damage: 'mollies', slow: 'slows', wall: 'walls', recon: 'recon', trap: 'traps'};
  try { Object.assign(g, JSON.parse(localStorage.getItem('nexus.drills.g') || '{}')); } catch (e) {}
  // only our own values (from the lists the page came with), whatever was saved or picked
  const own = (list, v, dflt) => { const i = list.indexOf(v); return i >= 0 ? list[i] : dflt; };
  g.diff = own(C.diffs, g.diff, 'medium'); g.gun = own(C.guns, g.gun, 'Vandal'); g.foes = own(C.foes || [1, 2, 3], g.foes, 2); g.util = g.util !== false; g.agent = (C.agents || {})[g.agent] ? g.agent : '';
  g.styles = C.peeks.filter(k => Array.isArray(g.styles) && g.styles.includes(k));
  if (!g.styles.length) g.styles = ['wide'];
  g.map = typeof g.map === 'string' ? g.map : '';
  if (!g.reps || typeof g.reps !== 'object') g.reps = {};
  const saveG = () => { try { localStorage.setItem('nexus.drills.g', JSON.stringify(g)); } catch (e) {} };

  async function loadSpots() {
    clearTimeout(gTimer);
    try {
      const r = await fetch(`${C.spots_api}?map=${encodeURIComponent(g.map || '')}`, {credentials: 'same-origin'});
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
      G = d;
      if (d.map && d.map !== g.map) { g.map = d.map; saveG(); }
      renderGen();
      if (d.pending && TABS.indexOf(tab) > 0) gTimer = setTimeout(loadSpots, 2500);
    } catch (e) { $('am-g-from').textContent = e.message; }
  }
  const list = () => (!G ? [] : SITES.has(tab) ? G.sites : SPIKE.has(tab) ? (G.retakes || []) : G.angles);
  const where = s => (SITES.has(tab) ? (s.hides[0] || s.route[s.route.length - 1]) : SPIKE.has(tab) ? s.plant : s.hold);
  const pctTab = () => tab === 'track' || tab === 'clear';
  // 4.59: your sessions on a spot (the median of each, oldest first) as a small line: better is up
  function spark(meds, higher) {
    if (!meds || meds.length < 2) return '';
    const W = 60, H = 16, lo = Math.min(...meds), hi = Math.max(...meds), k = hi > lo ? (H - 4) / (hi - lo) : 0;
    const pts = meds.map((v, i) => `${(i / (meds.length - 1) * (W - 2) + 1).toFixed(1)},${(higher ? H - 2 - (v - lo) * k : 2 + (v - lo) * k).toFixed(1)}`);
    const up = higher ? meds[meds.length - 1] >= meds[0] : meds[meds.length - 1] <= meds[0];
    return `<svg class="am-spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true"><polyline fill="none" stroke="${up ? '#5fe0c6' : '#ff7d8b'}" stroke-width="1.8" points="${pts.join(' ')}"/></svg>`;
  }
  function trendText(meds, higher) {
    if (!meds || !meds.length) return '';
    const f = v => (higher ? Math.round(v) + ' %' : v.toFixed(2) + ' s');
    if (meds.length === 1) return `${T('1 session:')} ${f(meds[0])}`;
    const n = Math.min(3, Math.floor(meds.length / 2)), a = meds.slice(0, n), b = meds.slice(-n);    // the first and last few
    const m = v => v.slice().sort((x, y) => x - y)[Math.floor(v.length / 2)];
    const ma = m(a), mb = m(b), better = higher ? mb > ma : mb < ma, same = Math.abs(mb - ma) < (higher ? 2 : 0.03);
    return `${meds.length} ${T('sessions:')} ${f(ma)} → ${f(mb)} <span class="${same ? 'muted' : better ? 'good' : 'bad'}">${T(same ? 'about the same' : better ? 'better' : 'worse')}</span>${spark(meds, higher)}`;
  }

  // 4.59: what your last match points to: the drill on each spot you died at, the most deaths first
  const MODE_NAME = {hold: 'Hold', attack: 'Take', entry: 'Entry', retake: 'Retake', postplant: 'Post-plant'};
  let SUG = null;
  async function loadSuggest(again = 0) {
    if (!C.suggest_api) return;
    try {
      const r = await fetch(C.suggest_api + (C.match ? `?match=${encodeURIComponent(C.match)}` : ''), {credentials: 'same-origin'});
      SUG = await r.json();
    } catch (e) { return; }
    if (SUG.pending && again < 20) setTimeout(() => loadSuggest(again + 1), 3000);
    renderSuggest();
  }
  function renderSuggest() {
    const box = $('am-suggest');
    if (!box || !SUG || (!SUG.items.length && !SUG.pending)) { if (box) box.hidden = true; return; }
    box.hidden = false;
    const when = SUG.started ? new Date(SUG.started).toLocaleDateString() : '';
    const head = `${T(C.match ? 'This match' : 'Your last match')}: <span translate="no">${esc(SUG.map)}</span>${SUG.score ? ' ' + esc(SUG.score) : ''}${when ? ' · ' + esc(when) : ''}`;
    box.innerHTML = `<h3>${T('Practice what cost you rounds')}</h3><p class="small muted">${head}${SUG.pending ? ' · ' + esc(T('working it out…')) : ''}</p>
      <ul>${SUG.items.map((it, i) => `<li><button type="button" data-sug="${i}"><b><span>${esc(T(MODE_NAME[it.mode] || it.mode))}</span> <span translate="no">${esc(it.mode === 'retake' || it.mode === 'postplant' ? it.dz : fromTo(it.mode === 'hold' ? it.az : it.dz, it.mode === 'hold' ? it.dz : it.az))}</span></b>
        <small>${it.deaths}× ${esc(T(it.deaths === 1 ? 'death' : 'deaths'))} · ${esc(T(it.rounds.length === 1 ? 'round' : 'rounds'))} ${it.rounds.join(', ')}</small></button></li>`).join('')}</ul>`;
  }
  function openSpot(mode, mapName, id) {
    sel = id;
    if (!G || G.map !== mapName) { g.map = mapName; saveG(); G = null; }
    show(mode);
    if (G) renderGen();
    $('am-gen').scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-sug]');
    if (!b || !SUG) return;
    const it = SUG.items[+b.dataset.sug];
    if (it) openSpot(it.mode, SUG.map, it.id);
  });

  function renderGen() {
    const [head, text] = INTRO[tab];
    $('am-g-title').textContent = T(head); $('am-g-text').textContent = T(text);
    if (!G) return;
    const ms = $('am-g-map');
    ms.innerHTML = G.maps.map(m => `<option value="${esc(m.name)}" translate="no">${esc(m.name)} (${m.matches})</option>`).join('');
    ms.value = G.map;
    const from = [];
    if (G.map) from.push(`${T('Spots from')} ${G.fights} ${T('fights in the replays of this map')}`);
    if (G.pending) from.push(`${T('Working out')} ${G.pending} ${T(G.pending === 1 ? 'match…' : 'matches…')}`);
    $('am-g-from').textContent = from.join(' · ');
    const L = list();
    if (!sel || !L.some(s => s.id === sel)) sel = L.length ? L[0].id : null;
    const body = $('am-g-body'), empty = $('am-empty');
    body.hidden = !L.length;
    empty.hidden = !!L.length || !!G.pending;
    empty.innerHTML = `<p class="muted">${esc(T(!G.maps.length ? 'No maps yet: the general drills need replays on maps built from the game\'s files.'
      : SPIKE.has(tab) ? 'No retakes on this map yet. They come from the fights after a plant in its replays.' : 'No spots on this map yet. They come from the fights in its replays.'))}</p>`;
    $('am-g-list').innerHTML = L.slice(0, 40).map(s => {
      const best = (s.best || {})[tab];
      const b = best === null || best === undefined ? '' : `<span class="good">${pctTab() ? Math.round(best) + ' %' : best.toFixed(2) + ' s'}</span>`;
      return `<li><button type="button" data-sid="${esc(s.id)}" class="${s.id === sel ? 'on' : ''}"><span translate="no">${esc(title(s))}</span><small>×${s.count}${b ? ' · ' + b : ''}${spark((s.trend || {})[tab], pctTab())}</small></button></li>`;
    }).join('');
    plan();
    spotCard();
  }
  function plan() {                         // the spots on a plan of the map: where the fights were
    const cv = $('am-plan'), x = cv.getContext('2d'), W = cv.width, H = cv.height;
    x.clearRect(0, 0, W, H);
    if (!G) return;
    const pts = [];
    for (const a of G.angles) pts.push(a.hold, a.start, ...a.peeks, ...a.defs);
    for (const s of G.sites) pts.push(...s.route, ...s.hides);
    for (const s of G.retakes || []) pts.push(s.plant, ...s.posts, ...s.routes.flatMap(r => r.path));
    if (!pts.length) return;
    const xs = pts.map(p => p[0]), zs = pts.map(p => p[2]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
    const k = Math.min((W - 60) / Math.max(1, x1 - x0), (H - 60) / Math.max(1, z1 - z0));
    const ox = (W - (x1 - x0) * k) / 2, oz = (H - (z1 - z0) * k) / 2;
    const to = p => [ox + (p[0] - x0) * k, oz + (p[2] - z0) * k];
    plan.to = to;
    x.fillStyle = 'rgba(140,155,190,.18)';
    for (const p of pts) { const [a, b] = to(p); x.beginPath(); x.arc(a, b, 5, 0, 2 * Math.PI); x.fill(); }
    const L = list(), s = L.find(q => q.id === sel);
    if (s) {                                  // the chosen spot: who goes where
      x.lineWidth = 2;
      const line = (a, b, col, dash) => { const [p, q] = [to(a), to(b)]; x.strokeStyle = col; x.setLineDash(dash || []); x.beginPath(); x.moveTo(...p); x.lineTo(...q); x.stroke(); x.setLineDash([]); };
      const dot = (p, col, r = 5) => { const [a, b] = to(p); x.fillStyle = col; x.beginPath(); x.arc(a, b, r, 0, 2 * Math.PI); x.fill(); };
      if (SPIKE.has(tab)) {                  // the defenders' ways back in, where attackers played it, the spike
        for (const r of s.routes) {
          x.strokeStyle = '#5fe0c6'; x.lineWidth = 3; x.setLineDash([7, 6]); x.beginPath();
          r.path.forEach((p, i) => { const [a, b] = to(p); if (i) x.lineTo(a, b); else x.moveTo(a, b); });
          x.stroke(); x.setLineDash([]);
          dot(r.path[0], '#5fe0c6', 6);
        }
        for (const p of s.posts) dot(p, '#ff7d8b', 6);
        const [a, b] = to(s.plant);
        x.fillStyle = '#ff3b4e'; x.strokeStyle = '#fff'; x.lineWidth = 2;
        x.beginPath(); x.moveTo(a, b - 10); x.lineTo(a + 9, b); x.lineTo(a, b + 10); x.lineTo(a - 9, b); x.closePath(); x.fill(); x.stroke();
      } else if (SITES.has(tab)) {
        x.strokeStyle = '#ff4f8b'; x.lineWidth = 3; x.setLineDash([7, 6]); x.beginPath();
        s.route.forEach((p, i) => { const [a, b] = to(p); if (i) x.lineTo(a, b); else x.moveTo(a, b); });
        x.stroke(); x.setLineDash([]);
        dot(s.route[0], '#ffd166', 7);
        for (const h of s.hides) dot(h, '#5fe0c6', 6);
      } else if (tab === 'attack') {
        for (const d of s.defs) { line(s.start, d, 'rgba(255,79,139,.6)', [5, 5]); dot(d, '#ff7d8b', 6); }
        dot(s.start, '#ffd166', 8);
      } else {
        for (const p of s.peeks) { line(s.hold, p, 'rgba(255,209,102,.5)', [5, 5]); dot(p, '#ff7d8b', 6); }
        dot(s.hold, '#ffd166', 8);
      }
    }
    x.font = '12px system-ui, sans-serif'; x.textAlign = 'center';
    const top = Math.max(1, ...L.map(q => q.count));
    for (const q of L.slice().reverse()) {     // the most fought-over on top
      const [a, b] = to(where(q)), r = 7 + 11 * Math.sqrt(q.count / top), on = q.id === sel;
      x.fillStyle = on ? 'rgba(255,79,139,.85)' : 'rgba(91,107,140,.75)';
      x.strokeStyle = '#fff'; x.lineWidth = on ? 2.5 : 1;
      x.beginPath(); x.arc(a, b, r, 0, 2 * Math.PI); x.fill(); x.stroke();
      x.fillStyle = '#fff'; x.fillText(String(q.count), a, b + 4);
    }
    for (const q of L.slice(0, 8)) {
      const [a, b] = to(where(q)), r = 7 + 11 * Math.sqrt(q.count / top);
      x.lineWidth = 3; x.strokeStyle = 'rgba(0,0,0,.7)'; x.strokeText(q.dz, a, b - r - 4);
      x.fillStyle = '#e8e9f2'; x.fillText(q.dz, a, b - r - 4);
    }
  }
  function playUrl(s) {
    const o = new URLSearchParams();
    if (tab === 'hold') o.set('styles', g.styles.join(','));
    o.set('diff', g.diff); o.set('gun', g.gun); o.set('reps', String(g.reps[tab] || C.reps[tab]));
    if (FOES.has(tab)) o.set('foes', String(g.foes));
    if (ENEMY[tab] && !g.util) o.set('util', '0');
    if (ENEMY[tab] && g.agent) o.set('agent', g.agent);
    return C.play.replace('MODE', tab).replace('MAP', encodeURIComponent(G.map)).replace('SID', s.id) + '?' + o;
  }
  function spotCard() {
    const el = $('am-g-spot'), s = list().find(q => q.id === sel);
    if (!s) { el.innerHTML = ''; return; }
    const reps = g.reps[tab] || C.reps[tab];
    const what = tab === 'hold' ? `${T('Enemies come out of')} <span translate="no">${esc(s.az)}</span>.`
      : tab === 'attack' ? `${Math.min(3, s.defs.length)} ${T('defenders on the places they held.')}`
      : tab === 'track' ? `${T('About')} ${Math.round(s.dist)} m ${T('away.')}`
      : tab === 'entry' ? `${s.hides.length} ${T('places defenders hid; one of them swings you.')}`
      : SPIKE.has(tab) ? `${s.posts.length} ${T('places attackers played the spike from,')} ${s.routes.length} ${T(s.routes.length === 1 ? 'way back in.' : 'ways back in.')} ${T('The spike has')} ${Math.round(s.left)} s ${T('left when they set off.')}`
      : `${s.hides.length} ${T('hiding places; the route attackers took most.')}`;
    const won = SITES.has(tab) ? '' : ` ${T('Defenders won')} ${Math.round(s.won_def / s.count * 100)} %.`;
    const foes = !FOES.has(tab) ? '' : `<fieldset class="am-opt"><legend>${esc(T(tab === 'postplant' ? 'Retakers' : tab === 'retake' ? 'Attackers' : 'Defenders'))}</legend>${(C.foes || [1, 2, 3]).map(n =>
      `<label class="am-chip"><input type="radio" name="am-foes" value="${n}" ${g.foes === n ? 'checked' : ''}> ${n}</label>`).join('')}</fieldset>`;
    const side = ENEMY[tab], sets = side ? (s.util || []).filter(set => set.some(u => u[2] === side)) : [];
    const kinds = [...new Set(sets.flat().filter(u => u[2] === side).map(u => u[0]))].filter(k => UTIL_NAME[k]);
    const util = !side ? '' : `<fieldset class="am-opt"><legend>${esc(T('Their utility'))}</legend>${sets.length
      ? `<label class="am-chip"><input type="radio" name="am-util" value="1" ${g.util ? 'checked' : ''}> ${esc(T('on'))}</label><label class="am-chip"><input type="radio" name="am-util" value="0" ${g.util ? '' : 'checked'}> ${esc(T('off'))}</label>
        <small class="muted">${esc(T('from'))} ${sets.length} ${esc(T(sets.length === 1 ? 'round' : 'rounds'))}: ${kinds.map(k => esc(T(UTIL_NAME[k]))).join(', ')}</small>`
      : `<small class="muted">${esc(T('None in your replays here yet.'))}</small>`}</fieldset>`;
    const styles = tab !== 'hold' ? '' : `<fieldset class="am-opt"><legend>${esc(T('How they peek'))}</legend>${C.peeks.map(k =>
      `<label class="am-chip"><input type="checkbox" data-style="${k}" ${g.styles.includes(k) ? 'checked' : ''}> ${esc(T(STYLE[k]))}</label>`).join('')}</fieldset>`;
    const best = (s.best || {})[tab];
    el.innerHTML = `<p class="muted small" translate="no">${esc(G.map)} · ${esc(s.dz)}</p>
      <h2 translate="no">${esc(title(s))}</h2>
      <p>${esc(T('Fought over'))} ${s.count} ${esc(T(s.count === 1 ? 'time in the replays.' : 'times in the replays.'))}${esc(won)} ${what}</p>
      ${styles}${foes}${util}${agentPick()}
      <fieldset class="am-opt"><legend>${esc(T(tab === 'track' ? 'How fast he strafes' : 'Difficulty'))}</legend>${C.diffs.map(k =>
        `<label class="am-chip"><input type="radio" name="am-diff" value="${k}" ${g.diff === k ? 'checked' : ''}> ${esc(T(DIFF[k]))}</label>`).join('')}</fieldset>
      <div class="am-row"><label>${esc(T('Gun'))} <select id="am-g-gun">${C.guns.map(n => `<option ${n === g.gun ? 'selected' : ''} translate="no">${esc(n)}</option>`).join('')}</select></label>
        <label>${esc(T(tab === 'hold' ? 'Peeks' : 'Reps'))} <select id="am-g-reps">${REPS[tab].map(n => `<option ${n === reps ? 'selected' : ''}>${n}</option>`).join('')}</select></label></div>
      <p class="am-btns"><a class="btn primary" id="am-g-play" href="${esc(playUrl(s))}">${esc(T('Play drill'))} · ${reps} ${esc(T(tab === 'hold' ? 'peeks' : reps === 1 ? 'rep' : 'reps'))}</a>
        ${best !== null && best !== undefined ? `<span class="good">${esc(T('your best'))} ${pctTab() ? Math.round(best) + ' %' : best.toFixed(2) + ' s'}</span>` : `<span class="muted">${esc(T('not played yet'))}</span>`}</p>
      ${(s.trend || {})[tab] ? `<p class="small">${trendText(s.trend[tab], pctTab())}</p>` : ''}`;
  }
  $('am-g-map').addEventListener('change', e => { g.map = own((G ? G.maps : []).map(m => m.name), e.target.value, g.map); saveG(); sel = null; G = null; plan(); loadSpots(); });
  $('am-g-list').addEventListener('click', e => { const b = e.target.closest('[data-sid]'); if (b) { sel = b.dataset.sid; renderGen(); } });
  $('am-plan').addEventListener('click', e => {
    if (!plan.to) return;
    const cv = e.currentTarget, rc = cv.getBoundingClientRect();
    const px = (e.clientX - rc.left) * cv.width / rc.width, py = (e.clientY - rc.top) * cv.height / rc.height;
    let best = null, bd = 30;
    for (const q of list()) { const [a, b] = plan.to(where(q)), d = Math.hypot(a - px, b - py); if (d < bd) { bd = d; best = q; } }
    if (best) { sel = best.id; renderGen(); }
  });
  $('am-g-spot').addEventListener('change', e => {
    const t = e.target;
    if (t.dataset.style) {
      const on = new Set(g.styles); if (t.checked) on.add(t.dataset.style); else on.delete(t.dataset.style);
      g.styles = C.peeks.filter(k => on.has(k));
      if (!g.styles.length) g.styles = ['wide'];
    } else if (t.name === 'am-diff') g.diff = own(C.diffs, t.value, g.diff);
    else if (t.id === 'am-g-gun') g.gun = own(C.guns, t.value, g.gun);
    else if (t.name === 'am-foes') g.foes = own(C.foes || [1, 2, 3], +t.value, g.foes);
    else if (t.name === 'am-util') g.util = t.value === '1';
    else if (t.id === 'am-g-agent') g.agent = (C.agents || {})[t.value] ? t.value : '';
    else if (t.id === 'am-g-reps') g.reps[tab] = own(REPS[tab], +t.value, C.reps[tab]);
    saveG(); spotCard();
  });

  // ------------------------------------------------------------------------------------------ tabs, keys
  function show(t) {
    tab = tabOf(t) || 'deaths';
    t = tab;
    for (const b of document.querySelectorAll('.am-tabs [data-tab]')) {
      const on = b.dataset.tab === t; b.classList.toggle('on', on); b.setAttribute('aria-selected', String(on));
    }
    const gen = t !== 'deaths';
    $('am-deaths').hidden = gen; $('am-grid').hidden = gen; $('am-gen').hidden = !gen;
    $('am-g-body').hidden = true; $('am-empty').hidden = true;
    try { history.replaceState(null, '', '#' + t); } catch (e) {}
    if (gen) { if (G) renderGen(); else { renderGen(); loadSpots(); } }
    else if (data) render();
  }
  document.querySelector('.am-tabs').addEventListener('click', e => { const b = e.target.closest('[data-tab]'); if (b) show(b.dataset.tab); });
  let ed = null;
  for (const b of document.querySelectorAll('[data-keys]')) b.addEventListener('click', () => {
    const box = $('am-keys');
    box.hidden = !box.hidden;
    if (!box.hidden && !ed) ed = window.NexusKeys.editor($('am-keys-box'), {keys: C.keys, defaults: C.defaults, actions: C.actions, api: C.keys_api});
  });
  window.addEventListener('hashchange', () => { const t = tabOf(location.hash.slice(1)); if (t && t !== tab) show(t); });
  show(tab);
  load();
  loadSuggest();
})();
