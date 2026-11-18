// Replay page (4.44; 4.49: controlled like the game's own replays). A match's replay inside the 3D map (map3d.js),
// round by round. Two camera modes, switched with V: Player (through a player's eyes; 1–0 or a click on his
// portrait picks him, left/right click on the view the next/previous one) and Free camera (WASD, Space/E up,
// Ctrl/Q down, Shift faster, drag to look, the wheel moves forward). P plays (Space too in player view; 4.50: the
// agents are animated and hold their guns, dead ones lie where they fell), ← → jump 5 s, , . change the round, T hides
// the controls, N opens the Combat Report (kills with callouts and who saw whom first, your deaths with the
// sightline, the utility check, the team's comments, kept per match for the whole team: web/replayview.py).
(function () {
  'use strict';
  const C = window.NEXUS_MAP3D;
  if (!C || !C.replay) return;
  const $ = id => document.getElementById(id);
  const T = s => (window.vcT ? window.vcT(s) : s);
  const OURS = '#3ee6c1', THEIRS = '#ff5d6c', SPIKE = '#ffd166';
  const R_UTIL = {smoke: 4.4, slow: 3.5, damage: 3.3, wall: 2.0, recon: 2.5, trap: 1.2, orb: 2.5, flash: 1.2};
  const S = {round: null, d: null, t: 0, playing: false, speed: 1, mode: 'free', follow: null, names: true, util: true,
             comments: [], loading: 0, ui: true, report: false, tab: 'round', sight: null,
             cam: {x: 0, y: 40, z: 0, yaw: 0, pitch: -1.1}, keys: new Set()};
  const P = C.players, byI = {};
  P.forEach(p => { byI[p.i] = p; });
  const me = P.find(p => p.me) || P.find(p => p.ours) || P[0];
  S.follow = me ? me.i : null;
  // the order of the keys 1–0 and of the portraits: your team, then the enemy
  const ORDER = [...P.filter(p => p.ours), ...P.filter(p => !p.ours)];
  const col = p => (p && p.ours ? OURS : THEIRS);
  const fmt = t => { t = Math.max(0, t); const m = Math.floor(t / 60), s = Math.floor(t % 60); return `${m}:${String(s).padStart(2, '0')}`; };
  const short = a => String(a || '?').replace(/[^A-Za-z/]/g, '').slice(0, 3);

  // ------------------------------------------------------------------------------------------ data
  async function loadRound(i, t0 = 0) {
    const tok = ++S.loading;
    S.playing = false; syncPlay(); S.sight = null;
    $('rv-msg').hidden = false; $('rv-msg').textContent = T('Loading the round…');
    try {
      const r = await fetch(`${C.round_api}${i}?pid=${C.pid}`, {credentials: 'same-origin'});
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
      if (tok !== S.loading) return;
      prep(d);
      S.round = i; S.d = d; S.t = Math.min(t0, d.end);
      $('rv-time').max = String(d.end); $('rv-end').textContent = fmt(d.end);
      document.querySelectorAll('#rv-rounds [data-r]').forEach(b => b.classList.toggle('on', +b.dataset.r === i));
      $('rv-msg').hidden = true;
      feed(); marks(); deaths(); comments(); score(); ui(true);
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
  const FLY = 9, FAST = 3, LOOK = 0.0045;
  function tick(dt) {
    if (!S.d) return;
    if (S.playing) {
      S.t += dt * S.speed;
      if (S.t >= S.d.end) { S.t = S.d.end; S.playing = false; syncPlay(); }
      ui();
    }
    if (S.mode === 'free') fly(dt);
    camera();
  }
  function fly(dt) {                    // the free camera: WASD along the view, Space/E up, Ctrl/Q down
    const k = S.keys, c = S.cam, v = FLY * (k.has('ShiftLeft') || k.has('ShiftRight') ? FAST : 1) * dt;
    const fx = Math.sin(c.yaw) * Math.cos(c.pitch), fy = Math.sin(c.pitch), fz = -Math.cos(c.yaw) * Math.cos(c.pitch);
    const rx = Math.cos(c.yaw), rz = Math.sin(c.yaw);
    const f = (k.has('KeyW') ? 1 : 0) - (k.has('KeyS') ? 1 : 0), r = (k.has('KeyD') ? 1 : 0) - (k.has('KeyA') ? 1 : 0);
    const u = (k.has('KeyE') || k.has('Space') ? 1 : 0) - (k.has('KeyQ') || k.has('ControlLeft') || k.has('ControlRight') ? 1 : 0);
    c.x += (fx * f + rx * r) * v; c.y += (fy * f + u) * v; c.z += (fz * f + rz * r) * v;
  }
  function bounds() {
    const M = window.nexusMap3D.map();
    if (!M || !M.cells || !M.cells.length) return null;
    if (M._b) return M._b;
    let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity, y = 0;
    for (const c of M.cells) { x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]); z0 = Math.min(z0, c[1]); z1 = Math.max(z1, c[1]); y += c[2]; }
    M._b = {x: (x0 + x1 + 1) / 2 * M.cell, z: (z0 + z1 + 1) / 2 * M.cell, w: (x1 - x0 + 1) * M.cell, h: (z1 - z0 + 1) * M.cell, y: y / M.cells.length};
    return M._b;
  }
  const EYE = 1.6;                      // map3d.js puts the eyes this far above the position it's given
  function camera() {
    const V = window.nexusMap3D;
    if (S.mode === 'player' && S.d) {
      const p = at(S.d.paths[S.follow], Math.min(S.t, deadAt(S.follow)));
      if (p) V.view({x: p[0], y: p[1], z: p[2], yaw: p[3], pitch: 0, fly: true});
    } else {
      const c = S.cam;
      V.view({x: c.x, y: c.y - EYE, z: c.z, yaw: c.yaw, pitch: c.pitch, fly: true});
    }
  }
  function overview() {                 // the free camera's first place: above the map, looking down at it
    const b = bounds(); if (!b) return;
    Object.assign(S.cam, {x: b.x, y: b.y + Math.max(b.w, b.h) * 0.62, z: b.z + Math.max(b.w, b.h) * 0.42, yaw: 0, pitch: -0.95});
  }
  function behind(i) {                  // the free camera a few metres behind and above a player
    const p = S.d && at(S.d.paths[i], Math.min(S.t, deadAt(i)));
    if (!p) return;
    Object.assign(S.cam, {x: p[0] - Math.sin(p[3]) * 6, y: p[1] + 5, z: p[2] + Math.cos(p[3]) * 6, yaw: p[3], pitch: -0.45});
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
      const pl = byI[i], url = C.agents[pl.agent];
      if (!url) continue;
      const c = rgb(col(pl)).map(c => c * 0.85 + 0.1);
      if (S.t > deadAt(+i)) {                   // 4.50: the body stays where he fell until the round is over
        if (S.mode === 'player' && +i === S.follow) continue;      // (not under the camera of his own eyes)
        const b = body(+i, path);
        if (b) out.push({key: +i, url, col: c.map(v => v * 0.7), ...b});
        continue;
      }
      if (S.mode === 'player' && +i === S.follow) continue;
      const p = at(path, S.t); if (!p) continue;
      const o = {key: +i, url, x: p[0], y: p[1], z: p[2], yaw: p[3], col: c};
      if (C.anims) { const m = motion(path, S.t, p); o.anim = m.anim; o.y += m.lift; o.gun = gunOf(+i, S.t); }
      out.push(o);
    }
    return out;
  }

  // ------------------------------------------------------------------------------------------ 4.50: how they move
  // The animations come from the game (stats/agentanim.py); which ones play is read from the replay: how fast and
  // which way a player moves compared to where he looks (walk/run in eight directions, blended), up or down fast
  // (in the air), lower than the floor around him (crouching). The legs' phase follows the distance walked, so the
  // feet don't slide and scrubbing back and forth gives the same pose. The upper body holds the gun.
  const GAIT = {walk: 3.4, run: 5.5, cwalk: 1.8};      // m/s each clip moves at (measured from the clips)
  const DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  function prep(d) {                                    // per sample: the distance walked so far, the floor around (±2 s)
    for (const path of Object.values(d.paths)) {
      let s = 0;
      for (let k = 0; k < path.length; k++) {
        if (k) s += Math.hypot(path[k][1] - path[k - 1][1], path[k][3] - path[k - 1][3]);
        path[k][5] = s;
      }
      for (let k = 0; k < path.length; k++) {
        const ys = [];
        for (let j = Math.max(0, k - 10); j <= Math.min(path.length - 1, k + 10); j++) ys.push(path[j][2]);
        ys.sort((a, b) => a - b); path[k][6] = ys[ys.length >> 1];
      }
    }
  }
  function extra(path, t, n) {                          // a prep() value at time t
    if (!path || !path.length) return 0;
    if (t <= path[0][0]) return path[0][n] || 0;
    if (t >= path[path.length - 1][0]) return path[path.length - 1][n] || 0;
    let lo = 0, hi = path.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (path[m][0] <= t) lo = m; else hi = m; }
    const a = path[lo], b = path[hi], f = b[0] > a[0] ? (t - a[0]) / (b[0] - a[0]) : 0;
    return (a[n] || 0) + ((b[n] || 0) - (a[n] || 0)) * f;
  }
  const clamp01 = v => Math.max(0, Math.min(1, v));
  function motion(path, t, p) {                          // -> {anim: {lb, ub}, lift}
    const t0 = path[0][0], t1 = path[path.length - 1][0];
    const ta = Math.max(t0, t - 0.2), tb = Math.min(t1, t + 0.2), dt = tb - ta;
    let vx = 0, vy = 0, vz = 0;
    if (dt > 0.05) { const a = at(path, ta), b = at(path, tb); if (a && b) { vx = (b[0] - a[0]) / dt; vy = (b[1] - a[1]) / dt; vz = (b[2] - a[2]) / dt; } }
    const sp = Math.hypot(vx, vz), M = window.nexusMap3D.map(), hand = (M && M.hand) || 1;
    const f = [Math.sin(p[3]), -Math.cos(p[3])], r = [hand * f[1], -hand * f[0]];
    const ang = Math.atan2(vx * r[0] + vz * r[1], vx * f[0] + vz * f[1]);       // 0 forward, + to the right
    const s8 = ((ang / (Math.PI / 4)) % 8 + 8) % 8, i0 = Math.floor(s8), fr = s8 - i0;
    const d0 = DIRS[i0 % 8], d1 = DIRS[(i0 + 1) % 8];
    const walked = extra(path, t, 5), dip = extra(path, t, 6) - p[1];
    const air = clamp01((Math.abs(vy) - 1.5) / 1.5), g = 1 - air;
    const cr = sp < 3.2 && air < 0.5 ? clamp01((dip - 0.22) / 0.1) : 0;
    const wIdle = sp < 0.3 ? 1 : clamp01(1 - (sp - 0.3) / 0.9), wRun = clamp01((sp - 4.6) / 1.2), wWalk = Math.max(0, 1 - wIdle - wRun);
    const lb = [];
    const add = (name, secs, w) => { if (w > 0.001) lb.push([name, secs, w]); };
    add('idle', t, g * wIdle * (1 - cr)); add('crouch', t, g * wIdle * cr);
    for (const [kind, w] of [['walk', g * wWalk * (1 - cr)], ['cwalk', g * wWalk * cr], ['run', g * wRun]]) {
      const secs = walked / GAIT[kind];
      add(`${kind}_${d0}`, secs, w * (1 - fr)); add(`${kind}_${d1}`, secs, w * fr);
    }
    add('fall', t, air);
    if (!lb.length) lb.push(['idle', t, 1]);
    return {anim: {lb, ub: [['hold', t, 1]]}, lift: cr * Math.max(0, dip)};
  }
  function body(i, path) {                               // a dead player: where he fell and how (away from the killer)
    const k = S.d.kills.find(k => k.victim === i);
    if (!k) return null;
    const p = at(path, Math.min(k.t, path[path.length - 1][0])) || [k.x, k.y, k.z, 0];
    const o = {x: p[0], y: p[1], z: p[2], yaw: p[3]};
    if (!C.anims) return null;                           // without animations a standing body would look alive
    let clip = 'death_front';
    const kp = k.killer !== null && k.killer !== undefined ? at(S.d.paths[k.killer], k.t) : null;
    if (kp) {
      const M = window.nexusMap3D.map(), hand = (M && M.hand) || 1;
      const f = [Math.sin(p[3]), -Math.cos(p[3])], r = [hand * f[1], -hand * f[0]];
      const dx = kp[0] - p[0], dz = kp[2] - p[2], fw = dx * f[0] + dz * f[1], rt = dx * r[0] + dz * r[1];
      if (Math.abs(fw) >= Math.abs(rt)) clip = fw > 0 ? 'death_back' : 'death_front';     // pushed away from the killer
      else clip = rt > 0 ? 'death_left' : 'death_right';
    }
    o.anim = {lb: [[clip, S.t - k.t, 1]], ub: null};
    return o;
  }
  function gunOf(i, t) {                                 // the gun in his hands: bought, then what he killed with
    if (!C.guns) return null;
    const seq = (S.d.guns || {})[i];
    let name = 'Classic';
    if (seq) for (const [t0, w] of seq) if (t0 <= t) name = w;
    return C.guns[name] || null;
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
      if (window.nexusMap3D.drawnModel(k.victim)) continue;          // 4.50: his body lies there (the X stays on the radar)
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
      if (S.mode === 'player' && +i === S.follow) continue;         // you're looking through his eyes
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
    if (!force && now - lastUi < 100) return;
    lastUi = now;
    const end = S.d ? S.d.end || 1 : 1, pc = Math.min(100, S.t / end * 100);
    $('rv-time').value = String(S.t); $('rv-clock').textContent = fmt(S.t); $('rv-rclock').textContent = fmt(S.t);
    $('rv-fill').style.width = pc + '%'; $('rv-head').style.left = pc + '%';
    $('rv-c-at').textContent = `${T('Round')} ${S.round + 1} · ${fmt(S.t)}`;
    teams(); pov(); feedNow();
    $('rv-where').textContent = (S.mode === 'player' ? T('Player view') : T('Free camera')) + (where() ? ' · ' + where() : '');
  }
  function where() {
    const V = window.nexusMap3D, e = V.state().me;
    return V.zoneAt ? V.zoneAt(e.x, e.y, e.z) : '';
  }
  // 4.50: the agents' portraits along the top like in the game (dead ones greyed out); the icons come from
  // /agent-icon/ (valorant-api.com, cached on the server), the agent's first letters if there's none
  const face = p => `<img src="/agent-icon/${encodeURIComponent(p.agent || '')}" alt="" draggable="false" ` +
    `onerror="this.replaceWith(document.createTextNode(this.parentNode.dataset.s || ''))">`;
  function teams() {
    for (const [id, side] of [['rv-ours', true], ['rv-theirs', false]]) {
      const box = $(id);
      if (!box.dataset.built) {
        box.innerHTML = ORDER.filter(p => p.ours === side).map(p => {
          const n = ORDER.indexOf(p) + 1;
          return `<button type="button" class="rv-a" data-p="${p.i}" data-s="${esc(short(p.agent))}" style="--c:${col(p)}" ` +
                 `title="${esc(p.agent)} · ${esc(p.name)} (${n % 10})" translate="no">${face(p)}<i></i></button>`;
        }).join('');
        box.dataset.built = '1';
      }
      for (const b of box.querySelectorAll('.rv-a')) {
        const i = +b.dataset.p;
        b.classList.toggle('dead', S.t > deadAt(i));
        b.classList.toggle('on', S.mode === 'player' && S.follow === i);
      }
    }
  }
  let povFor = null;
  function pov() {
    const el = $('rv-pov'), p = byI[S.follow];
    el.hidden = !(S.mode === 'player' && p && S.ui);
    if (el.hidden) return;
    const dead = S.t > deadAt(p.i), key = `${p.i}:${dead}`;
    if (povFor === key) return;
    povFor = key;
    el.innerHTML = `<span class="rv-a ${dead ? 'dead' : ''}" style="--c:${col(p)}" data-s="${esc(short(p.agent))}" translate="no">${face(p)}<i></i></span>` +
      `<span><b translate="no">${esc(p.name)}</b><small><span translate="no">${esc(p.agent)}</span>${dead ? ' · ' + T('dead') : ''} · ${T('click: next player')}</small></span>`;
  }
  function score() {                   // rounds won before this one
    let a = 0, b = 0;
    for (const r of C.rounds) { if (r.i >= S.round) break; if (r.won) a++; else if (r.won === false) b++; }
    $('rv-s-ours').textContent = a; $('rv-s-theirs').textContent = b;
    $('rv-rlabel').textContent = `${T('Round')} ${S.round + 1}`;
  }
  function marks() {                   // the round's events over the timeline, like the game's: kills, deaths, ults, the spike
    const d = S.d, end = d.end || 1, out = [];
    const pos = t => `left:${Math.max(0, Math.min(100, t / end * 100))}%`;
    for (const k of d.kills) {
      const v = byI[k.victim], ours = v && !v.ours;                  // an enemy died: a kill for your team
      const mine = v && v.me;
      out.push(`<button type="button" class="mk" data-t="${Math.max(0, k.t - 3)}" style="${pos(k.t)};color:${ours ? '#4ade80' : '#ff5a6a'}${mine ? ';font-size:17px' : ''}" ` +
               `title="${fmt(k.t)} ${esc(byI[k.killer] ? byI[k.killer].name : '')} → ${esc(v ? v.name : '')}">${ours ? '◆' : '▮'}</button>`);
    }
    for (const [t, i, key] of d.casts || []) {
      if (key !== 'X') continue;
      const p = byI[i];
      out.push(`<button type="button" class="mk" data-t="${Math.max(0, t - 2)}" style="${pos(t)};color:#f5c76a" title="${fmt(t)} ${esc(p ? p.agent : '')}: ${T('ultimate')}">★</button>`);
    }
    for (const sp of d.spike) {
      out.push(`<button type="button" class="mk" data-t="${Math.max(0, sp.t - 3)}" style="${pos(sp.t)};color:${SPIKE}" title="${fmt(sp.t)} ${T(sp.kind === 'plant' ? 'Spike planted' : 'Spike defused')}">⬥</button>`);
    }
    $('rv-marks').innerHTML = out.join('');
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
  // 4.49: your deaths in this round, each with its sightline: the replay stops where the killer first had you
  function deaths() {
    const mine = S.d.kills.map((k, n) => [k, n]).filter(([k]) => byI[k.victim] && byI[k.victim].me);
    $('rv-deaths').innerHTML = mine.length ? mine.map(([k, n]) => {
      const a = byI[k.killer], r = k.review || {};
      return `<div class="rv-death"><b>${fmt(k.t)}</b> ${T('killed by')} <b style="color:${col(a)}" translate="no">${a ? esc(a.name) : '–'}</b>` +
        (k.where ? ` · <span translate="no">${esc(k.where)}</span>` : '') + `<span class="rv-why">${review(k) || ''}</span>` +
        `<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">` +
        (k.killer !== null && k.killer !== undefined ? `<button type="button" class="btn sm primary" data-sight="${n}">${T('Show the sightline')}</button>` : '') +
        `<button type="button" class="btn sm ghost" data-t="${Math.max(0, k.t - 3)}">${T('3 s before')}</button></div></div>`;
    }).join('') : `<p class="muted small" style="margin:0">${T('You didn\'t die in this round.')}</p>`;
  }
  function showSight(n) {
    const k = S.d.kills[n]; if (!k) return;
    const r = k.review || {}, back = r.killer_saw !== null && r.killer_saw !== undefined ? r.killer_saw : 1.5;
    S.sight = {a: k.killer, b: k.victim, until: k.t};
    S.playing = false; syncPlay();
    seek(k.t - back);
    S.mode = 'free'; behindPair(k.killer, k.victim); setMode('free');
  }
  function behindPair(a, b) {           // the free camera to the side of the line between killer and victim, looking at it
    const pa = at(S.d.paths[a], S.t), pb = at(S.d.paths[b], S.t);
    if (!pa || !pb) return;
    const mx = (pa[0] + pb[0]) / 2, mz = (pa[2] + pb[2]) / 2, dx = pb[0] - pa[0], dz = pb[2] - pa[2], L = Math.hypot(dx, dz) || 1;
    const nx = -dz / L, nz = dx / L, back = Math.max(8, L * 0.9);
    const x = mx + nx * back, z = mz + nz * back;
    Object.assign(S.cam, {x, y: Math.max(pa[1], pb[1]) + back * 0.55, z, yaw: Math.atan2(mx - x, -(mz - z)), pitch: -0.5});
  }
  function drawSight(g, project, dpr) {
    if (!S.sight || !S.d || S.t > S.sight.until + 0.3) return;
    const pa = at(S.d.paths[S.sight.a], S.t), pb = at(S.d.paths[S.sight.b], S.t);
    if (!pa || !pb) return;
    const a = project(pa[0], pa[1] + 1.55, pa[2]), b = project(pb[0], pb[1] + 1.3, pb[2]);
    if (!a || !b) return;
    const clear = window.nexusMap3D.visible([pa[0], pa[1] + 1.55, pa[2]], [pb[0], pb[1] + 1.3, pb[2]]);
    g.save(); g.lineWidth = 3 * dpr; g.strokeStyle = clear ? '#ff5a6a' : 'rgba(255,255,255,.45)';
    if (!clear) g.setLineDash([8 * dpr, 6 * dpr]);
    g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(b.x, b.y); g.stroke(); g.restore();
    g.font = `650 ${Math.round(12 * dpr)}px system-ui, sans-serif`; g.textAlign = 'center';
    const label = clear ? T('in sight') : T('no line of sight');
    g.lineWidth = 3 * dpr; g.strokeStyle = 'rgba(0,0,0,.75)'; g.strokeText(label, (a.x + b.x) / 2, (a.y + b.y) / 2 - 8 * dpr);
    g.fillStyle = '#fff'; g.fillText(label, (a.x + b.x) / 2, (a.y + b.y) / 2 - 8 * dpr);
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
      b.classList.toggle('cm', n > 0);
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

  // ------------------------------------------------------------------------------------------ controls (like the game's)
  function seek(t) { if (!S.d) return; S.t = Math.max(0, Math.min(S.d.end, t)); ui(true); }
  function play() { if (!S.d) return; if (S.t >= S.d.end) S.t = 0; S.playing = !S.playing; syncPlay(); }
  function setMode(m) {
    if (m === 'free' && S.mode === 'player' && !S.sight) behind(S.follow);
    S.mode = m;
    document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
    ui(true);
  }
  function watch(i) { if (byI[i] === undefined) return; S.follow = i; S.sight = null; setMode('player'); }
  function cycle(dir) {                  // the next / previous player still alive (all of them once everyone's dead)
    const alive = ORDER.filter(p => S.t <= deadAt(p.i));
    const list = alive.length ? alive : ORDER;
    const k = list.findIndex(p => p.i === S.follow);
    watch(list[(k + dir + list.length) % list.length].i);
  }
  function setUi(on) {
    S.ui = on;
    for (const id of ['rv-hud', 'rv-tr', 'rv-bar']) $(id).hidden = !on;
    $('m3-radar').style.visibility = on ? '' : 'hidden';
    $('rv-hint').hidden = on;
    if (!on) setReport(false);
    pov();
  }
  function setReport(on) {
    S.report = on; $('rv-report').hidden = !on;
    if (on) tab(S.tab);
  }
  function tab(name) {
    S.tab = name;
    document.querySelectorAll('[data-tab]').forEach(b => { b.classList.toggle('on', b.dataset.tab === name); b.setAttribute('aria-selected', b.dataset.tab === name); });
    document.querySelectorAll('[data-pane]').forEach(p => { p.hidden = p.dataset.pane !== name; });
  }
  const typing = e => /INPUT|TEXTAREA|SELECT/.test(e.target.tagName || '') && e.target.type !== 'checkbox' && e.target.type !== 'range';
  const FLY_KEYS = ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyE', 'KeyQ', 'ShiftLeft', 'ShiftRight', 'ControlLeft', 'ControlRight'];
  document.addEventListener('keydown', e => {
    if (typing(e)) return;
    const c = e.code;
    // 4.50: Ctrl flies down in the free camera like in the game; the browser's own Ctrl shortcuts (save, bookmark,
    // select all…) are kept away from WASD while it's held. Ctrl+W can't be stopped outside full screen.
    if (c === 'ControlLeft' || c === 'ControlRight') { if (S.mode === 'free') S.keys.add(c); return; }
    if (e.ctrlKey && S.mode === 'free' && /^Key[WASDEQ]$/.test(c)) { e.preventDefault(); S.keys.add(c); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (FLY_KEYS.includes(c)) {
      S.keys.add(c);
      if (S.mode === 'player' && /^Key[WASDEQ]$/.test(c)) { behind(S.follow); setMode('free'); }
      return;
    }
    if (c === 'KeyP') { e.preventDefault(); play(); }                       // 4.50: P plays in both camera modes
    else if (c === 'Space') { e.preventDefault(); if (S.mode === 'free') S.keys.add(c); else play(); }   // free camera: up
    else if (c === 'ArrowRight') { e.preventDefault(); seek(S.t + 5); }
    else if (c === 'ArrowLeft') { e.preventDefault(); seek(S.t - 5); }
    else if (c === 'KeyV') setMode(S.mode === 'player' ? 'free' : 'player');
    else if (c === 'KeyT') setUi(!S.ui);
    else if (c === 'KeyN') setReport(!S.report);
    else if (c === 'Escape' && S.report) setReport(false);
    else if (/^Digit[0-9]$/.test(c)) { const n = (+c.slice(5) + 9) % 10; if (ORDER[n]) watch(ORDER[n].i); }
    else if (c === 'Period' || c === 'PageDown') { const n = C.rounds.find(r => r.i > S.round && r.has); if (n) loadRound(n.i); }
    else if (c === 'Comma' || c === 'PageUp') { const n = [...C.rounds].reverse().find(r => r.i < S.round && r.has); if (n) loadRound(n.i); }
    else if (c === 'BracketRight' || c === 'BracketLeft') {
      const sp = [...$('rv-speed').options].map(o => +o.value), k = sp.indexOf(S.speed);
      S.speed = sp[Math.max(0, Math.min(sp.length - 1, k + (c === 'BracketRight' ? 1 : -1)))]; $('rv-speed').value = String(S.speed);
    }
  });
  document.addEventListener('keyup', e => S.keys.delete(e.code));
  window.addEventListener('blur', () => S.keys.clear());

  // the mouse on the view: drag to look (free camera); in player view a click is the next player, a right click the
  // previous one; the mouse's back and forward buttons do the same in both modes. The wheel flies forward and back.
  const cv = $('m3-canvas'), stage = $('m3-stage');
  let drag = null;
  cv.addEventListener('contextmenu', e => e.preventDefault());
  cv.addEventListener('pointerdown', e => {
    if (e.button === 3 || e.button === 4) { e.preventDefault(); cycle(e.button === 4 ? 1 : -1); return; }
    drag = {x: e.clientX, y: e.clientY, moved: 0, button: e.button, id: e.pointerId};
    try { cv.setPointerCapture(e.pointerId); } catch (err) {}
    stage.classList.add('drag');
  });
  cv.addEventListener('pointermove', e => {
    if (!drag || e.pointerId !== drag.id) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    drag.x = e.clientX; drag.y = e.clientY; drag.moved += Math.abs(dx) + Math.abs(dy);
    if (S.mode !== 'free' && drag.moved > 6) { behind(S.follow); setMode('free'); }
    if (S.mode === 'free') { S.cam.yaw += dx * LOOK; S.cam.pitch = Math.max(-1.55, Math.min(1.4, S.cam.pitch - dy * LOOK)); }
  });
  const up = e => {
    if (!drag || e.pointerId !== drag.id) return;
    const click = drag.moved < 6, b = drag.button;
    drag = null; stage.classList.remove('drag');
    if (click && S.mode === 'player') cycle(b === 2 ? -1 : 1);
  };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  cv.addEventListener('wheel', e => {
    e.preventDefault();
    if (S.mode !== 'free') { behind(S.follow); setMode('free'); }
    const c = S.cam, d = -Math.sign(e.deltaY) * (e.shiftKey ? 6 : 2.5);
    c.x += Math.sin(c.yaw) * Math.cos(c.pitch) * d; c.y += Math.sin(c.pitch) * d; c.z += -Math.cos(c.yaw) * Math.cos(c.pitch) * d;
  }, {passive: false});

  $('rv-play').addEventListener('click', play);
  $('rv-back').addEventListener('click', () => seek(S.t - 5));
  $('rv-fwd').addEventListener('click', () => seek(S.t + 5));
  $('rv-time').addEventListener('input', e => seek(+e.target.value));
  $('rv-speed').addEventListener('change', e => { S.speed = +e.target.value || 1; });
  $('rv-names').addEventListener('change', e => { S.names = e.target.checked; });
  $('rv-util').addEventListener('change', e => { S.util = e.target.checked; });
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
  document.querySelectorAll('[data-tab]').forEach(b => b.addEventListener('click', () => tab(b.dataset.tab)));
  $('rv-report-btn').addEventListener('click', () => setReport(!S.report));
  $('rv-report-x').addEventListener('click', () => setReport(false));
  $('rv-hint').addEventListener('click', () => setUi(true));
  $('rv-full').addEventListener('click', () => {
    const el = $('rv');
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else if (el.requestFullscreen) el.requestFullscreen().then(() => {
      // 4.50: in full screen the page may keep Ctrl+W & co. for itself (Chrome, Edge): Ctrl is "down" in the free camera
      try { if (navigator.keyboard && navigator.keyboard.lock) navigator.keyboard.lock(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE']).catch(() => {}); } catch (err) {}
    }).catch(() => {});
  });
  $('rv-rounds').addEventListener('click', e => { const b = e.target.closest('[data-r]'); if (b && !b.disabled) loadRound(+b.dataset.r); });
  document.addEventListener('click', e => {
    const p = e.target.closest('[data-p]'); if (p) { watch(+p.dataset.p); return; }
    const sg = e.target.closest('[data-sight]'); if (sg) { showSight(+sg.dataset.sight); return; }
    const k = e.target.closest('[data-t]');
    if (k && (k.closest('#rv-feed') || k.closest('#rv-clist') || k.closest('#rv-marks') || k.closest('#rv-deaths'))) { S.sight = null; seek(+k.dataset.t); return; }
    const del = e.target.closest('[data-del]'); if (del) delComment(del.dataset.del);
  });
  $('rv-c-add').addEventListener('click', addComment);
  $('rv-c-text').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); addComment(); } });
  $('rv-c-text').addEventListener('focus', () => { if (S.playing) { S.playing = false; syncPlay(); } });

  const drawAll = (g, project, w, h, dpr) => { draw(g, project, w, h, dpr); drawSight(g, project, dpr); };
  const layer = {tick, draw: drawAll, radar, models, objects, ready: () => { if (!S.placed) { overview(); S.placed = true; } camera(); }};
  window.nexusMap3D.setLayer(layer);
  window.nexusMap3D.setOpt('labels', false);
  if (C.anims && window.nexusMap3D.anims) window.nexusMap3D.anims(C.anims);
  loadRound(C.start);
  loadComments();
  setMode('free');
  window.nexusReplay = {state: () => ({round: S.round, t: S.t, mode: S.mode, cam: S.mode, follow: S.follow, playing: S.playing, ui: S.ui,
                                        report: S.report, players: S.d ? Object.keys(S.d.paths).length : 0, comments: S.comments.length}),
                        seek, loadRound, at, setMode, watch, play, setCam: m => setMode(m === 'follow' ? 'player' : 'free'),
                        models, keys: () => [...S.keys], cam: () => ({...S.cam}), place: c => { setMode('free'); Object.assign(S.cam, c); }};   // for tests
})();
