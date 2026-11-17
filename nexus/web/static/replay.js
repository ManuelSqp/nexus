// Replay page (4.44): a match's replay inside the rebuilt 3D map (map3d.js), round by round. Players are drawn on
// top of the 3D view and on the radar; the camera looks from above, follows a player, or flies free (click the
// map). Comments are kept per match for the whole team (web/replayview.py).
(function () {
  'use strict';
  const C = window.NEXUS_MAP3D;
  if (!C || !C.replay) return;
  const $ = id => document.getElementById(id);
  const T = s => (window.vcT ? window.vcT(s) : s);
  const OURS = '#3ee6c1', THEIRS = '#ff5d6c', SPIKE = '#ffd166';
  const R_UTIL = {smoke: 4.4, slow: 3.5, damage: 3.3, wall: 2.0, recon: 2.5, trap: 1.2, orb: 2.5, flash: 1.2};
  const S = {round: null, d: null, t: 0, playing: false, speed: 1, cam: 'top', follow: null, names: true, util: true,
             height: 80, comments: [], loading: 0};
  const P = C.players, byI = {};
  P.forEach(p => { byI[p.i] = p; });
  const me = P.find(p => p.me) || P.find(p => p.ours) || P[0];
  S.follow = me ? me.i : null;
  const col = p => (p && p.ours ? OURS : THEIRS);
  const fmt = t => { t = Math.max(0, t); const m = Math.floor(t / 60), s = Math.floor(t % 60); return `${m}:${String(s).padStart(2, '0')}`; };

  // ------------------------------------------------------------------------------------------ data
  async function loadRound(i, t0 = 0) {
    const tok = ++S.loading;
    S.playing = false; syncPlay();
    $('rv-msg').hidden = false; $('rv-msg').textContent = T('Loading the round…');
    try {
      const r = await fetch(`${C.round_api}${i}?pid=${C.pid}`, {credentials: 'same-origin'});
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
      if (tok !== S.loading) return;
      S.round = i; S.d = d; S.t = Math.min(t0, d.end);
      $('rv-time').max = String(d.end); $('rv-end').textContent = fmt(d.end);
      document.querySelectorAll('#rv-rounds [data-r]').forEach(b => b.classList.toggle('on', +b.dataset.r === i));
      $('rv-msg').hidden = true;
      feed(); comments(); ui(true);
      try { history.replaceState(null, '', `?round=${i}`); } catch (e) {}
    } catch (e) { $('rv-msg').textContent = e.message; }
  }
  function at(path, t) {                // [x, y, z, yaw] at time t (between two samples), or null
    if (!path || !path.length || t < path[0][0] - 0.5 || t > path[path.length - 1][0] + 0.25) return null;
    let lo = 0, hi = path.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (path[m][0] <= t) lo = m; else hi = m; }
    const a = path[lo], b = path[hi], f = b[0] > a[0] ? Math.min(1, Math.max(0, (t - a[0]) / (b[0] - a[0]))) : 0;
    let dy = b[4] - a[4]; if (dy > Math.PI) dy -= 2 * Math.PI; if (dy < -Math.PI) dy += 2 * Math.PI;
    return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f, a[4] + dy * f];
  }
  const deadAt = i => { const k = S.d && S.d.kills.find(k => k.victim === i); return k ? k.t : Infinity; };

  // ------------------------------------------------------------------------------------------ the clock and the camera
  function tick(dt) {
    if (!S.d) return;
    if (S.playing) {
      S.t += dt * S.speed;
      if (S.t >= S.d.end) { S.t = S.d.end; S.playing = false; syncPlay(); }
      ui();
    }
    camera();
  }
  function bounds() {
    const M = window.nexusMap3D.map();
    if (!M || !M.cells || !M.cells.length) return null;
    if (M._b) return M._b;
    let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
    for (const c of M.cells) { x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]); z0 = Math.min(z0, c[1]); z1 = Math.max(z1, c[1]); }
    M._b = {x: (x0 + x1 + 1) / 2 * M.cell, z: (z0 + z1 + 1) / 2 * M.cell, w: (x1 - x0 + 1) * M.cell, h: (z1 - z0 + 1) * M.cell};
    return M._b;
  }
  function camera() {
    const V = window.nexusMap3D;
    if (S.cam === 'top') {
      const b = bounds(); if (!b) return;
      V.view({x: b.x, z: b.z, y: S.height, yaw: 0, pitch: -1.5, fly: true});
    } else if (S.cam === 'follow' && S.d) {
      const p = at(S.d.paths[S.follow], Math.min(S.t, deadAt(S.follow)));
      if (p) V.view({x: p[0], y: p[1], z: p[2], yaw: p[3], pitch: -0.08, fly: true});
    }
  }

  // ------------------------------------------------------------------------------------------ utility shapes (4.45)
  const MIN_LIFE = 0.9;                 // shorter than this: an ability's targeting or a flicker, not placed utility
  function live(u, t) {
    if (u.t0 > t || (u.t1 !== null && u.t1 < t)) return false;
    return u.type === 'flash' || u.t1 === null || u.t1 - u.t0 >= MIN_LIFE;
  }
  // Smoke colours per agent (also their codenames in the replay file); everything else uses the utility type's colour.
  const SMOKE = {omen: [0.32, 0.25, 0.46], wraith: [0.32, 0.25, 0.46], brimstone: [0.86, 0.56, 0.40], sarge: [0.86, 0.56, 0.40],
                 viper: [0.38, 0.68, 0.32], pandemic: [0.38, 0.68, 0.32], astra: [0.58, 0.38, 0.74], rift: [0.58, 0.38, 0.74],
                 harbor: [0.30, 0.56, 0.82], mage: [0.30, 0.56, 0.82], clove: [0.96, 0.82, 0.90], smonk: [0.96, 0.82, 0.90],
                 miks: [0.62, 0.88, 0.66], jett: [0.88, 0.92, 0.97], wushu: [0.88, 0.92, 0.97], cypher: [0.86, 0.88, 0.92], gumshoe: [0.86, 0.88, 0.92]};
  const SMOKE_DEFAULT = [0.80, 0.82, 0.86];
  const hex = h => { const n = parseInt(h.slice(1), 16); return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]; };
  function utilColor(u) {
    if (u.type === 'smoke') return SMOKE[(u.agent || '').toLowerCase()] || SMOKE_DEFAULT;
    return hex(C.util_col[u.type] || '#cccccc');
  }
  function objects() {                     // 3D utility for map3d.js (the walls hide them)
    if (!S.d || !S.util) return [];
    const out = [];
    for (const u of S.d.util) {
      if (!live(u, S.t)) continue;
      const y = u.y !== null ? u.y : 0, col = utilColor(u), seed = (u.x * 7.3 + u.z * 3.1) % 50;
      if (u.type === 'smoke') out.push({x: u.x, y: y + 2.4, z: u.z, r: R_UTIL.smoke, sc: [1, 0.9, 1], col, a: 0.88, seed});
      else if (u.type === 'damage' || u.type === 'slow') out.push({x: u.x, y: y + 0.06, z: u.z, r: R_UTIL[u.type], sc: [1, 0.035, 1], col, a: 0.55, seed, cloudy: false});
      else if (u.type === 'wall') out.push({x: u.x, y: y + 2, z: u.z, r: 2, sc: [0.35, 1, 0.35], col, a: 0.6, seed, cloudy: false});
      else out.push({x: u.x, y: y + 1, z: u.z, r: 0.35, col, a: 0.95, seed, cloudy: false});
    }
    return out;
  }
  function drawUtil(g, project, u, dpr) {    // the agent's name over his utility (the shapes are 3D now)
    if (!S.names || !u.agent) return;
    const y = u.y !== null ? u.y : 0;
    const s = project(u.x, y + (u.type === 'smoke' ? R_UTIL.smoke * 0.95 + 2.6 : 2.2), u.z);
    if (!s) return;
    g.font = `600 ${Math.round(10.5 * dpr)}px system-ui, sans-serif`; g.textAlign = 'center';
    g.lineWidth = 3 * dpr; g.strokeStyle = 'rgba(0,0,0,.7)'; g.strokeText(u.agent, s.x, s.y);
    g.fillStyle = '#fff'; g.fillText(u.agent, s.x, s.y);
  }

  // ------------------------------------------------------------------------------------------ 4.48: agent models
  const rgb = h => hex(h);
  function models() {                      // the players as their agents (map3d.js draws them; walls hide them)
    if (!S.d || !C.agents) return [];
    const out = [];
    for (const [i, path] of Object.entries(S.d.paths)) {
      if (S.t > deadAt(+i)) continue;
      if (S.cam === 'follow' && +i === S.follow) continue;
      const p = at(path, S.t); if (!p) continue;
      const pl = byI[i], url = C.agents[pl.agent];
      if (!url) continue;
      out.push({key: +i, url, x: p[0], y: p[1], z: p[2], yaw: p[3], col: rgb(col(pl)).map(c => c * 0.85 + 0.1)});
    }
    return out;
  }
  const headOf = p => [p[0], p[1] + 1.9, p[2]];

  // ------------------------------------------------------------------------------------------ drawing
  function draw(g, project, w, h, dpr) {
    if (!S.d) return;
    g.lineJoin = 'round';                       // no spikes on the outlined text ("M")
    const t = S.t, d = S.d;
    if (S.util) for (const u of d.util) if (live(u, t)) drawUtil(g, project, u, dpr);
    for (const k of d.kills) {
      if (k.t > t) continue;
      const s = project(k.x, k.y + 0.1, k.z); if (!s) continue;
      const r = 6 * dpr, v = byI[k.victim];
      g.strokeStyle = col(v); g.lineWidth = 3 * dpr;
      g.beginPath(); g.moveTo(s.x - r, s.y - r); g.lineTo(s.x + r, s.y + r); g.moveTo(s.x + r, s.y - r); g.lineTo(s.x - r, s.y + r); g.stroke();
    }
    for (const sp of d.spike) {
      if (sp.t > t || sp.kind !== 'plant') continue;
      const s = project(sp.x, sp.y + 0.3, sp.z); if (!s) continue;
      const r = 8 * dpr; g.fillStyle = SPIKE; g.strokeStyle = '#000'; g.lineWidth = 1.5 * dpr;
      g.beginPath(); g.moveTo(s.x, s.y - r); g.lineTo(s.x + r, s.y); g.lineTo(s.x, s.y + r); g.lineTo(s.x - r, s.y); g.closePath(); g.fill(); g.stroke();
    }
    g.textAlign = 'center'; g.font = `650 ${Math.round(12 * dpr)}px system-ui, sans-serif`;
    const list = [];
    for (const [i, path] of Object.entries(d.paths)) {
      if (t > deadAt(+i)) continue;
      if (S.cam === 'follow' && +i === S.follow) continue;          // you're looking through his eyes
      const p = at(path, t); if (!p) continue;
      const s = project(p[0], p[1] + 0.2, p[2]); if (!s) continue;
      list.push([s, p, byI[i]]);
    }
    list.sort((a, b) => b[0].d - a[0].d);                           // far ones first
    const V = window.nexusMap3D, xray = V.opt().xray, eye = V.eye();
    for (const [s, p, pl] of list) {
      const hidden = !xray && !V.visible(eye, headOf(p)) && !V.visible(eye, [p[0], p[1] + 1.1, p[2]]);
      let top = s.y;
      if (V.drawnModel(pl.i) && s.px >= 9) {         // 4.48: drawn as his agent (close enough to see): the name above the head
        const hd = project(p[0], p[1] + 2.25, p[2]);
        if (!hd || hidden) continue;
        top = hd.y + 5 * dpr;
      } else {
        if (hidden) continue;
        const r = Math.min(16 * dpr, Math.max(5 * dpr, 0.45 * s.px));
        const f = project(p[0] + Math.sin(p[3]) * 1.4, p[1] + 0.2, p[2] - Math.cos(p[3]) * 1.4);
        if (f) { g.strokeStyle = col(pl); g.lineWidth = 2.5 * dpr; g.beginPath(); g.moveTo(s.x, s.y); g.lineTo(f.x, f.y); g.stroke(); }
        g.fillStyle = col(pl); g.strokeStyle = pl.me ? '#fff' : 'rgba(0,0,0,.7)'; g.lineWidth = (pl.me ? 2.5 : 1.5) * dpr;
        g.beginPath(); g.arc(s.x, s.y, r, 0, 2 * Math.PI); g.fill(); g.stroke();
        top = s.y - r;
      }
      if (S.names) {
        const label = `${pl.agent} · ${pl.name}`;
        g.lineWidth = 3 * dpr; g.strokeStyle = 'rgba(0,0,0,.75)'; g.strokeText(label, s.x, top - 5 * dpr);
        g.fillStyle = pl.me ? '#ffd166' : '#fff'; g.fillText(label, s.x, top - 5 * dpr);
      }
    }
  }
  function radar(g, toR, yaw, S2) {
    if (!S.d) return;
    const t = S.t, d = S.d;
    const k = toR(1, 0)[0] - toR(0, 0)[0];
    if (S.util) for (const u of d.util) {
      if (!live(u, t)) continue;
      const [x, y] = toR(u.x, u.z);
      const uc = utilColor(u);
      g.globalAlpha = 0.55; g.fillStyle = `rgb(${uc[0] * 255 | 0},${uc[1] * 255 | 0},${uc[2] * 255 | 0})`;
      g.beginPath(); g.arc(x, y, Math.max(2, (R_UTIL[u.type] || 1.5) * k), 0, 2 * Math.PI); g.fill(); g.globalAlpha = 1;
    }
    for (const kl of d.kills) {
      if (kl.t > t) continue;
      const [x, y] = toR(kl.x, kl.z); g.strokeStyle = col(byI[kl.victim]); g.lineWidth = 2;
      g.beginPath(); g.moveTo(x - 4, y - 4); g.lineTo(x + 4, y + 4); g.moveTo(x + 4, y - 4); g.lineTo(x - 4, y + 4); g.stroke();
    }
    for (const [i, path] of Object.entries(d.paths)) {
      if (t > deadAt(+i)) continue;
      const p = at(path, t); if (!p) continue;
      const [x, y] = toR(p[0], p[2]), pl = byI[i];
      g.fillStyle = col(pl); g.strokeStyle = pl.me ? '#fff' : '#000'; g.lineWidth = 1.5;
      g.beginPath(); g.arc(x, y, 5, 0, 2 * Math.PI); g.fill(); g.stroke();
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.sin(p[3]) * 10, y - Math.cos(p[3]) * 10); g.strokeStyle = col(pl); g.stroke();
    }
  }

  // ------------------------------------------------------------------------------------------ the page around it
  let lastUi = 0;
  function ui(force) {
    const now = performance.now();
    if (!force && now - lastUi < 120) return;
    lastUi = now;
    $('rv-time').value = String(S.t); $('rv-clock').textContent = fmt(S.t);
    $('rv-c-at').textContent = `${T('Round')} ${S.round + 1} · ${fmt(S.t)}`;
    board(); feedNow();
  }
  function board() {
    const html = side => P.filter(p => p.ours === side).map(p => {
      const dead = S.t > deadAt(p.i);
      return `<button type="button" class="rv-p ${dead ? 'dead' : ''} ${S.cam === 'follow' && S.follow === p.i ? 'on' : ''}" data-p="${p.i}" style="--c:${col(p)}">` +
             `<b translate="no">${esc(p.agent)}</b> <span translate="no">${esc(p.name)}</span></button>`;
    }).join('');
    $('rv-ours').innerHTML = html(true); $('rv-theirs').innerHTML = html(false);
  }
  function feed() {
    const d = S.d;
    $('rv-feed').innerHTML = d.kills.map(k => {
      const a = byI[k.killer], v = byI[k.victim];
      const more = review(k);
      return `<button type="button" class="rv-k" data-t="${Math.max(0, k.t - 3)}" data-kt="${k.t}"><span class="tm">${fmt(k.t)}</span> ` +
             `<b style="color:${col(a)}" translate="no">${a ? esc(a.name) : '–'}</b> → <b style="color:${col(v)}" translate="no">${esc(v ? v.name : '')}</b>` +
             (k.weapon ? ` <span class="muted" translate="no">${esc(k.weapon)}</span>` : '') +
             (more ? `<span class="rv-why">${more}</span>` : '') + '</button>';
    }).join('') + d.spike.map(s => `<button type="button" class="rv-k" data-t="${Math.max(0, s.t - 3)}" data-kt="${s.t}"><span class="tm">${fmt(s.t)}</span> ` +
             `<b style="color:${SPIKE}">${T(s.kind === 'plant' ? 'Spike planted' : 'Spike defused')}</b>${s.site ? ' ' + esc(s.site) : ''}</button>`).join('');
    feedNow();
  }
  // 4.48: where it happened (the game's callouts) and, with line of sight, who saw whom first
  function review(k) {
    const parts = [];
    if (k.where) parts.push(`<span translate="no">${esc(k.where)}</span>`);
    const r = k.review;
    if (r) {
      if (r.unseen && r.killer_saw !== null) parts.push(`<span class="bad">${T('never saw the killer')}</span>`);
      else if (r.first === 'killer' && r.victim_saw !== null) parts.push(`<span class="bad">${T('the enemy saw him first')}</span> <span translate="no">(+${(r.killer_saw - r.victim_saw).toFixed(1)} s)</span>`);
      else if (r.first === 'victim') parts.push(`<span>${T('he saw the killer first')}</span>` + (r.killer_saw !== null ? ` <span translate="no">(+${(r.victim_saw - r.killer_saw).toFixed(1)} s)</span>` : ''));
      else if (r.first === 'same') parts.push(`<span>${T('saw each other at once')}</span>`);
      if (r.open_to > 1) parts.push(`<span class="bad">${T('open to')} <span translate="no">${r.open_to}</span></span>`);
    }
    return parts.join(' · ');
  }
  function feedNow() {
    document.querySelectorAll('#rv-feed .rv-k').forEach(b => b.classList.toggle('past', +b.dataset.kt <= S.t));
  }
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  function syncPlay() { $('rv-play').textContent = S.playing ? T('Pause') : T('Play'); }

  // ------------------------------------------------------------------------------------------ comments
  async function loadComments() {
    try {
      const r = await fetch(C.comments_api, {credentials: 'same-origin'});
      S.comments = (await r.json()).comments || [];
    } catch (e) { S.comments = []; }
    comments(); roundBadges();
  }
  function comments() {
    const mine = S.comments.filter(c => c.round === S.round);
    $('rv-clist').innerHTML = mine.length ? mine.map(c =>
      `<div class="rv-c"><button type="button" class="tm" data-t="${c.t}">${fmt(c.t)}</button> <b translate="no">${esc(c.user)}</b> ` +
      `<span>${esc(c.text)}</span>${c.mine ? ` <button type="button" class="rv-del" data-del="${c.id}" title="${T('Delete')}">×</button>` : ''}</div>`).join('')
      : `<p class="muted small" style="margin:0">${T('No comments on this round yet.')}</p>`;
  }
  function roundBadges() {
    document.querySelectorAll('#rv-rounds [data-r]').forEach(b => {
      const n = S.comments.filter(c => c.round === +b.dataset.r).length;
      b.classList.toggle('cm', n > 0); b.title = n ? `${n} ${T(n === 1 ? 'comment' : 'comments')}` : '';
    });
  }
  async function addComment() {
    const text = $('rv-c-text').value.trim();
    if (!text || S.round === null) return;
    $('rv-c-add').disabled = true;
    try {
      const r = await fetch(C.comments_api, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
                                             body: JSON.stringify({round: S.round, t: S.t, text})});
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
      S.comments.push(d.comment); S.comments.sort((a, b) => a.round - b.round || a.t - b.t);
      $('rv-c-text').value = ''; comments(); roundBadges();
    } catch (e) { alertLine(e.message); }
    $('rv-c-add').disabled = false;
  }
  async function delComment(id) {
    try {
      const u = C.comments_api.replace('/comments?', `/comments/${encodeURIComponent(id)}?`);
      const r = await fetch(u, {method: 'DELETE', credentials: 'same-origin'});
      if (!r.ok) throw new Error((await r.json()).error || ('HTTP ' + r.status));
      S.comments = S.comments.filter(c => c.id !== id); comments(); roundBadges();
    } catch (e) { alertLine(e.message); }
  }
  function alertLine(msg) { $('rv-c-err').textContent = msg; setTimeout(() => { $('rv-c-err').textContent = ''; }, 5000); }

  // ------------------------------------------------------------------------------------------ controls
  function seek(t) { if (!S.d) return; S.t = Math.max(0, Math.min(S.d.end, t)); ui(true); }
  function setCam(c) {
    S.cam = c;
    document.querySelectorAll('[data-cam]').forEach(b => b.classList.toggle('on', b.dataset.cam === c));
    if (c === 'free' && S.d) {                       // start free flight a bit above where the camera was
      const st = window.nexusMap3D.state().me;
      window.nexusMap3D.view({y: Math.min(st.y, 25), pitch: -0.5, fly: true});
    }
    board();
  }
  $('rv-play').addEventListener('click', () => { if (S.d && S.t >= S.d.end) S.t = 0; S.playing = !S.playing; syncPlay(); });
  $('rv-time').addEventListener('input', e => seek(+e.target.value));
  $('rv-speed').addEventListener('change', e => { S.speed = +e.target.value || 1; });
  $('rv-names').addEventListener('change', e => { S.names = e.target.checked; });
  $('rv-util').addEventListener('change', e => { S.util = e.target.checked; });
  document.querySelectorAll('[data-cam]').forEach(b => b.addEventListener('click', () => setCam(b.dataset.cam)));
  $('rv-zoom-in').addEventListener('click', () => { S.height = Math.max(20, S.height / 1.25); });
  $('rv-zoom-out').addEventListener('click', () => { S.height = Math.min(220, S.height * 1.25); });
  $('rv-rounds').addEventListener('click', e => { const b = e.target.closest('[data-r]'); if (b && !b.disabled) loadRound(+b.dataset.r); });
  document.addEventListener('click', e => {
    const p = e.target.closest('[data-p]'); if (p) { S.follow = +p.dataset.p; setCam('follow'); return; }
    const k = e.target.closest('[data-t]'); if (k && (k.closest('#rv-feed') || k.closest('#rv-clist'))) { seek(+k.dataset.t); return; }
    const del = e.target.closest('[data-del]'); if (del) delComment(del.dataset.del);
  });
  $('rv-c-add').addEventListener('click', addComment);
  $('rv-c-text').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); addComment(); } });
  $('rv-c-text').addEventListener('focus', () => { if (S.playing) { S.playing = false; syncPlay(); } });
  document.addEventListener('keydown', e => {
    if (document.pointerLockElement || /INPUT|TEXTAREA|SELECT/.test((e.target.tagName || ''))) return;
    if (e.code === 'Space') { e.preventDefault(); $('rv-play').click(); }
    else if (e.code === 'ArrowRight') { e.preventDefault(); seek(S.t + 5); }
    else if (e.code === 'ArrowLeft') { e.preventDefault(); seek(S.t - 5); }
    else if (e.code === 'PageDown' || e.code === 'Period') { const n = C.rounds.find(r => r.i > S.round && r.has); if (n) loadRound(n.i); }
    else if (e.code === 'PageUp' || e.code === 'Comma') { const n = [...C.rounds].reverse().find(r => r.i < S.round && r.has); if (n) loadRound(n.i); }
  });
  document.addEventListener('pointerlockchange', () => { if (document.pointerLockElement) setCam('free'); });

  const layer = {tick, draw, radar, models, objects, ready: () => { camera(); }};
  window.nexusMap3D.setLayer(layer);
  window.nexusMap3D.setOpt('labels', false);
  loadRound(C.start);
  loadComments();
  setCam('top');
  window.nexusReplay = {state: () => ({round: S.round, t: S.t, cam: S.cam, follow: S.follow, playing: S.playing, players: S.d ? Object.keys(S.d.paths).length : 0,
                                        comments: S.comments.length}), seek, loadRound, at, setCam};   // for tests
})();
