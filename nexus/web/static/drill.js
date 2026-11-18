// Aim drills on the real maps (Practice › Aim on maps; web/drills.py, stats/drills.py), in the 3D map of map3d.js
// with the game's animated agents (4.50). Valorant's numbers: 0.07° per mouse count × sens, 103° wide view, the
// gun's magazine, fire rate, reload, damage and zoom; hits on the agent's skeleton (head, body and arms, legs);
// walls and smokes in the way. Your own keys (keys.js); Esc always stops.
//
// Modes (C.mode):
//   death  (4.51) your death as a drill: you stand where you died, your killer comes out on his real path from the
//          replay with his gun, the round's smokes and walls where they were; beat his time.
//   hold   (4.52) hold an angle: enemies peek from the real corner (wide swing, jiggle, crouch, jump, two at once);
//          kill each before he has you for his reaction time (the difficulty).
//   attack (4.52) you peek: you move (your keys, Valorant's speeds and stopping) and take the spot from the
//          defenders on their usual places; shots while moving go wide, the drill shows how fast you stopped.
//   track  (4.52) an enemy strafes (ADAD) where fights happen; stay on his head for 30 s.
//   clear  (4.52) walk the attackers' route onto a site; each hiding place is checked as it opens (your crosshair
//          on it, at head height?), some have an enemy.
// The spots and routes come from the fights in all replays of the map (stats/drills.py spots()).
(function () {
  'use strict';
  const C = window.NEXUS_MAP3D;
  if (!C || !C.drill) return;
  const MODE = C.mode || 'death', D = C.drill, SP = C.spot || null, O = C.opts || {};
  const NM = window.NexusMotion, KB = window.NexusKeys;
  const $ = id => document.getElementById(id);
  const T = s => (window.vcT ? window.vcT(s) : s);
  const V = () => window.nexusMap3D;
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const D2R = Math.PI / 180, YAW = 0.07, VFOV = 70.53;
  const EYE = 1.85, EYE_CROUCH = 1.35, MAP_EYE = 1.6;   // your eyes above your feet; map3d.js adds MAP_EYE
  const HEAD_R = 0.14, BODY_R = 0.2, ARM_R = 0.07, LEG_R = 0.1;
  const WATCH = 0.35;                       // "watch how he did it": this fast
  const ENEMY = [0.86, 0.3, 0.36];
  // moving like Valorant (m/s): running, walking, crouching; how fast you speed up and stop; above ACCURATE the
  // first shot goes wide (up to SPREAD degrees at full speed)
  const RUN = 6.75, WALK = 3.6, CROUCH = 2.4, ACCEL = 40, STOP = 55, ACCURATE = 1.75, SPREAD = 6;
  const MOVING = MODE === 'attack' || MODE === 'clear';
  const canvas = $('m3-canvas');
  let keys = KB.normalize(C.keys, C.defaults);
  const opt = {speed: 1, heads: true, reps: O.reps || 10};
  if (MODE === 'death') try { Object.assign(opt, JSON.parse(localStorage.getItem('nexus.drill') || '{}')); } catch (e) {}
  else try { opt.heads = JSON.parse(localStorage.getItem('nexus.drill') || '{}').heads !== false; } catch (e) {}
  const saveOpt = () => {
    try {
      const old = JSON.parse(localStorage.getItem('nexus.drill') || '{}');
      localStorage.setItem('nexus.drill', JSON.stringify(MODE === 'death' ? opt : Object.assign(old, {heads: opt.heads})));
    } catch (e) {}
  };
  const gun = C.gun, HP = C.hp || 150;
  const react = O.react || 0.6;
  const AGENTS = Object.keys(C.agents || {});
  const RIFLES = ['Vandal', 'Phantom', 'Vandal', 'Phantom', 'Spectre', 'Sheriff'];
  const pick = a => a[Math.floor(Math.random() * a.length)];
  const S = {phase: 'loading', R: null, t: 0, t0: 0, reps: [], foes: [], yaw: 0, pitch: 0, ammo: gun.mag, reload: 0,
             next: 0, firing: false, ads: false, first: null, firsts: {head: 0, body: 0, legs: 0, miss: 0}, offs: [],
             flash: 0, until: 0, msg: '', lastT: 0, paused: false, saved: false, held: new Set(), dead: false,
             me: {x: 0, y: 0, z: 0, vx: 0, vz: 0, crouch: false, still: 0}, styles: {}, shots: [], track: null,
             hides: [], deaths: 0, kills: 0};

  // ------------------------------------------------------------------------------------------ where you stand
  function home() {                       // where a rep starts: [x, y, z, yaw]
    if (MODE === 'death') return D.me;
    if (MODE === 'attack') return SP._start || [...SP.start, SP.start_yaw];
    if (MODE === 'clear') {
      const i = SP._from || 0, p = SP.route[i];
      return [p[0], p[1], p[2], yawTo(p, SP.route[Math.min(SP.route.length - 1, i + 4)])];
    }
    return SP._stand || [...SP.hold, SP.hold_yaw];
  }
  // attacking: start on the attackers' route, as close as can be but out of the defenders' sight
  function attackStart() {
    const defs = SP.defs.slice(0, 3), unseen = p => defs.every(d => !V().visible([d[0], d[1] + 1.75, d[2]], [p[0], p[1] + 1.85, p[2]]) &&
                                                                       !V().visible([d[0], d[1] + 1.75, d[2]], [p[0], p[1] + 1.1, p[2]]));
    const pts = [SP.start, ...SP.route.slice().reverse()];
    const p = pts.find(unseen) || SP.route[0] || SP.start;
    return [p[0], p[1], p[2], yawTo(p, SP.hold)];
  }
  // clear a site: start on the route as late as can be while no hiding place can be seen yet
  function clearStart() {
    const R = SP.route;
    for (let i = R.length - 1; i >= 0; i--) {
      const e = [R[i][0], R[i][1] + EYE, R[i][2]];
      if (SP.hides.every(h => !V().visible(e, [h[0], h[1] + 1.95, h[2]]))) return Math.max(0, i - 2);  // a step back
    }
    return 0;
  }
  // hold, track: where the defender stood may be right behind a box (he crouched, or the replay's position is a bit
  // off): stand where the corners can be seen, as close as can be, looking at the first one
  function stand() {
    const h = [...SP.hold, SP.hold_yaw];
    const opens = (x, y, z) => SP.peeks.filter(P => V().visible([x, y + EYE, z], [P[0], P[1] + 1.6, P[2]]));
    let best = [opens(h[0], h[1], h[2]), h];
    for (const r of [0.5, 1, 1.5, 2, 3]) {
      if (best[0].length) break;
      for (let k = 0; k < 12; k++) {
        const a = k / 12 * 2 * Math.PI, x = h[0] + Math.cos(a) * r, z = h[2] + Math.sin(a) * r, y = floor(x, z, h[1]);
        if (y === null || Math.abs(y - h[1]) > 0.5 || V().blocked(x, z, y)) continue;
        const o = opens(x, y, z);
        if (o.length > best[0].length) best = [o, [x, y, z, h[3]]];
      }
    }
    const [o, at] = best;
    if (o.length) at[3] = yawTo(at, o[0]);
    return at;
  }
  const eyeH = () => (S.me.crouch ? EYE_CROUCH : EYE);
  const eye = () => [S.me.x, S.me.y + eyeH(), S.me.z];
  const look = () => [Math.sin(S.yaw) * Math.cos(S.pitch), Math.sin(S.pitch), -Math.cos(S.yaw) * Math.cos(S.pitch)];
  const zoom = () => (S.ads ? gun.zoom || 1 : 1);
  const speed = () => Math.hypot(S.me.vx, S.me.vz);

  // ------------------------------------------------------------------------------------------ geometry
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const add = (a, b, k) => [a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k];
  const norm = v => { const L = Math.hypot(...v) || 1; return [v[0] / L, v[1] / L, v[2] / L]; };
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const angleTo = (p, from = eye(), dir = look()) => Math.acos(Math.max(-1, Math.min(1, dot(dir, norm(sub(p, from)))))) / D2R;
  const yawTo = (a, b) => Math.atan2(b[0] - a[0], -(b[2] - a[2]));
  function rayCapsule(o, d, a, b, r) {      // -> distance along the ray to the capsule a–b (radius r), or null
    const u = sub(b, a), cc = dot(u, u) || 1e-9;
    let best = null;
    for (let i = 0; i <= 8; i++) {          // closest approach: a few steps along the segment, then refined
      const s = i / 8, q = add(a, u, s), t = Math.max(0, dot(sub(q, o), d)), p = add(o, d, t), dd = dot(sub(p, q), sub(p, q));
      if (best === null || dd < best[1]) best = [t, dd, s];
    }
    let [t, dd] = best;
    for (let k = 0; k < 3; k++) {
      const p = add(o, d, t);
      const s = Math.max(0, Math.min(1, dot(sub(p, a), u) / cc));
      const q = add(a, u, s);
      t = Math.max(0, dot(sub(q, o), d));
      const p2 = add(o, d, t); dd = dot(sub(p2, q), sub(p2, q));
    }
    if (dd > r * r) return null;
    return Math.max(0, t - Math.sqrt(r * r - dd));
  }
  const floor = (x, z, y) => { const f = V().floorAt(x, z, y + 0.6); return f === null ? null : f; };

  // ------------------------------------------------------------------------------------------ the enemies
  // A foe: {key, agent, url, weapon, path ([t, x, y, z, yaw] samples, like a replay's), seen (when you could first
  // see him), sees (since when he has you), dead {t, wall}, hp, style, fov (defenders only see ahead)}
  const foeAt = (f, t) => NM.atClamped(f.path, t);
  function hitboxes(f) {                    // [[part, a, b, r], …] on the map
    const b = V().bones && V().bones(f.key);
    const p = foeAt(f, f.dead ? f.dead.t : S.t);
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
  const clear = (a, b) => V().visible(a, b) && !throughSmoke(a, b);
  const hiding = f => f.appear !== undefined && S.t < f.appear;   // not there yet (comes out of cover at this time)
  function seenBy(f) {                      // can you see him (head or chest)?
    if (hiding(f)) return false;
    const hb = hitboxes(f), hd = hb[0], chest = hb.find(h => h[0] === 'body');
    return (hd && clear(eye(), hd[1])) || (chest && clear(eye(), chest[2]));
  }
  function seesMe(f) {                      // can he see you (from his eyes, ahead of him when he holds a spot)?
    if (hiding(f)) return false;
    const p = foeAt(f, S.t), e = [p[0], p[1] + 1.75, p[2]];
    if (f.fov) {
      const d = norm([S.me.x - p[0], 0, S.me.z - p[2]]), fwd = [Math.sin(p[3]), 0, -Math.cos(p[3])];
      if (dot(d, fwd) < Math.cos(f.fov * D2R)) return false;
    }
    return clear(e, eye()) || clear(e, [S.me.x, S.me.y + 1.1, S.me.z]);
  }
  function foe(i, path, extra = {}) {
    const agent = extra.agent || pick(AGENTS.length ? AGENTS : ['']);
    const floors = path.map(r => r[6]);                  // our paths know the floor (crouching = lower than it)
    NM.prep({p: path});
    path.forEach((r, k) => { if (floors[k] !== undefined) r[6] = floors[k]; });
    return Object.assign({key: 100 + i, agent, url: (C.agents || {})[agent], weapon: pick(RIFLES), path, seen: null,
                          sees: null, dead: null, hp: HP}, extra);
  }
  const still = (p, yaw, crouch = false) => {           // a defender holding a place (crouched: lower, see motion.js)
    const y = p[1] - (crouch ? 0.45 : 0);
    return [[-1, p[0], y, p[2], yaw, 0, p[1]], [999, p[0], y, p[2], yaw, 0, p[1]]];
  };
  const seeFrom = (a, p) => V().visible(a, p);
  // a peek out of the corner at P: where he hides (behind cover, a few metres to the side), where the corner opens,
  // and his path for the style
  function peekPath(P, style, delay) {
    const H = eye(), dx = P[0] - H[0], dz = P[2] - H[2], L = Math.hypot(dx, dz) || 1;
    const u = [-dz / L, dx / L];                        // to the side
    const hidden = q => !seeFrom(H, [q[0], q[1] + 1.8, q[2]]) && !seeFrom(H, [q[0], q[1] + 1.1, q[2]]);
    let Q = null;
    for (const s of [0.6, 1, 1.5, 2, 2.5, 3, 4, 5]) {
      for (const sg of [1, -1]) {
        const x = P[0] + u[0] * s * sg, z = P[2] + u[1] * s * sg, y = floor(x, z, P[1]);
        if (y === null || V().blocked(x, z, y)) continue;
        if (hidden([x, y, z])) { Q = [x, y, z]; break; }
      }
      if (Q) break;
    }
    if (!Q) {                                            // no side cover: back off behind the corner
      for (const s of [1, 2, 3, 4, 6]) {
        const x = P[0] + dx / L * s, z = P[2] + dz / L * s, y = floor(x, z, P[1]);
        if (y !== null && hidden([x, y, z])) { Q = [x, y, z]; break; }
      }
    }
    if (!Q) Q = P.slice();
    const od = norm([P[0] - Q[0], 0, P[2] - Q[2]]);
    let E = Q.slice();                                    // where he first shows
    for (let s = 0; s < 6; s += 0.1) {
      const x = Q[0] + od[0] * s, z = Q[2] + od[2] * s, y = floor(x, z, E[1]);
      if (y === null) break;
      E = [x, y, z];
      if (!hidden(E)) break;
    }
    const out = [];
    let t = 0, cur = Q.slice();
    const push = (p, dy = 0) => out.push([t, p[0], p[1] + dy, p[2], yawTo(p, H), 0, p[1]]);
    const go = (to, sp, dyf = null) => {                   // in a line at sp m/s (dyf(k): a height on the way)
      const d = Math.hypot(to[0] - cur[0], to[2] - cur[2]), n = Math.max(1, Math.ceil(d / (sp * 0.05)));
      for (let i = 1; i <= n; i++) {
        const k = i / n, x = cur[0] + (to[0] - cur[0]) * k, z = cur[2] + (to[2] - cur[2]) * k;
        const y = floor(x, z, cur[1]) ?? cur[1];
        t += d / sp / n; push([x, y, z], dyf ? dyf(k) : 0);
      }
      cur = [to[0], floor(to[0], to[2], cur[1]) ?? to[1], to[2]];
    };
    const wait = s => { t += s; push(cur); };
    const past = m => { const x = E[0] + od[0] * m, z = E[2] + od[2] * m, y = floor(x, z, E[1]); return y === null ? E.slice() : [x, y, z]; };
    t = -1; push(Q); t = delay; push(Q);
    if (style === 'jiggle') { go(past(0.45), RUN); go(Q, RUN); wait(0.3 + Math.random() * 0.4); go(past(2.2), RUN); }
    else if (style === 'crouch') go(past(0.9), CROUCH, () => -0.45);
    else if (style === 'jump') { go(past(1.3), RUN, k => 1.1 * Math.sin(Math.PI * k)); go(Q, RUN); wait(0.4); go(past(2.2), RUN); }
    else go(past(2.2), RUN);                              // wide swing
    if (style === 'crouch') { t += 30; push(cur, -0.45); } else wait(30);
    return out;
  }
  // tracking: he strafes left and right (ADAD) across the line to the spot, as far as the floor and your view go
  function trackPath(P, secs) {
    const H = eye(), dx = P[0] - H[0], dz = P[2] - H[2], L = Math.hypot(dx, dz) || 1, u = [-dz / L, dx / L];
    const reach = sg => {
      let ok = 0;
      for (let s = 0.25; s <= 3.5; s += 0.25) {
        const x = P[0] + u[0] * s * sg, z = P[2] + u[1] * s * sg, y = floor(x, z, P[1]);
        if (y === null || V().blocked(x, z, y) || !seeFrom(H, [x, y + 1.8, z])) break;
        ok = s;
      }
      return ok;
    };
    let lo = -reach(-1), hi = reach(1);
    if (hi - lo < 1.5) { lo = -1.5; hi = 1.5; }          // no room on the map: strafe anyway
    const top = {easy: 3.0, medium: 5.0, hard: RUN, pro: RUN}[O.diff] || 5.0;
    const seg = {easy: [0.5, 1.1], medium: [0.3, 0.8], hard: [0.2, 0.6], pro: [0.15, 0.45]}[O.diff] || [0.3, 0.8];
    const out = [], dt = 1 / 30;
    let s = 0, v = 0, dir = 1, left = 0;
    for (let t = 0; t <= secs + 0.5; t += dt) {
      if (left <= 0) { dir = Math.random() < 0.8 ? -dir : dir; left = seg[0] + Math.random() * (seg[1] - seg[0]); }
      if (s >= hi - 0.05) dir = -1;
      if (s <= lo + 0.05) dir = 1;
      const target = dir * top, a = Math.sign(target) === Math.sign(v) || v === 0 ? ACCEL : STOP;
      v += Math.max(-a * dt, Math.min(a * dt, target - v));
      s = Math.max(lo, Math.min(hi, s + v * dt)); left -= dt;
      const x = P[0] + u[0] * s, z = P[2] + u[1] * s, y = floor(x, z, P[1]) ?? P[1];
      out.push([t, x, y, z, yawTo([x, y, z], H)]);
    }
    return out;
  }

  // ------------------------------------------------------------------------------------------ loading
  async function load() {
    try {
      if (MODE === 'death') {
        const r = await fetch(C.round_api, {credentials: 'same-origin'});
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
        NM.prep(d.paths);
        S.R = d;
        if (!d.paths[D.killer]) throw new Error(T('The killer isn\'t in this round\'s replay.'));
      }
      // the map, and its walls from the game's files (line of sight: where they hide, where you can see them)
      const t0 = performance.now();
      await new Promise(res => {
        const w = () => {
          const M = V().map(), walls = M && (!(M.game && M.mesh) || V().game() || performance.now() - t0 > 90000);
          return M && M.cells && walls ? res() : setTimeout(w, 100);
        };
        w();
      });
      if (MODE === 'hold' || MODE === 'track') SP._stand = stand();
      if (MODE === 'attack') SP._start = attackStart();
      if (MODE === 'clear') SP._from = clearStart();
      place(home());
      S.phase = 'ready';
      panel();
    } catch (e) {
      S.phase = 'error';
      panel(e.message);
    }
  }
  function place(h) {
    S.me = {x: h[0], y: h[1], z: h[2], vx: 0, vz: 0, crouch: false, still: 0};
    S.yaw = h[3]; S.pitch = 0;
  }

  // ------------------------------------------------------------------------------------------ shooting
  function shoot() {
    if (S.phase !== 'run' || S.dead) return;
    const now = performance.now() / 1000;
    if (S.reload > now || now < S.next) return;
    if (S.ammo <= 0) { startReload(); return; }
    S.ammo--; S.next = now + 1 / gun.rate;
    const o = eye(), sp = speed();
    let d = look();
    if (sp > ACCURATE) {                                   // moving: the shot goes wide
      const cone = Math.min(SPREAD, (sp - ACCURATE) / (RUN - ACCURATE) * SPREAD) * D2R * (S.me.crouch ? 0.6 : 1);
      const a = Math.random() * 2 * Math.PI, r = Math.tan(Math.sqrt(Math.random()) * cone);
      const side = norm(cross(d, [0, 1, 0])), up = norm(cross(side, d));
      d = norm(add(add(d, side, Math.cos(a) * r), up, Math.sin(a) * r));
    }
    if (MOVING) S.shots.push({sp, still: S.me.still});
    let hit = null;
    for (const f of S.foes) {
      if (f.dead || hiding(f)) continue;
      for (const [part, a, b, r] of hitboxes(f)) {
        const t = rayCapsule(o, d, a, b, r);
        if (t !== null && (hit === null || t < hit[2])) hit = [f, part, t];
      }
    }
    if (hit) {
      const p = add(o, d, Math.max(0, hit[2] - 0.05));
      if (!V().visible(o, p)) hit = null;                // a wall in the way
    }
    const part = hit ? hit[1] : 'miss';
    if (!S.first) { S.first = part; S.firsts[part]++; }
    marker(part, MOVING && sp > ACCURATE);
    if (!hit || MODE === 'track') return;
    const f = hit[0];
    f.hp -= gun[part] || 0;
    if (part === 'head' ? (opt.heads || f.hp <= 0) : (!opt.heads && f.hp <= 0)) kill(f);
  }
  function startReload() {
    const now = performance.now() / 1000;
    if (S.reload > now || S.ammo >= gun.mag) return;
    S.reload = now + gun.reload; S.firing = false;
  }
  function kill(f) {
    f.dead = {t: S.t, wall: performance.now() / 1000};
    S.kills++;
    if (!S.foes.every(x => x.dead)) return;
    if (MODE === 'death' || MODE === 'hold') {
      const seen = Math.min(...S.foes.map(x => (x.seen ?? x.dead.t)));
      const mine = Math.max(0, S.t - seen);
      S.reps.push(Math.round(mine * 1000) / 1000);
      if (MODE === 'hold') for (const x of S.foes) (S.styles[x.style] = S.styles[x.style] || []).push(mine);
      endRep(mine);
    } else if (MODE === 'attack') {
      S.reps.push(Math.round(S.t * 1000) / 1000);
      endRep(S.t, T('Spot taken'));
    }
  }

  // ------------------------------------------------------------------------------------------ the reps
  function startRep() {
    S.t = MODE === 'death' ? D.t0 : 0; S.lastT = S.t; S.t0 = S.t;
    place(home());
    S.dead = false; S.ammo = gun.mag; S.reload = 0; S.next = 0; S.first = null; S.flash = 0; S.msg = '';
    S.foes = [];
    if (MODE === 'death') {
      S.foes = [foe(0, S.R.paths[D.killer], {key: D.killer, agent: D.killer_agent, weapon: D.weapon, replay: true})];
    } else if (MODE === 'hold') {
      const styles = (O.styles || ['wide']).filter(s => s !== 'two');
      const two = (O.styles || []).includes('two') && SP.peeks.length > 1 && (!styles.length || Math.random() < 0.35);
      const open = SP.peeks.filter(P => seeFrom(eye(), [P[0], P[1] + 1.6, P[2]]));   // the corners you can see
      const from = (open.length ? open : SP.peeks).slice().sort(() => Math.random() - 0.5);
      const delay = 0.6 + Math.random() * 1.8;
      for (let i = 0; i < (two ? 2 : 1); i++) {
        const style = pick(styles.length ? styles : ['wide']), at = delay + i * (0.15 + Math.random() * 0.4);
        S.foes.push(foe(i, peekPath(from[i % from.length], style, at), {style: two ? 'two' : style, appear: at}));
      }
    } else if (MODE === 'track') {
      S.track = {secs: 30, head: 0, body: 0, all: 0, bins: []};
      const P = SP.peeks.find(q => seeFrom(eye(), [q[0], q[1] + 1.6, q[2]])) || SP.peeks[0];
      S.foes = [foe(0, trackPath(P, 30), {style: 'track', harmless: true})];
    } else if (MODE === 'attack') {
      S.foes = SP.defs.slice(0, Math.min(3, SP.defs.length))
        .map((p, i) => foe(i, still(p, yawTo(p, SP.start), Math.random() < 0.3), {fov: 52}));
    } else if (MODE === 'clear') {
      const order = SP.hides.map((p, i) => i).sort(() => Math.random() - 0.5);
      const busy = new Set(order.slice(0, Math.min(2, SP.hides.length)));
      // hiding places you can already see from the start don't count (you can't hold them all at once)
      S.hides = SP.hides.map((p, i) => ({p, open: clear(eye(), [p[0], p[1] + 1.95, p[2]]) ? -1 : null, off: null, busy: busy.has(i)}));
      S.foes = SP.hides.map((p, i) => [p, i]).filter(([, i]) => busy.has(i))
        .map(([p, i], k) => foe(k, still(p, yawTo(p, nearestOnRoute(p)), Math.random() < 0.3), {fov: 60, hide: i}));
    }
    S.phase = 'count'; S.until = performance.now() / 1000 + 0.7;
    panel();
  }
  function nearestOnRoute(p) {              // where a defender looks: the nearest bit of the route (not on top of him)
    let best = SP.route[0], bd = Infinity;
    for (const q of SP.route) { const d = Math.hypot(q[0] - p[0], q[2] - p[2]); if (d < bd && d > 3) { bd = d; best = q; } }
    return best;
  }
  function endRep(mine, label) {
    S.phase = 'between'; S.firing = false;
    const his = MODE === 'death' ? D.his : MODE === 'hold' ? react : null;
    if (mine === null) S.msg = `<b class="bad">${esc(label || T('He got you'))}</b>`;
    else if (MODE === 'track') S.msg = `<b class="good">${Math.round(mine)} % ${esc(T('on his head'))}</b>`;
    else if (MODE === 'clear') S.msg = `<b class="good">${Math.round(mine)} % ${esc(T('crosshair placement'))}</b>`;
    else if (his !== null && his !== undefined) S.msg = mine < his ? `<b class="good">${esc(T('Faster than him'))} · ${mine.toFixed(2)} s</b>` : `<b class="bad">${esc(T('Slower than him'))} · ${mine.toFixed(2)} s</b>`;
    else S.msg = `<b class="good">${esc(label || '')} ${mine.toFixed(2)} s</b>`;
    S.until = performance.now() / 1000 + (mine === null ? 1.3 : 1.6);
    hud(true);
  }
  function failRep(label) {
    if (S.phase !== 'run') return;
    S.dead = true; S.deaths++;
    S.reps.push(MODE === 'clear' ? placement() : null);
    endRep(null, label);
  }
  function placement() {                    // % of the opened hiding places your crosshair was on (within 7°)
    const op = S.hides.filter(h => h.off !== null);
    return op.length ? Math.round(op.filter(h => h.off <= 7).length / op.length * 1000) / 10 : 0;
  }
  function afterRep() {
    if (S.reps.length >= opt.reps) done();
    else startRep();
  }
  function restart() {
    S.reps = []; S.firsts = {head: 0, body: 0, legs: 0, miss: 0}; S.offs = []; S.saved = false; S.styles = {};
    S.shots = []; S.deaths = 0; S.kills = 0; startRep();
  }
  function watch() {
    if (MODE !== 'death' || !S.R) return;
    startRep(); S.phase = 'watch'; S.msg = esc(T('Watching how he did it (slowed down)'));
    panel();
  }

  // ------------------------------------------------------------------------------------------ the clock
  function move(dt) {                       // your feet: Valorant's speeds, speeding up and stopping
    const m = S.me, has = a => (keys[a] || []).some(k => k && S.held.has(k));
    m.crouch = has('crouch');
    const max = m.crouch ? CROUCH : has('walk') ? WALK : RUN;
    const f = [Math.sin(S.yaw), -Math.cos(S.yaw)], r = [Math.cos(S.yaw), Math.sin(S.yaw)];
    let wx = 0, wz = 0;
    if (has('forward')) { wx += f[0]; wz += f[1]; }
    if (has('back')) { wx -= f[0]; wz -= f[1]; }
    if (has('right')) { wx += r[0]; wz += r[1]; }
    if (has('left')) { wx -= r[0]; wz -= r[1]; }
    const L = Math.hypot(wx, wz);
    const tx = L ? wx / L * max : 0, tz = L ? wz / L * max : 0;
    const dvx = tx - m.vx, dvz = tz - m.vz, dv = Math.hypot(dvx, dvz);
    const a = (tx * m.vx + tz * m.vz < 0 || Math.hypot(tx, tz) < Math.hypot(m.vx, m.vz)) ? STOP : ACCEL;
    if (dv > 1e-6) { const s = Math.min(dv, a * dt); m.vx += dvx / dv * s; m.vz += dvz / dv * s; }
    if (!L) m.still += dt; else m.still = 0;
    const nx = m.x + m.vx * dt, nz = m.z + m.vz * dt;
    const ok = (x, z) => !V().blocked(x, z, m.y);
    if (ok(nx, nz)) { m.x = nx; m.z = nz; } else if (ok(nx, m.z)) { m.x = nx; m.vz = 0; } else if (ok(m.x, nz)) { m.z = nz; m.vx = 0; } else { m.vx = 0; m.vz = 0; }
    const fl = floor(m.x, m.z, m.y);
    if (fl !== null) m.y = fl;
  }
  function tick(dt) {
    if (S.phase === 'loading' || S.phase === 'error') { camera(); return; }
    const now = performance.now() / 1000;
    if (S.phase === 'count' && now >= S.until) { S.phase = 'run'; panel(); }
    if (S.phase === 'between' && now >= S.until) afterRep();
    if (S.phase === 'run' || S.phase === 'watch') {
      S.lastT = S.t;
      S.t += dt * (S.phase === 'watch' ? WATCH : (MODE === 'death' ? opt.speed : 1));
      if (MOVING && S.phase === 'run') move(dt);
      for (const f of S.foes) {
        if (f.dead) continue;
        if (f.seen === null && seenBy(f)) {
          f.seen = S.t;
          if (S.phase === 'run' && MODE !== 'track') S.offs.push(angleTo(hitboxes(f)[0][1]));
        }
        if (MODE === 'death' || f.harmless || S.phase !== 'run') continue;
        if (seesMe(f)) { if (f.sees === null) f.sees = S.t; } else f.sees = null;
        if (f.sees !== null && S.t - f.sees >= react) { failRep(); break; }
      }
      if (MODE === 'death' && S.phase === 'run' && !S.foes[0].dead && S.t >= D.t_kill) failRep();
      if (MODE === 'death' && S.phase === 'watch' && S.t >= D.t_kill) { S.phase = 'between'; S.msg = ''; S.until = now + 0.8; }
      if (MODE === 'track' && S.phase === 'run') trackTick(dt);
      if (MODE === 'clear' && S.phase === 'run') clearTick();
      if (MODE === 'attack' && S.phase === 'run' && S.t > 60) failRep(T('Out of time'));
      if (MODE === 'hold' && S.phase === 'run' && S.t > 40) failRep(T('Out of time'));
      if (S.R) flashes();
      if (S.phase === 'run' && S.firing && gun.auto) shoot();
    }
    if (S.reload && now >= S.reload) { S.reload = 0; S.ammo = gun.mag; }
    S.flash = Math.max(0, S.flash - dt / 1.6);
    camera();
    hud();
  }
  function trackTick(dt) {
    const tr = S.track, f = S.foes[0], o = eye(), d = look();
    let on = null;
    for (const [part, a, b, r] of hitboxes(f)) { const t = rayCapsule(o, d, a, b, r); if (t !== null && (on === null || part === 'head')) on = part; }
    tr.all += dt; if (on === 'head') tr.head += dt; if (on) tr.body += dt;
    const i = Math.floor(S.t);
    tr.bins[i] = tr.bins[i] || [0, 0]; tr.bins[i][0] += dt; if (on === 'head') tr.bins[i][1] += dt;
    if (S.t >= tr.secs) {
      const pct = tr.all ? tr.head / tr.all * 100 : 0;
      S.reps.push(Math.round(pct * 10) / 10);
      endRep(pct);
    }
  }
  function clearTick() {
    for (const h of S.hides) {                // each hiding place, the moment it opens
      if (h.open !== null) continue;
      const head = [h.p[0], h.p[1] + 1.95, h.p[2]];
      if (Math.hypot(head[0] - S.me.x, head[2] - S.me.z) < 40 && clear(eye(), head)) { h.open = S.t; h.off = angleTo(head); }
    }
    const end = SP.route[SP.route.length - 1];
    const allOpen = S.hides.every(h => h.open !== null), atEnd = Math.hypot(end[0] - S.me.x, end[2] - S.me.z) < 2.5;
    if (((allOpen || atEnd) && S.foes.every(f => f.dead)) || S.t > 75) {
      const pct = placement();
      S.reps.push(pct);
      endRep(pct);
    }
  }
  function flashes() {                      // a flash that popped in your view while you looked
    for (const u of (S.R.util || [])) {
      if (u.type !== 'flash' || u.t0 <= S.lastT || u.t0 > S.t) continue;
      const p = [u.x, (u.y !== null ? u.y : S.me.y) + 1.2, u.z];
      if (angleTo(p) < 60 && V().visible(eye(), p)) S.flash = 1;
    }
  }
  function camera() {
    V().view({x: S.me.x, y: S.me.y + eyeH() - MAP_EYE, z: S.me.z, yaw: S.yaw, pitch: S.pitch, fly: true, fov: VFOV / zoom()});
  }

  // ------------------------------------------------------------------------------------------ for map3d.js
  function models() {
    const out = [];
    for (const f of S.foes) {
      if (!f.url || hiding(f)) continue;
      const p = foeAt(f, f.dead ? f.dead.t : S.t);
      if (!p) continue;
      const o = {key: f.key, url: f.url, x: p[0], y: p[1], z: p[2], yaw: p[3], col: ENEMY};
      if (f.dead) {
        o.anim = {lb: [[NM.deathClip(p, eye()), performance.now() / 1000 - f.dead.wall, 1]], ub: null};
      } else if (C.anims) {
        const m = NM.motion(f.path, S.t, p, NM.holdFor(f.weapon));
        o.anim = m.anim; o.y += m.lift; o.gun = (C.guns && C.guns[f.weapon]) || null; o.hold = NM.holdFor(f.weapon);
      }
      out.push(o);
    }
    return out;
  }
  function objects() { return S.R ? NM.utilObjects(S.R.util, S.t, C.util_col) : []; }
  function radar(g, toR) {                  // clear a site: the route and the hiding places on the minimap
    if (MODE !== 'clear' || !SP) return;
    g.strokeStyle = 'rgba(255,79,139,.9)'; g.lineWidth = 3; g.setLineDash([6, 6]); g.beginPath();
    SP.route.slice(SP._from || 0).forEach((p, i) => { const [x, y] = toR(p[0], p[2]); if (i) g.lineTo(x, y); else g.moveTo(x, y); });
    g.stroke(); g.setLineDash([]);
    for (const h of S.hides) {
      const [x, y] = toR(h.p[0], h.p[2]);
      g.fillStyle = h.off === null ? '#5b6b8c' : h.off <= 7 ? '#2fc4b2' : '#e2a23a';
      g.beginPath(); g.arc(x, y, 6, 0, 2 * Math.PI); g.fill(); g.strokeStyle = '#fff'; g.lineWidth = 1.5; g.stroke();
    }
  }

  // ------------------------------------------------------------------------------------------ the page
  const fromTo = (a, b) => (a === b ? a : `${a} ${T('from')} ${b}`);
  function title() {                        // the spot's name (translated)
    switch (MODE) {
      case 'hold': return `${T('Hold:')} ${fromTo(SP.az, SP.dz)}`;
      case 'attack': return `${T('Take:')} ${fromTo(SP.dz, SP.az)}`;
      case 'track': return `${T('Tracking at')} ${SP.az}`;
      case 'clear': return `${T('Clear:')} ${fromTo(SP.dz, SP.az)}`;
      default: return C.title || '';
    }
  }
  const STYLE = {wide: 'Wide swing', jiggle: 'Jiggle peek', crouch: 'Crouch peek', jump: 'Jump peek', two: 'Two at once'};
  let lastHud = 0;
  function hud(force) {
    const now = performance.now();
    if (!force && now - lastHud < 60) return;
    lastHud = now;
    const live = S.foes.filter(f => !f.dead), seen = S.foes.map(f => f.seen).filter(x => x !== null);
    let clock = '–';
    if (MODE === 'track' && S.track) clock = S.track.all ? Math.round(S.track.head / S.track.all * 100) + ' %' : '0 %';
    else if (MODE === 'clear') clock = S.hides.some(h => h.off !== null) ? Math.round(placement()) + ' %' : '–';
    else if (MODE === 'attack') clock = S.phase === 'run' || S.phase === 'between' ? S.t.toFixed(1) + ' s' : '–';
    else if (S.phase === 'run' && seen.length && live.length) clock = (S.t - Math.min(...seen)).toFixed(2) + ' s';
    else if (S.reps.length && S.phase === 'between' && S.reps[S.reps.length - 1] !== null) clock = S.reps[S.reps.length - 1].toFixed(2) + ' s';
    $('dr-clock').textContent = clock;
    const sub2 = MODE === 'death' ? [T('his time'), D.his !== null && D.his !== undefined ? D.his.toFixed(2) + ' s' : '–']
      : MODE === 'hold' ? [T('they shoot after'), react.toFixed(2) + ' s']
      : MODE === 'track' ? [T('time left'), Math.max(0, (S.track ? S.track.secs : 30) - S.t).toFixed(0) + ' s']
      : MODE === 'attack' ? [T('defenders left'), `${live.length} / ${S.foes.length}`]
      : [T('spots checked'), `${S.hides.filter(h => h.off !== null).length} / ${S.hides.filter(h => h.open !== -1).length}`];
    $('dr-his-l').textContent = sub2[0]; $('dr-his').textContent = sub2[1];
    const pct = MODE === 'track' || MODE === 'clear';
    $('dr-reps').innerHTML = Array.from({length: Math.min(opt.reps, 40)}, (_, i) => {
      const v = S.reps[i];
      const good = v !== null && v !== undefined && (pct ? v >= 60 : MODE === 'death' ? (D.his === null || D.his === undefined || v < D.his) : MODE === 'hold' ? v < react : true);
      const cls = i < S.reps.length ? (v === null ? 'miss' : good ? 'beat' : 'slow') : (i === S.reps.length ? 'now' : '');
      return `<i class="${cls}" title="${esc(T('Rep'))} ${i + 1}"></i>`;
    }).join('');
    $('dr-rep').textContent = `${T('Rep')} ${Math.min(opt.reps, S.reps.length + (S.phase === 'between' ? 0 : 1))} / ${opt.reps}`;
    const rel = S.reload > performance.now() / 1000;
    $('dr-ammo').innerHTML = rel ? `<b>${esc(T('Reloading…'))}</b>` : `<b>${S.ammo}</b> / ${gun.mag} · <span translate="no">${esc(gun.name)}</span>`;
    $('dr-flash').style.opacity = String(Math.min(1, S.flash * 1.1));
    $('dr-msg').innerHTML = S.msg;
    $('dr-msg').hidden = !S.msg || S.phase === 'done';
    if (MOVING) {
      const sp = speed(), el = $('dr-move');
      el.hidden = S.phase === 'done';
      const band = sp <= ACCURATE ? ['good', T('Still: accurate')] : sp <= WALK ? ['warn', T('Slowing down')] : ['bad', T('Moving: shots go wide')];
      el.innerHTML = `<div class="dr-meter"><i style="left:${Math.min(100, sp / RUN * 100)}%"></i></div><span class="${band[0]}">${esc(band[1])}</span>`;
    }
  }
  let markT = 0;
  function marker(part, wide) {
    const el = $('dr-hit');
    el.textContent = T(part === 'head' ? 'HEAD' : part === 'body' ? 'BODY' : part === 'legs' ? 'LEGS' : 'MISS') + (wide ? ' · ' + T('moving') : '');
    el.className = 'dr-hit ' + part; el.hidden = false;
    clearTimeout(markT); markT = setTimeout(() => { el.hidden = true; }, 500);
  }
  const keyName = a => KB.label((keys[a] || [])[0]) || '–';
  const INTRO = {
    death: 'You stand where you died, looking where you looked. He comes out the same way he did. Kill him before his time.',
    hold: 'Hold the angle. They peek from the real corner, one at a time (sometimes two). Kill each before he has you for his reaction time.',
    attack: 'Take the spot: move up and peek the defenders on their usual places. Stop before you shoot (counter-strafe): shots while moving go wide.',
    track: 'He strafes left and right. Stay on his head for 30 seconds.',
    clear: 'Walk the route onto the site. Have your crosshair on each hiding place, at head height, the moment it opens. Some have an enemy.'};
  function panel(err) {
    const el = $('dr-panel');
    if (err) { el.hidden = false; el.innerHTML = `<p class="bad">${esc(err)}</p><p><a class="btn" href="${esc(C.list)}">${esc(T('Back to the list'))}</a></p>`; return; }
    if (S.phase === 'loading') { el.hidden = false; el.innerHTML = `<p>${esc(T('Loading the drill…'))}</p>`; return; }
    if (S.phase === 'ready' || S.paused) {
      el.hidden = false;
      const moveKeys = MOVING ? ` · ${['forward', 'left', 'back', 'right'].map(keyName).join('')} ${esc(T('move'))} · ${esc(keyName('walk'))} ${esc(T('walk'))} · ${esc(keyName('crouch'))} ${esc(T('crouch'))}` : '';
      el.innerHTML = `<h2>${esc(S.paused ? T('Paused') : MODE === 'death' ? T('Your death as a drill') : title())}</h2>` +
        `<p>${esc(T(INTRO[MODE]))}</p>` +
        (MODE === 'death' ? `<p class="dr-his">${esc(T('His time'))}: <b>${D.his !== null && D.his !== undefined ? D.his.toFixed(2) + ' s' : '–'}</b></p>` : '') +
        `<p class="muted small">${esc(keyName('shoot'))} ${esc(T('shoot'))} · ${esc(keyName('reload'))} ${esc(T('reload'))}${moveKeys} · ${esc(keyName('restart'))} ${esc(T('again'))}${MODE === 'death' ? ` · ${esc(keyName('watch'))} ${esc(T('watch how he did it'))}` : ''} · Esc ${esc(T('stop'))}</p>` +
        `<p><button type="button" class="btn primary" data-a="go">${esc(S.paused ? T('Go on') : T('Start · click'))}</button> ` +
        `<button type="button" class="btn ghost" data-a="opts">${esc(T('Options & keys'))}</button></p>`;
      return;
    }
    if (S.phase === 'done') { result(); return; }
    el.hidden = true;
  }
  function done() {
    S.phase = 'done'; S.firing = false; S.held.clear();
    if (document.pointerLockElement === canvas) document.exitPointerLock();
    save();
    result();
  }
  const median = a => { const s = a.slice().sort((x, y) => x - y); return s.length ? s[s.length >> 1] : null; };
  const avg = a => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);
  function matchOff() {                    // how far off his corner you looked in the match (degrees)
    if (MODE !== 'death') return null;
    const t = D.t_kill - (D.his ?? 0.6), k = NM.atClamped(S.R.paths[D.killer], t);
    if (!k) return null;
    const v = [k[0] - D.me[0], k[2] - D.me[2]], f = [Math.sin(D.me[3]), -Math.cos(D.me[3])], L = Math.hypot(...v) || 1;
    return Math.acos(Math.max(-1, Math.min(1, (v[0] * f[0] + v[1] * f[1]) / L))) / D2R;
  }
  function details() {                      // a few numbers per mode, kept with the run
    const out = {};
    if (MODE === 'hold') for (const [k, v] of Object.entries(S.styles)) out['style_' + k] = median(v);
    if (MOVING) {
      const sh = S.shots;
      out.still = sh.length ? sh.filter(s => s.sp <= ACCURATE).length / sh.length * 100 : 0;
      out.deaths = S.deaths; out.kills = S.kills;
    }
    if (MODE === 'track' && S.track) out.body = S.track.all ? S.track.body / S.track.all * 100 : 0;
    return out;
  }
  function result() {
    const el = $('dr-panel'), vals = S.reps.filter(v => v !== null);
    const pct = MODE === 'track' || MODE === 'clear';
    const his = MODE === 'death' ? D.his ?? null : MODE === 'hold' ? react : null;
    const good = v => (pct ? v >= 60 : his === null || v < his);
    const beat = vals.filter(good).length;
    const best = vals.length ? (pct ? Math.max(...vals) : Math.min(...vals)) : null, med = median(vals);
    const fmt = v => (v === null ? '–' : pct ? Math.round(v) + ' %' : v.toFixed(2) + ' s');
    const top = pct ? 100 : Math.max(his || 0, ...vals, 0.3) * 1.15;
    const bars = S.reps.map((v, i) => `<div class="dr-bar"><span>${v === null ? T('miss') : pct ? Math.round(v) + '%' : v.toFixed(2)}</span>` +
      `<i class="${v === null ? 'miss' : good(v) ? 'beat' : 'slow'}" style="height:${v === null ? 100 : Math.max(3, Math.round(v / top * 100))}%"></i><small>${i + 1}</small></div>`).join('');
    const off = avg(S.offs), mo = matchOff();
    const h = C.history || {}, meds = (h.medians || []).concat(med !== null ? [med] : []);
    const head = MODE === 'death' && his !== null ? `${esc(T('You beat him'))} <span class="good">${beat} / ${S.reps.length}</span>`
      : MODE === 'hold' ? `${esc(T('Peeks won'))} <span class="good">${beat} / ${S.reps.length}</span>`
      : MODE === 'attack' ? `${esc(T('Spot taken'))} <span class="good">${vals.length} / ${S.reps.length}</span>`
      : MODE === 'track' ? `${esc(T('On his head'))} <span class="good">${fmt(best)}</span>`
      : MODE === 'clear' ? `${esc(T('Crosshair placement'))} <span class="good">${fmt(med)}</span>`
      : `${esc(T('Kills'))} <span class="good">${vals.length} / ${S.reps.length}</span>`;
    const facts = [];
    if (MODE !== 'track') facts.push(`<div><b>${esc(T('Your first shots'))}</b><p><span class="hd">${esc(T('head'))} ${S.firsts.head}</span> <span>${esc(T('body'))} ${S.firsts.body}</span> <span>${esc(T('legs'))} ${S.firsts.legs}</span> <span class="bad">${esc(T('missed'))} ${S.firsts.miss}</span></p></div>`);
    if (MODE === 'death' || MODE === 'hold' || MODE === 'attack')
      facts.push(`<div><b>${esc(T('Your crosshair when he appeared'))}</b><p>${off !== null ? `${esc(T('On average'))} ${Math.round(off)}° ${esc(T('off him'))}.` : '–'}${mo !== null ? ` ${esc(T('In the match:'))} ${Math.round(mo)}°.` : ''}</p></div>`);
    if (MODE === 'hold') {
      const rows = Object.entries(S.styles).map(([k, v]) => `<span>${esc(T(STYLE[k] || k))} <b>${median(v).toFixed(2)} s</b></span>`).join(' ');
      facts.push(`<div><b>${esc(T('By kind of peek'))}</b><p>${rows || '–'}</p></div>`);
    }
    if (MOVING) {
      const sh = S.shots, st = sh.filter(s => s.sp <= ACCURATE);
      const stopT = avg(st.filter(s => s.still > 0).map(s => s.still * 1000));
      facts.push(`<div><b>${esc(T('Stopped when you shot'))}</b><p>${sh.length ? `${Math.round(st.length / sh.length * 100)} % ${esc(T('of your shots'))}${stopT !== null ? ` · ${esc(T('after'))} ${Math.round(stopT)} ms` : ''}` : '–'}</p></div>`);
    }
    if (MODE === 'track' && S.track) {
      const bins = S.track.bins.map(b => (b && b[0] ? b[1] / b[0] : 0));
      facts.push(`<div class="dr-wide"><b>${esc(T('On his head, second by second'))}</b><p class="dr-bins">${bins.map(v => `<i class="${v >= 0.6 ? 'beat' : v >= 0.3 ? 'slow' : 'miss'}"></i>`).join('')}</p></div>`);
      facts.push(`<div><b>${esc(T('On him at all'))}</b><p>${S.track.all ? Math.round(S.track.body / S.track.all * 100) : 0} %</p></div>`);
    }
    if (MODE === 'clear') facts.push(`<div><b>${esc(T('Hiding places'))}</b><p>${S.hides.map(h2 => `<span class="${h2.off === null ? '' : h2.off <= 7 ? 'good' : 'bad'}">${h2.off === null ? '–' : Math.round(h2.off) + '°'}</span>`).join(' ')} · ${esc(T('kills'))} ${S.kills} · ${esc(T('deaths'))} ${S.deaths}</p></div>`);
    facts.push(`<div><b>${esc(T('Since the first time'))}</b><p>${meds.length > 1 ? `${esc(T('Median per session'))}: ${meds.slice(-5).map(fmt).join(' → ')}` : esc(T('Your first session on this spot.'))}</p></div>`);
    el.hidden = false;
    el.innerHTML = `<div class="dr-res">
      <p class="muted small" translate="no">${esc(D.map)} · ${esc(MODE === 'death' ? `${D.where} · ${D.killer_agent} · ${D.weapon}` : title())}</p>
      <h2>${head}</h2>
      <div class="dr-nums"><div><b class="good">${fmt(best)}</b><small>${esc(T('your best'))}</small></div>
        <div><b>${fmt(med)}</b><small>${esc(T('your median'))}</small></div>
        ${his !== null && !pct ? `<div><b class="bad">${his.toFixed(2)} s</b><small>${esc(T(MODE === 'hold' ? 'their reaction' : 'his time'))}</small></div>` : ''}</div>
      ${S.reps.length > 1 ? `<div class="dr-bars">${his !== null && !pct ? `<div class="dr-his-line" style="bottom:${Math.round(his / top * 100)}%"><span>${esc(T(MODE === 'hold' ? 'theirs' : 'his'))} ${his.toFixed(2)} s</span></div>` : ''}${bars}</div>` : ''}
      <div class="dr-facts">${facts.join('')}</div>
      <p class="dr-btns">${C.next ? `<a class="btn primary" href="${esc(C.next)}">${esc(T('Next drill'))}</a>` : ''}
        <button type="button" class="btn ${C.next ? '' : 'primary'}" data-a="again">${esc(T('Again'))} (${esc(keyName('restart'))})</button>
        ${C.watch ? `<a class="btn ghost" href="${esc(C.watch)}">${esc(T('Watch the real death in the replay'))}</a>` : ''}
        <a href="${esc(C.list)}">${esc(T('Back to the list'))}</a></p>
      <p class="muted small" id="dr-saved">${C.can_save ? '' : esc(T('Not saved: this isn\'t your player.'))}</p></div>`;
  }
  async function save() {
    if (!C.can_save || S.saved || !S.reps.length) return;
    S.saved = true;
    try {
      const r = await fetch(C.runs_api, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({kind: MODE, reps: S.reps, his: MODE === 'death' ? D.his ?? null : MODE === 'hold' ? react : null,
                              first: S.firsts, off: avg(S.offs), detail: details()})});
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
    if (S.phase === 'ready' || S.phase === 'done') restart();
  }
  document.addEventListener('pointerlockchange', () => {
    if (document.pointerLockElement === canvas) return;
    S.firing = false; S.ads = false; S.held.clear();
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
    if (down) S.held.add(code); else S.held.delete(code);
    for (const a of KB.actionsOf(keys, code)) {
      if (a === 'shoot') { S.firing = down; if (down) shoot(); }
      else if (a === 'ads') S.ads = down && (gun.zoom || 1) > 1;
      else if (!down) continue;
      else if (a === 'reload') startReload();
      else if (a === 'restart') { if (document.pointerLockElement !== canvas) lock(); S.paused = false; restart(); }
      else if (a === 'next') { if (S.phase === 'between' && !S.paused) S.until = 0; }
      else if (a === 'watch') { if (MODE === 'death' && (document.pointerLockElement === canvas || S.phase === 'done')) { if (S.phase === 'done') lock(); watch(); } }
      else if (a === 'full') {
        const el = $('dr');
        if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
        else if (el.requestFullscreen) el.requestFullscreen().then(() => {     // Ctrl & co. stay in the page
          try { if (navigator.keyboard && navigator.keyboard.lock) navigator.keyboard.lock(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyC']).catch(() => {}); } catch (err) {}
        }).catch(() => {});
      }
    }
  }
  const locked = () => document.pointerLockElement === canvas;
  const typing = e => /INPUT|TEXTAREA|SELECT/.test((e.target && e.target.tagName) || '');
  document.addEventListener('keydown', e => {
    if (typing(e) || !$('dr-opts').hidden) return;
    if (e.code === 'Escape') return;
    if (!locked() && !['restart', 'full', 'watch'].some(a => keys[a] && keys[a].includes(e.code))) return;
    if (KB.actionsOf(keys, e.code).length || (locked() && e.ctrlKey)) e.preventDefault();
    if (!e.repeat) act(e.code, true);
  });
  document.addEventListener('keyup', e => { if (locked() || S.held.has(e.code)) act(e.code, false); });
  window.addEventListener('blur', () => { S.held.clear(); S.firing = false; });
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
    $('dr-o-speed').closest('label').hidden = MODE !== 'death';
    $('dr-o-reps').closest('label').hidden = MODE !== 'death';
    KB.editor($('dr-keys'), {keys, defaults: C.defaults || keys, actions: C.actions, api: C.keys_api, onSave: k => { keys = k; panel(); }});
  }
  $('dr-opts').addEventListener('change', () => {
    opt.heads = $('dr-o-heads').checked;
    if (MODE === 'death') { opt.speed = +$('dr-o-speed').value || 1; opt.reps = +$('dr-o-reps').value || 10; }
    saveOpt(); hud(true);
  });
  $('dr-opts-x').addEventListener('click', () => { $('dr-opts').hidden = true; panel(); });

  // ------------------------------------------------------------------------------------------ start
  if (MODE === 'death') {
    $('dr-info').innerHTML = `<b translate="no">${esc(D.map)} · ${esc(D.where || '?')}</b><small><span translate="no">${esc(D.killer_agent)} · ${esc(D.weapon)}</span>` +
      `${D.kwhere ? ' · ' + esc(T('from')) + ' <span translate="no">' + esc(D.kwhere) + '</span>' : ''}${D.first === 'killer' ? ' · ' + esc(T('he saw you first')) : ''}</small>`;
  } else {
    const what = MODE === 'hold' ? (O.styles || []).map(s => T(STYLE[s] || s)).join(', ') : MODE === 'track' ? 'ADAD'
      : MODE === 'attack' ? `${Math.min(3, SP.defs.length)} ${T('defenders')}` : `${SP.hides.length} ${T('hiding places')}`;
    const diff = (O.diff || 'medium').replace(/^./, c => c.toUpperCase());
    $('dr-info').innerHTML = `<b translate="no">${esc(D.map)} · ${esc(title())}</b><small>${esc(T(diff))} · <span translate="no">${esc(gun.name)}</span> · ${esc(what)}</small>`;
  }
  if (C.anims && V().anims) V().anims(C.anims);
  V().setLayer({tick, models, objects, radar, ready: () => camera()});
  V().setOpt('labels', false); V().setOpt('radar', true);    // like the game: the minimap in the corner (not saved)
  panel();
  load();
  window.nexusDrill = {state: () => ({phase: S.phase, t: S.t, reps: S.reps.slice(), seen: S.foes.length ? S.foes[0].seen : null,
                                      kill: S.foes.some(f => f.dead), ammo: S.ammo, yaw: S.yaw, pitch: S.pitch,
                                      hp: S.foes.length ? S.foes[0].hp : null, firsts: {...S.firsts}, paused: S.paused,
                                      foes: S.foes.length, me: {...S.me}, speed: speed(), mode: MODE, dead: S.dead,
                                      hides: S.hides.map(h => ({open: h.open, off: h.off}))}),
                       hitboxes: (i = 0) => (S.foes[i] ? hitboxes(S.foes[i]) : []),
                       aimAt: p => { const v = sub(p, eye()), L = Math.hypot(...v); S.yaw = Math.atan2(v[0], -v[2]); S.pitch = Math.asin(v[1] / L); },
                       shoot: () => { shoot(); }, start: () => { restart(); }, eye, keys: () => keys, act, models,
                       // for tests: stand dist metres in front of where he is at t (he faces you)
                       faceOff: (t, dist) => {
                         const p = NM.atClamped(S.R.paths[D.killer], t), f = [Math.sin(p[3]), -Math.cos(p[3])];
                         D.me = [p[0] + f[0] * dist, p[1], p[2] + f[1] * dist, Math.atan2(-f[0], f[1])]; place(D.me);
                       },
                       goTo: p => { S.me.x = p[0]; S.me.y = p[1]; S.me.z = p[2]; },          // for tests: stand there
                       trackSecs: s => { if (S.track) S.track.secs = s; },                  // for tests: shorter
                       foeAt: (i = 0) => (S.foes[i] ? foeAt(S.foes[i], S.t) : null), spot: () => SP,
                       foeDead: i => !!(S.foes[i] && S.foes[i].dead)};
})();
