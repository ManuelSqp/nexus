// 4.51: one aim drill on the real map (Practice › Aim on maps; web/drills.py, stats/drills.py). You stand where you
// died, looking where you looked; your killer comes out on his real path from the replay (his agent animated, his
// gun), the round's smokes, walls and flashes where they were. Shoot him before his time: how long he had you in
// view before he killed you. Valorant's numbers: 0.07° per mouse count × sens, 103° wide view, the gun's magazine,
// fire rate, reload and damage (head, body, legs on the agent's skeleton), walls and smokes in the way.
// Keys are yours (keys.js); Esc always stops.
(function () {
  'use strict';
  const C = window.NEXUS_MAP3D;
  if (!C || !C.drill) return;
  const D = C.drill, NM = window.NexusMotion, KB = window.NexusKeys;
  const $ = id => document.getElementById(id);
  const T = s => (window.vcT ? window.vcT(s) : s);
  const V = () => window.nexusMap3D;
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const D2R = Math.PI / 180, YAW = 0.07, VFOV = 70.53;
  const EYE = 1.85, MAP_EYE = 1.6;          // your eyes above your feet (the agents' eyes); map3d.js adds MAP_EYE
  const HEAD_R = 0.14, BODY_R = 0.2, ARM_R = 0.07, LEG_R = 0.1;
  const WATCH = 0.35;                       // "watch how he did it": this fast
  const ENEMY = [0.86, 0.3, 0.36];
  const canvas = $('m3-canvas');
  let keys = KB.normalize(C.keys, C.defaults);
  const opt = {speed: 1, heads: true, reps: 10};
  try { Object.assign(opt, JSON.parse(localStorage.getItem('nexus.drill') || '{}')); } catch (e) {}
  const saveOpt = () => { try { localStorage.setItem('nexus.drill', JSON.stringify(opt)); } catch (e) {} };
  const gun = C.gun, HP = C.hp || 150;
  const S = {phase: 'loading', R: null, kp: null, t: D.t0, reps: [], rep: 0, yaw: D.me[3], pitch: 0, seen: null,
             kill: null, hp: HP, ammo: gun.mag, reload: 0, next: 0, firing: false, ads: false, first: null,
             firsts: {head: 0, body: 0, legs: 0, miss: 0}, offs: [], flash: 0, until: 0, msg: '', lastT: D.t0,
             paused: false, saved: false};

  // ------------------------------------------------------------------------------------------ data
  async function load() {
    try {
      const r = await fetch(C.round_api, {credentials: 'same-origin'});
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
      NM.prep(d.paths);
      S.R = d; S.kp = d.paths[D.killer];
      if (!S.kp) throw new Error(T('The killer isn\'t in this round\'s replay.'));
      S.phase = 'ready';
      panel();
    } catch (e) {
      S.phase = 'error';
      panel(e.message);
    }
  }
  const eye = () => [D.me[0], D.me[1] + EYE, D.me[2]];
  const look = () => [Math.sin(S.yaw) * Math.cos(S.pitch), Math.sin(S.pitch), -Math.cos(S.yaw) * Math.cos(S.pitch)];
  const zoom = () => (S.ads ? gun.zoom || 1 : 1);
  function enemyAt(t) {
    const p = NM.atClamped(S.kp, t);
    return p;
  }

  // ------------------------------------------------------------------------------------------ hits
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const add = (a, b, k) => [a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k];
  function rayCapsule(o, d, a, b, r) {      // -> distance along the ray to the capsule a–b (radius r), or null
    const u = sub(b, a), cc = dot(u, u) || 1e-9;
    let best = null;
    for (let i = 0; i <= 8; i++) {          // closest approach: a few steps along the segment, then refined
      const s = i / 8, q = add(a, u, s), t = Math.max(0, dot(sub(q, o), d)), p = add(o, d, t), dd = dot(sub(p, q), sub(p, q));
      if (best === null || dd < best[1]) best = [t, dd, s];
    }
    let [t, dd, s] = best;
    for (let k = 0; k < 3; k++) {
      const p = add(o, d, t);
      s = Math.max(0, Math.min(1, dot(sub(p, a), u) / cc));
      const q = add(a, u, s);
      t = Math.max(0, dot(sub(q, o), d));
      const p2 = add(o, d, t); dd = dot(sub(p2, q), sub(p2, q));
    }
    if (dd > r * r) return null;
    return Math.max(0, t - Math.sqrt(r * r - dd));
  }
  function hitboxes() {                    // [[part, a, b, r], …] on the map
    const b = V().bones && V().bones(D.killer);
    const p = enemyAt(S.t);
    if (!b || !b.Head) {                    // no animations: a standing body
      const x = p[0], y = p[1], z = p[2];
      return [['head', [x, y + 1.97, z], [x, y + 1.97, z], HEAD_R], ['body', [x, y + 1.05, z], [x, y + 1.7, z], BODY_R],
              ['legs', [x, y + 0.1, z], [x, y + 0.95, z], LEG_R * 1.6]];
    }
    const up = sub(b.Head, b.Neck), n = Math.hypot(...up) || 1, hc = add(b.Head, up, 0.09 / n);
    const out = [['head', hc, hc, HEAD_R], ['body', b.Pelvis, b.Spine4, BODY_R], ['body', b.Spine4, b.Neck, BODY_R * 0.8]];
    for (const s of ['L', 'R']) {
      out.push(['body', b[s + '_Shoulder'], b[s + '_Elbow'], ARM_R], ['body', b[s + '_Elbow'], b[s + '_Hand'], ARM_R]);
      out.push(['legs', b[s + '_Hip'], b[s + '_Knee'], LEG_R], ['legs', b[s + '_Knee'], b[s + '_Foot'], LEG_R * 0.85]);
    }
    return out.filter(h => h[1] && h[2]);
  }
  function smokes() { return S.R ? NM.utilObjects(S.R.util, S.t, C.util_col).filter(o => o.block) : []; }
  function throughSmoke(a, b) {             // a line from a to b goes through a smoke or a wall
    const d = sub(b, a), L = Math.hypot(...d) || 1, u = [d[0] / L, d[1] / L, d[2] / L];
    for (const s of smokes()) {
      const r = s.r * Math.max(...(s.sc || [1, 1, 1])) * 0.92, c = [s.x, s.y, s.z];
      const t = Math.max(0, Math.min(L, dot(sub(c, a), u))), p = add(a, u, t);
      if (dot(sub(p, c), sub(p, c)) < r * r) return true;
    }
    return false;
  }
  function canSee(p) { return V().visible(eye(), p) && !throughSmoke(eye(), p); }
  function shoot() {
    if (S.phase !== 'run' || S.kill) return;
    const now = performance.now() / 1000;
    if (S.reload > now || now < S.next) return;
    if (S.ammo <= 0) { startReload(); return; }
    S.ammo--; S.next = now + 1 / gun.rate;
    const o = eye(), d = look();
    let hit = null;
    for (const [part, a, b, r] of hitboxes()) {
      const t = rayCapsule(o, d, a, b, r);
      if (t !== null && (hit === null || t < hit[1])) hit = [part, t];
    }
    if (hit) {
      const p = add(o, d, Math.max(0, hit[1] - 0.05));
      if (!V().visible(o, p)) hit = null;          // a wall in the way
    }
    const part = hit ? hit[0] : 'miss';
    if (!S.first) { S.first = part; S.firsts[part]++; }
    marker(part);
    if (!hit) return;
    S.hp -= gun[part] || 0;
    const dead = part === 'head' ? (opt.heads || S.hp <= 0) : (!opt.heads && S.hp <= 0);
    if (dead) killed();
  }
  function startReload() {
    const now = performance.now() / 1000;
    if (S.reload > now || S.ammo >= gun.mag) return;
    S.reload = now + gun.reload; S.firing = false;
  }
  function killed() {
    const mine = Math.max(0, S.t - (S.seen ?? S.t));
    S.kill = {t: S.t, time: mine, wall: performance.now() / 1000};
    S.reps.push(Math.round(mine * 1000) / 1000);
    endRep(mine);
  }

  // ------------------------------------------------------------------------------------------ the reps
  function startRep() {
    S.t = D.t0; S.lastT = D.t0; S.yaw = D.me[3]; S.pitch = 0; S.seen = null; S.kill = null; S.hp = HP;
    S.ammo = gun.mag; S.reload = 0; S.next = 0; S.first = null; S.flash = 0; S.msg = '';
    S.phase = 'count'; S.until = performance.now() / 1000 + 0.7;
    panel();
  }
  function endRep(mine) {
    S.phase = 'between'; S.firing = false;
    const his = D.his;
    if (mine === null) S.msg = `<b class="bad">${esc(T('He got you'))}</b>`;
    else if (his !== null && his !== undefined) S.msg = mine < his ? `<b class="good">${esc(T('Faster than him'))} · ${mine.toFixed(2)} s</b>` : `<b class="bad">${esc(T('Slower than him'))} · ${mine.toFixed(2)} s</b>`;
    else S.msg = `<b class="good">${mine.toFixed(2)} s</b>`;
    S.until = performance.now() / 1000 + (mine === null ? 1.3 : 1.6);
    hud(true);
  }
  function failRep() {
    S.reps.push(null);
    endRep(null);
  }
  function afterRep() {
    if (S.reps.length >= opt.reps) done();
    else startRep();
  }
  function restart() { S.reps = []; S.firsts = {head: 0, body: 0, legs: 0, miss: 0}; S.offs = []; S.saved = false; startRep(); }
  function watch() {
    if (!S.R) return;
    S.t = D.t0; S.lastT = D.t0; S.kill = null; S.seen = null; S.yaw = D.me[3]; S.pitch = 0;
    S.phase = 'watch'; S.msg = esc(T('Watching how he did it (slowed down)'));
    panel();
  }

  // ------------------------------------------------------------------------------------------ the clock
  function tick(dt) {
    if (!S.R) { camera(); return; }
    const now = performance.now() / 1000;
    if (S.phase === 'count' && now >= S.until) { S.phase = 'run'; panel(); }
    if (S.phase === 'between' && now >= S.until) afterRep();
    if (S.phase === 'run' || S.phase === 'watch') {
      S.lastT = S.t;
      S.t += dt * (S.phase === 'watch' ? WATCH : opt.speed);
      const hb = hitboxes(), hd = hb[0], chest = hb.find(h => h[0] === 'body');
      if (S.seen === null && hd && (canSee(hd[1]) || (chest && canSee(chest[2])))) {
        S.seen = S.t;
        if (S.phase === 'run') {
          const v = sub(hd[1], eye()), L = Math.hypot(...v) || 1;
          S.offs.push(Math.acos(Math.max(-1, Math.min(1, dot(look(), [v[0] / L, v[1] / L, v[2] / L])))) / D2R);
        }
      }
      flashes();
      if (S.phase === 'run' && !S.kill && S.t >= D.t_kill) failRep();
      if (S.phase === 'watch' && S.t >= D.t_kill) { S.phase = 'between'; S.msg = ''; S.until = now + 0.8; }
      if (S.phase === 'run' && S.firing && gun.auto) shoot();
    }
    if (S.reload && now >= S.reload) { S.reload = 0; S.ammo = gun.mag; }
    S.flash = Math.max(0, S.flash - dt / 1.6);
    camera();
    hud();
  }
  function flashes() {                     // a flash that popped in your view while you looked
    for (const u of (S.R.util || [])) {
      if (u.type !== 'flash' || u.t0 <= S.lastT || u.t0 > S.t) continue;
      const p = [u.x, (u.y !== null ? u.y : D.me[1]) + 1.2, u.z], v = sub(p, eye()), L = Math.hypot(...v) || 1;
      const ang = Math.acos(Math.max(-1, Math.min(1, dot(look(), [v[0] / L, v[1] / L, v[2] / L])))) / D2R;
      if (ang < 60 && V().visible(eye(), p)) S.flash = 1;
    }
  }
  function camera() {
    V().view({x: D.me[0], y: D.me[1] + EYE - MAP_EYE, z: D.me[2], yaw: S.yaw, pitch: S.pitch, fly: true, fov: VFOV / zoom()});
  }

  // ------------------------------------------------------------------------------------------ for map3d.js
  function models() {
    if (!S.R || !C.agents) return [];
    const url = C.agents[D.killer_agent];
    if (!url) return [];
    const p = enemyAt(S.kill ? S.kill.t : S.t);
    if (!p) return [];
    const o = {key: D.killer, url, x: p[0], y: p[1], z: p[2], yaw: p[3], col: ENEMY};
    if (S.kill) {
      o.anim = {lb: [[NM.deathClip(p, D.me), performance.now() / 1000 - S.kill.wall, 1]], ub: null};
      return [o];
    }
    if (C.anims) {
      const w = D.weapon, m = NM.motion(S.kp, S.t, p, NM.holdFor(w));
      o.anim = m.anim; o.y += m.lift; o.gun = (C.guns && C.guns[w]) || null; o.hold = NM.holdFor(w);
    }
    return [o];
  }
  function objects() { return S.R ? NM.utilObjects(S.R.util, S.t, C.util_col) : []; }

  // ------------------------------------------------------------------------------------------ the page
  let lastHud = 0;
  function hud(force) {
    const now = performance.now();
    if (!force && now - lastHud < 60) return;
    lastHud = now;
    const running = S.phase === 'run' && S.seen !== null && !S.kill ? S.t - S.seen : (S.kill ? S.kill.time : 0);
    $('dr-clock').textContent = (S.phase === 'run' || S.kill) ? running.toFixed(2) + ' s' : '–';
    $('dr-reps').innerHTML = Array.from({length: opt.reps}, (_, i) => {
      const v = S.reps[i], cls = i < S.reps.length ? (v === null ? 'miss' : (D.his !== null && D.his !== undefined && v < D.his) || D.his === null ? 'beat' : 'slow') : (i === S.reps.length ? 'now' : '');
      return `<i class="${cls}" title="${esc(T('Rep'))} ${i + 1}"></i>`;
    }).join('');
    $('dr-rep').textContent = `${T('Rep')} ${Math.min(opt.reps, S.reps.length + (S.phase === 'between' ? 0 : 1))} / ${opt.reps}`;
    const rel = S.reload > performance.now() / 1000;
    $('dr-ammo').innerHTML = rel ? `<b>${esc(T('Reloading…'))}</b>` : `<b>${S.ammo}</b> / ${gun.mag} · <span translate="no">${esc(gun.name)}</span>`;
    $('dr-flash').style.opacity = String(Math.min(1, S.flash * 1.1));
    $('dr-msg').innerHTML = S.msg;
    $('dr-msg').hidden = !S.msg || S.phase === 'done';
  }
  let markT = 0;
  function marker(part) {
    const el = $('dr-hit');
    el.textContent = T(part === 'head' ? 'HEAD' : part === 'body' ? 'BODY' : part === 'legs' ? 'LEGS' : 'MISS');
    el.className = 'dr-hit ' + part; el.hidden = false;
    clearTimeout(markT); markT = setTimeout(() => { el.hidden = true; }, 500);
  }
  const keyName = a => KB.label((keys[a] || [])[0]) || '–';
  function panel(err) {
    const el = $('dr-panel');
    if (err) { el.hidden = false; el.innerHTML = `<p class="bad">${esc(err)}</p><p><a class="btn" href="${esc(C.list)}">${esc(T('Back to the list'))}</a></p>`; return; }
    if (S.phase === 'loading') { el.hidden = false; el.innerHTML = `<p>${esc(T('Loading the drill…'))}</p>`; return; }
    if (S.phase === 'ready' || S.paused) {
      el.hidden = false;
      el.innerHTML = `<h2>${esc(S.paused ? T('Paused') : T('Your death as a drill'))}</h2>` +
        `<p>${esc(T('You stand where you died, looking where you looked. He comes out the same way he did. Kill him before his time.'))}</p>` +
        `<p class="dr-his">${esc(T('His time'))}: <b>${D.his !== null && D.his !== undefined ? D.his.toFixed(2) + ' s' : '–'}</b></p>` +
        `<p class="muted small">${esc(keyName('shoot'))} ${esc(T('shoot'))} · ${esc(keyName('reload'))} ${esc(T('reload'))} · ${esc(keyName('restart'))} ${esc(T('again'))} · ${esc(keyName('watch'))} ${esc(T('watch how he did it'))} · Esc ${esc(T('stop'))}</p>` +
        `<p><button type="button" class="btn primary" data-a="go">${esc(S.paused ? T('Go on') : T('Start · click'))}</button> ` +
        `<button type="button" class="btn ghost" data-a="opts">${esc(T('Options & keys'))}</button></p>`;
      return;
    }
    if (S.phase === 'done') { result(); return; }
    el.hidden = true;
  }
  function done() {
    S.phase = 'done'; S.firing = false;
    if (document.pointerLockElement === canvas) document.exitPointerLock();
    save();
    result();
  }
  const median = a => { const s = a.slice().sort((x, y) => x - y); return s.length ? s[s.length >> 1] : null; };
  function matchOff() {                    // how far off his corner you looked in the match (degrees)
    const t = D.t_kill - (D.his ?? 0.6), k = NM.atClamped(S.kp, t);
    if (!k) return null;
    const v = [k[0] - D.me[0], k[2] - D.me[2]], f = [Math.sin(D.me[3]), -Math.cos(D.me[3])], L = Math.hypot(...v) || 1;
    return Math.acos(Math.max(-1, Math.min(1, (v[0] * f[0] + v[1] * f[1]) / L))) / D2R;
  }
  function result() {
    const el = $('dr-panel'), his = D.his ?? null, times = S.reps.filter(v => v !== null);
    const beat = his === null ? times.length : times.filter(v => v < his).length;
    const best = times.length ? Math.min(...times) : null, med = median(times);
    const top = Math.max(his || 0, ...times, 0.3) * 1.15;
    const bars = S.reps.map((v, i) => `<div class="dr-bar"><span>${v === null ? T('miss') : v.toFixed(2)}</span>` +
      `<i class="${v === null ? 'miss' : (his === null || v < his) ? 'beat' : 'slow'}" style="height:${v === null ? 100 : Math.round(v / top * 100)}%"></i><small>${i + 1}</small></div>`).join('');
    const off = S.offs.length ? S.offs.reduce((a, b) => a + b, 0) / S.offs.length : null, mo = matchOff();
    const h = C.history || {}, meds = (h.medians || []).concat(med !== null ? [med] : []);
    el.hidden = false;
    el.innerHTML = `<div class="dr-res">
      <p class="muted small" translate="no">${esc(D.map)} · ${esc(D.where)} · ${esc(D.killer_agent)} · ${esc(D.weapon)}</p>
      <h2>${his !== null ? `${esc(T('You beat him'))} <span class="good">${beat} / ${S.reps.length}</span>` : `${esc(T('Kills'))} <span class="good">${times.length} / ${S.reps.length}</span>`}</h2>
      <div class="dr-nums"><div><b class="good">${best !== null ? best.toFixed(2) + ' s' : '–'}</b><small>${esc(T('your best'))}</small></div>
        <div><b>${med !== null ? med.toFixed(2) + ' s' : '–'}</b><small>${esc(T('your median'))}</small></div>
        <div><b class="bad">${his !== null ? his.toFixed(2) + ' s' : '–'}</b><small>${esc(T('his time'))}</small></div></div>
      <div class="dr-bars">${his !== null ? `<div class="dr-his-line" style="bottom:${Math.round(his / top * 100)}%"><span>${esc(T('his'))} ${his.toFixed(2)} s</span></div>` : ''}${bars}</div>
      <div class="dr-facts">
        <div><b>${esc(T('Your first shots'))}</b><p><span class="hd">${esc(T('head'))} ${S.firsts.head}</span> <span>${esc(T('body'))} ${S.firsts.body}</span> <span>${esc(T('legs'))} ${S.firsts.legs}</span> <span class="bad">${esc(T('missed'))} ${S.firsts.miss}</span></p></div>
        <div><b>${esc(T('Your crosshair when he appeared'))}</b><p>${off !== null ? `${esc(T('On average'))} ${Math.round(off)}° ${esc(T('off him'))}.` : '–'}${mo !== null ? ` ${esc(T('In the match:'))} ${Math.round(mo)}°.` : ''}</p></div>
        <div><b>${esc(T('Since the first time'))}</b><p>${meds.length > 1 ? `${esc(T('Median per session'))}: ${meds.slice(-5).map(m => m.toFixed(2)).join(' → ')} s` : esc(T('Your first session on this spot.'))}</p></div>
      </div>
      <p class="dr-btns">${C.next ? `<a class="btn primary" href="${esc(C.next)}">${esc(T('Next drill'))}</a>` : ''}
        <button type="button" class="btn ${C.next ? '' : 'primary'}" data-a="again">${esc(T('Again'))} (${esc(keyName('restart'))})</button>
        <a class="btn ghost" href="${esc(C.watch)}">${esc(T('Watch the real death in the replay'))}</a>
        <a href="${esc(C.list)}">${esc(T('Back to the list'))}</a></p>
      <p class="muted small" id="dr-saved">${C.can_save ? '' : esc(T('Not saved: this isn\'t your player.'))}</p></div>`;
  }
  async function save() {
    if (!C.can_save || S.saved || !S.reps.length) return;
    S.saved = true;
    const off = S.offs.length ? S.offs.reduce((a, b) => a + b, 0) / S.offs.length : null;
    try {
      const r = await fetch(C.runs_api, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({reps: S.reps, his: D.his ?? null, first: S.firsts, off})});
      const d = await r.json();
      if (r.ok && d.history) C.history = d.history;
      const el = $('dr-saved'); if (el) el.textContent = r.ok ? T('Saved.') : (d.error || '');
    } catch (e) {}
  }

  // ------------------------------------------------------------------------------------------ input
  async function lock() {
    try { const p = canvas.requestPointerLock({unadjustedMovement: true}); if (p && p.then) await p; }
    catch (e) { try { await canvas.requestPointerLock(); } catch (e2) {} }
  }
  function go() {
    if (S.phase === 'loading' || S.phase === 'error') return;
    lock();
    if (S.paused) {                         // a rep stopped by Esc starts again from the beginning
      S.paused = false;
      if (S.reps.length >= opt.reps) done(); else startRep();
      return;
    }
    if (S.phase === 'ready' || S.phase === 'done') { restart(); }
  }
  document.addEventListener('pointerlockchange', () => {
    if (document.pointerLockElement === canvas) return;
    S.firing = false; S.ads = false;
    if (['run', 'count', 'watch', 'between'].includes(S.phase)) {
      S.paused = true; S.phase = 'hold'; S.msg = '';
      panel(); hud(true);
    }
  });
  document.addEventListener('mousemove', e => {
    if (document.pointerLockElement !== canvas || S.phase === 'done') return;
    const k = YAW * (+C.sens || 0.4) / Math.max(0.25, +C.scale || 1) / zoom() * D2R;
    S.yaw += e.movementX * k;
    S.pitch = Math.max(-1.55, Math.min(1.55, S.pitch - e.movementY * k));
  });
  function act(code, down) {
    for (const a of KB.actionsOf(keys, code)) {
      if (a === 'shoot') { S.firing = down; if (down) shoot(); }
      else if (a === 'ads') S.ads = down && (gun.zoom || 1) > 1;
      else if (!down) continue;
      else if (a === 'reload') startReload();
      else if (a === 'restart') { if (document.pointerLockElement !== canvas) lock(); S.paused = false; restart(); }
      else if (a === 'next') { if (S.phase === 'between' && !S.paused) S.until = 0; }
      else if (a === 'watch') { if (document.pointerLockElement === canvas || S.phase === 'done') { if (S.phase === 'done') lock(); watch(); } }
      else if (a === 'full') { const el = $('dr'); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); else if (el.requestFullscreen) el.requestFullscreen().catch(() => {}); }
    }
  }
  const locked = () => document.pointerLockElement === canvas;
  const typing = e => /INPUT|TEXTAREA|SELECT/.test((e.target && e.target.tagName) || '');
  document.addEventListener('keydown', e => {
    if (typing(e) || !$('dr-opts').hidden) return;
    if (e.code === 'Escape') return;
    if (!locked() && !['restart', 'full', 'watch'].some(a => keys[a] && keys[a].includes(e.code))) return;
    if (KB.actionsOf(keys, e.code).length) e.preventDefault();
    if (!e.repeat) act(e.code, true);
  });
  document.addEventListener('keyup', e => { if (locked()) act(e.code, false); });
  canvas.addEventListener('mousedown', e => {
    if (!locked()) return;
    e.preventDefault();
    act(KB.codeOfMouse(e.button), true);
  });
  document.addEventListener('mouseup', e => { if (locked()) act(KB.codeOfMouse(e.button), false); });
  canvas.addEventListener('contextmenu', e => e.preventDefault());
  canvas.addEventListener('wheel', e => {
    if (!locked()) return;
    e.preventDefault();
    const c = e.deltaY < 0 ? 'WheelUp' : 'WheelDown';
    act(c, true); act(c, false);
  }, {passive: false});
  canvas.addEventListener('click', () => { if (!locked() && (S.phase === 'ready' || S.paused)) go(); });
  $('dr-panel').addEventListener('click', e => {
    const b = e.target.closest('[data-a]'); if (!b) return;
    if (b.dataset.a === 'go') go();
    else if (b.dataset.a === 'again') { lock(); restart(); }
    else if (b.dataset.a === 'opts') openOpts();
  });

  // ------------------------------------------------------------------------------------------ options and keys
  function openOpts() {
    const el = $('dr-opts');
    el.hidden = false;
    $('dr-o-speed').value = String(opt.speed); $('dr-o-heads').checked = !!opt.heads; $('dr-o-reps').value = String(opt.reps);
    KB.editor($('dr-keys'), {keys, defaults: C.defaults || keys, actions: C.actions, api: C.keys_api, onSave: k => { keys = k; panel(); }});
  }
  $('dr-opts').addEventListener('change', () => {
    opt.speed = +$('dr-o-speed').value || 1; opt.heads = $('dr-o-heads').checked; opt.reps = +$('dr-o-reps').value || 10;
    saveOpt(); hud(true);
  });
  $('dr-opts-x').addEventListener('click', () => { $('dr-opts').hidden = true; panel(); });

  // ------------------------------------------------------------------------------------------ start
  $('dr-info').innerHTML = `<b translate="no">${esc(D.map)} · ${esc(D.where || '?')}</b><small><span translate="no">${esc(D.killer_agent)} · ${esc(D.weapon)}</span>` +
    `${D.kwhere ? ' · ' + esc(T('from')) + ' <span translate="no">' + esc(D.kwhere) + '</span>' : ''}${D.first === 'killer' ? ' · ' + esc(T('he saw you first')) : ''}</small>`;
  $('dr-his').textContent = D.his !== null && D.his !== undefined ? D.his.toFixed(2) + ' s' : '–';
  if (C.anims && V().anims) V().anims(C.anims);
  V().setLayer({tick, models, objects, ready: () => camera()});
  V().setOpt('labels', false);
  panel();
  load();
  window.nexusDrill = {state: () => ({phase: S.phase, t: S.t, reps: S.reps.slice(), seen: S.seen, kill: !!S.kill, ammo: S.ammo,
                                      yaw: S.yaw, pitch: S.pitch, hp: S.hp, firsts: {...S.firsts}, paused: S.paused}),
                       hitboxes, aimAt: p => { const v = sub(p, eye()), L = Math.hypot(...v); S.yaw = Math.atan2(v[0], -v[2]); S.pitch = Math.asin(v[1] / L); },
                       shoot: () => { shoot(); }, start: () => { restart(); }, eye, keys: () => keys, act, models,
                       // for tests: stand dist metres in front of where he is at t (he faces you)
                       faceOff: (t, dist) => { const p = enemyAt(t), f = [Math.sin(p[3]), -Math.cos(p[3])];
                         D.me = [p[0] + f[0] * dist, p[1], p[2] + f[1] * dist, Math.atan2(-f[0], f[1])]; S.yaw = D.me[3]; }};      // for tests
})();
