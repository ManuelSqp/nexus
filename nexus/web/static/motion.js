// 4.51: how players move in the 3D views, shared by the replay viewer (replay.js) and the aim drills (drill.js).
// Everything is read from a round's paths ([t, x, y, z, yaw] every 200 ms, web/replayview.py): where a player is
// at any time, which of the game's animations to play (stats/agentanim.py), how a dead one falls, the gun in his
// hands, and the utility placed at that time (smokes, walls, slows, mollies, flashes).
(function () {
  'use strict';
  // [x, y, z, yaw] at time t (between two samples), or null outside the path
  function at(path, t) {
    if (!path || !path.length || t < path[0][0] - 0.5 || t > path[path.length - 1][0] + 0.25) return null;
    let lo = 0, hi = path.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (path[m][0] <= t) lo = m; else hi = m; }
    const a = path[lo], b = path[hi], f = b[0] > a[0] ? Math.min(1, Math.max(0, (t - a[0]) / (b[0] - a[0]))) : 0;
    let dy = b[4] - a[4]; if (dy > Math.PI) dy -= 2 * Math.PI; if (dy < -Math.PI) dy += 2 * Math.PI;
    return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f, a[4] + dy * f];
  }
  // at(), but held at the path's ends (a drill keeps the enemy where his path stops)
  function atClamped(path, t) {
    if (!path || !path.length) return null;
    return at(path, Math.max(path[0][0], Math.min(path[path.length - 1][0], t)));
  }

  // ---------------------------------------------------------------- animations (4.50)
  // Which animations play is read from the path: how fast and which way a player moves compared to where he looks
  // (walk/run in eight directions, blended), up or down fast (in the air), lower than the floor around him
  // (crouching). The legs' phase follows the distance walked, so the feet don't slide and scrubbing back and forth
  // gives the same pose. The upper body holds the gun.
  const GAIT = {walk: 3.4, run: 5.5, cwalk: 1.8};      // m/s each clip moves at (measured from the clips)
  const DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  function prep(paths) {                                 // per sample: the distance walked so far, the floor around (±2 s)
    for (const path of Object.values(paths || {})) {
      if (path._prep) continue;
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
      path._prep = true;
    }
  }
  function extra(path, t, n) {                           // a prep() value at time t
    if (!path || !path.length) return 0;
    if (t <= path[0][0]) return path[0][n] || 0;
    if (t >= path[path.length - 1][0]) return path[path.length - 1][n] || 0;
    let lo = 0, hi = path.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (path[m][0] <= t) lo = m; else hi = m; }
    const a = path[lo], b = path[hi], f = b[0] > a[0] ? (t - a[0]) / (b[0] - a[0]) : 0;
    return (a[n] || 0) + ((b[n] || 0) - (a[n] || 0)) * f;
  }
  const clamp01 = v => Math.max(0, Math.min(1, v));
  const hand = () => { const M = window.nexusMap3D && window.nexusMap3D.map(); return (M && M.hand) || 1; };
  const axes = yaw => { const f = [Math.sin(yaw), -Math.cos(yaw)], h = hand(); return [f, [h * f[1], -h * f[0]]]; };
  function motion(path, t, p, hold = 'hold') {           // -> {anim: {lb, ub}, lift}
    const t0 = path[0][0], t1 = path[path.length - 1][0];
    const ta = Math.max(t0, t - 0.2), tb = Math.min(t1, t + 0.2), dt = tb - ta;
    let vx = 0, vy = 0, vz = 0;
    if (dt > 0.05) { const a = at(path, ta), b = at(path, tb); if (a && b) { vx = (b[0] - a[0]) / dt; vy = (b[1] - a[1]) / dt; vz = (b[2] - a[2]) / dt; } }
    const sp = Math.hypot(vx, vz), [f, r] = axes(p[3]);
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
    return {anim: {lb, ub: [[hold, t, 1]]}, lift: cr * Math.max(0, dip), speed: sp};
  }
  // how a player hit from `from` (a point) falls: pushed away from it
  function deathClip(p, from) {
    if (!from) return 'death_front';
    const [f, r] = axes(p[3]);
    const dx = from[0] - p[0], dz = from[2] - p[2], fw = dx * f[0] + dz * f[1], rt = dx * r[0] + dz * r[1];
    if (Math.abs(fw) >= Math.abs(rt)) return fw > 0 ? 'death_back' : 'death_front';
    return rt > 0 ? 'death_left' : 'death_right';
  }
  // the gun in his hands: bought (the round's economy), then what he killed with: [[from s, name], …]
  function weaponAt(seq, t) {
    let name = 'Classic';
    if (seq) for (const [t0, w] of seq) if (t0 <= t) name = w;
    return name;
  }
  // 4.50.1: sidearms are held out in front with both hands
  const SIDEARMS = new Set(['Classic', 'Shorty', 'Frenzy', 'Ghost', 'Sheriff', 'Bandit']);
  const holdFor = w => (SIDEARMS.has(w) && window.nexusMap3D.clips().includes('pistol') ? 'pistol' : 'hold');

  // ---------------------------------------------------------------- utility shapes (4.45)
  const R_UTIL = {smoke: 4.4, slow: 3.5, damage: 3.3, wall: 2.0, recon: 2.5, trap: 1.2, orb: 2.5, flash: 1.2};
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
  function utilColor(u, cols) {
    if (u.type === 'smoke') return SMOKE[(u.agent || '').toLowerCase()] || SMOKE_DEFAULT;
    return hex((cols || {})[u.type] || '#cccccc');
  }
  function utilObjects(list, t, cols) {                   // 3D utility for map3d.js (the walls hide them)
    const out = [];
    for (const u of list || []) {
      if (!live(u, t)) continue;
      const y = u.y !== null ? u.y : 0, col = utilColor(u, cols), seed = (u.x * 7.3 + u.z * 3.1) % 50;
      if (u.type === 'smoke') out.push({x: u.x, y: y + 2.4, z: u.z, r: R_UTIL.smoke, sc: [1, 0.9, 1], col, a: 0.88, seed, block: true});
      else if (u.type === 'damage' || u.type === 'slow') out.push({x: u.x, y: y + 0.06, z: u.z, r: R_UTIL[u.type], sc: [1, 0.035, 1], col, a: 0.55, seed, cloudy: false});
      else if (u.type === 'wall') out.push({x: u.x, y: y + 2, z: u.z, r: 2, sc: [0.35, 1, 0.35], col, a: 0.6, seed, cloudy: false, block: true});
      else out.push({x: u.x, y: y + 1, z: u.z, r: 0.35, col, a: 0.95, seed, cloudy: false});
    }
    return out;
  }

  window.NexusMotion = {at, atClamped, prep, extra, motion, deathClip, weaponAt, holdFor, SIDEARMS, live, utilColor,
                        utilObjects, R_UTIL, GAIT, hex};
})();
