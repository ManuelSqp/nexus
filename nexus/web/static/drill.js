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
//   entry  (4.54) first onto a site: the attackers' route in, defenders on the places they hid (one of them swings
//          you when you get close); take the site.
//   retake (4.54) the spike is down: come in on the defenders' real way back, kill the attackers on their post-plant
//          places and defuse (hold your key; half a defuse stays) before it goes off.
//   postplant (4.54) you play the spike after the plant: the retakers come in on their real routes, at their real
//          speed; kill each before he has you, and before anyone defuses.
// 4.56: the enemies use their utility (hold, attack, entry, retake, post-plant): what their side really threw around
// these fights in your replays (one round's worth a rep), at its real time: smokes and walls block sight, a flash
// blinds you if you look at it, mollies burn you (you have 150), slows slow you, recon and traps reveal you (they
// pre-aim: quicker, and they don't need to be looking your way).
// 4.58: your own abilities (hold, attack, entry, retake, post-plant; the agent you pick on the spot): C, Q and E on
// your keys, quick-cast where you aim (stats/kits.py says what each one is): smokes and walls block their sight,
// a flash blinds whoever looks at it (you too), a molly burns them (and you), a concuss / nearsight / tether stops
// them fighting you for a moment, recon and traps reveal them, a dash / teleport / anchor moves you.
// 4.72: retakes like in the game: the attackers hold a crossfire on the spike, one of them shifts after a few
// seconds, and a defuse is heard (whoever can't see you peeks the spike: tap it to bait them). After a lost duel
// (every drill) a few seconds of replay from your killer's eyes: what he saw of you, and why you lost it
// (drillai.js: the attackers' plan, the replay's path and the reasons).
// The spots and routes come from the fights in all replays of the map (stats/drills.py spots()).
(function () {
  'use strict';
  const C = window.NEXUS_MAP3D;
  if (!C || !C.drill) return;
  const MODE = C.mode || 'death', D = C.drill, SP = C.spot || null, O = C.opts || {};
  const NM = window.NexusMotion, KB = window.NexusKeys, AI = window.NexusDrillAI;
  const $ = id => document.getElementById(id);
  const T = s => (window.vcT ? window.vcT(s) : s);
  const V = () => window.nexusMap3D;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const D2R = Math.PI / 180, YAW = 0.07, VFOV = 70.53;
  const EYE = 1.85, EYE_CROUCH = 1.35, MAP_EYE = 1.6;   // your eyes above your feet; map3d.js adds MAP_EYE
  const HEAD_R = 0.14, BODY_R = 0.2, ARM_R = 0.07, LEG_R = 0.1;
  const WATCH = 0.35;                       // "watch how he did it": this fast
  const ENEMY = [0.86, 0.3, 0.36];
  // moving like Valorant (m/s): running, walking, crouching; how fast you speed up and stop; above ACCURATE the
  // first shot goes wide (up to SPREAD degrees at full speed)
  const RUN = 6.75, WALK = 3.6, CROUCH = 2.4, ACCEL = 40, STOP = 55, ACCURATE = 1.75, SPREAD = 6;
  const MOVING = MODE === 'attack' || MODE === 'clear' || MODE === 'entry' || MODE === 'retake';
  const SPIKE = MODE === 'retake' || MODE === 'postplant';
  const NFOES = O.foes || 2, DEFUSE = O.defuse || 7;
  const canvas = $('m3-canvas');
  let keys = KB.normalize(C.keys, C.defaults);
  const opt = {speed: 1, heads: true, reps: O.reps || 10, replay: true};
  if (MODE === 'death') try { Object.assign(opt, JSON.parse(localStorage.getItem('nexus.drill') || '{}')); } catch (e) {}
  else try {
    const o = JSON.parse(localStorage.getItem('nexus.drill') || '{}');
    opt.heads = o.heads !== false; opt.replay = o.replay !== false;
  } catch (e) {}
  const saveOpt = () => {
    try {
      const old = JSON.parse(localStorage.getItem('nexus.drill') || '{}');
      localStorage.setItem('nexus.drill', JSON.stringify(MODE === 'death' ? opt : Object.assign(old, {heads: opt.heads, replay: opt.replay})));
    } catch (e) {}
  };
  const REPLAY_S = 3, REPLAY_SPEED = 0.75, TRAIL_S = 4;   // the death replay: the last 3 s, a bit slowed down
  const ME_COL = [0.18, 0.77, 0.7];
  const gun = C.gun, HP = C.hp || 150;
  const react = O.react || 0.6;
  const UTIL = !!O.util && MODE !== 'death';
  const ENEMY_SIDE = {hold: 'a', attack: 'd', entry: 'd', retake: 'a', postplant: 'd'}[MODE] || null;
  const HP_ME = 150;                        // 100 + heavy shields
  // molly damage a second (close to the game's); anything else that burns: DPS_DEFAULT
  const DPS = {Brimstone: 60, Phoenix: 60, 'KAY/O': 60, Killjoy: 45, Viper: 24, Raze: 55, Gekko: 40, Tejo: 50, Vyse: 40};
  const DPS_DEFAULT = 40, SLOW = 0.5, REVEAL_REACT = 0.6, SOLID_A = 1.8;
  const KIT = O.kit || null, AGENT = O.agent || '';
  const SLOT_OF = {ab_c: 'C', ab_q: 'Q', ab_e: 'E'};
  const AGENTS = Object.keys(C.agents || {});
  const RIFLES = ['Vandal', 'Phantom', 'Vandal', 'Phantom', 'Spectre', 'Sheriff'];
  const pick = a => a[Math.floor(Math.random() * a.length)];
  const S = {phase: 'loading', R: null, t: 0, t0: 0, reps: [], foes: [], yaw: 0, pitch: 0, ammo: gun.mag, reload: 0,
             next: 0, firing: false, ads: false, first: null, firsts: {head: 0, body: 0, legs: 0, miss: 0}, offs: [],
             flash: 0, until: 0, msg: '', lastT: 0, paused: false, saved: false, held: new Set(), dead: false,
             me: {x: 0, y: 0, z: 0, vx: 0, vz: 0, crouch: false, still: 0}, styles: {}, shots: [], track: null,
             hides: [], deaths: 0, kills: 0, spike: null, defusing: false, lefts: [],
             U: [], hp: HP_ME, revealed: 0, slowed: false, burnt: 0, utilReps: 0, teamUtil: 0,
             kit: {}, anchor: {}, tp: null, fast: 0, fastMult: 1, casts: 0, toast: '', toastT: 0,
             trail: [], rp: null, heard: false};

  // ------------------------------------------------------------------------------------------ where you stand
  function home() {                       // where a rep starts: [x, y, z, yaw]
    if (MODE === 'death') return D.me;
    if (MODE === 'attack') return SP._start || [...SP.start, SP.start_yaw];
    if (MODE === 'clear' || MODE === 'entry') {
      const i = SP._from || 0, p = SP.route[i];
      return [p[0], p[1], p[2], yawTo(p, SP.route[Math.min(SP.route.length - 1, i + 4)])];
    }
    if (MODE === 'retake') {                // the start of the way back in, looking along it
      const R = myRoute(), p = R[0], q = R.find(x => Math.hypot(x[0] - p[0], x[2] - p[2]) > 2) || SP.plant;
      return [p[0], p[1], p[2], yawTo(p, q)];
    }
    if (MODE === 'postplant') return SP._posts[S.reps.length % SP._posts.length];
    return SP._stand || [...SP.hold, SP.hold_yaw];
  }
  // retake: one of the defenders' ways back in, rep by rep
  const myRoute = () => SP.routes[S.reps.length % SP.routes.length].path;
  // post-plant: the places attackers played the spike from (the three most used, rep by rep), looking where the
  // retakers first show up
  function postStands() {
    return SP.posts.slice(0, 3).map(p => {
      const e = [p[0], p[1] + EYE, p[2]];
      let q = null;
      for (const r of SP.routes) { q = r.path.find(x => V().visible(e, [x[0], x[1] + 1.6, x[2]])); if (q) break; }
      return [p[0], p[1], p[2], yawTo(p, q || SP.routes[0].path[SP.routes[0].path.length - 1])];
    });
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
  // entry: only hiding places you can see from somewhere on the way in (one you'd never find isn't a fair fight)
  function fairHides() {
    const R = SP.route.slice(SP._from || 0), out = [];
    SP.hides.forEach((h, i) => {
      const head = [h[0], h[1] + 1.6, h[2]];
      if (R.some(q => V().visible([q[0], q[1] + EYE, q[2]], head))) out.push(i);
    });
    return out.length ? out : SP.hides.map((h, i) => i);
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
  const utilList = () => (S.R ? S.R.util || [] : S.U);       // a death drill: the round's; else their utility (4.56)
  function smokes() { return NM.utilObjects(utilList(), S.t, C.util_col).filter(o => o.block); }
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
    if (S.t < (f.blind || 0) || S.t < (f.daze || 0)) return false;    // flashed, concussed, caught (4.58)
    const p = foeAt(f, S.t), e = [p[0], p[1] + 1.75, p[2]];
    if (f.fov && !(S.t < S.revealed)) {        // revealed: they know where you are
      const d = norm([S.me.x - p[0], 0, S.me.z - p[2]]), fwd = [Math.sin(p[3]), 0, -Math.cos(p[3])];
      if (dot(d, fwd) < Math.cos(f.fov * D2R)) return false;
    }
    return clear(e, eye()) || clear(e, [S.me.x, S.me.y + 1.1, S.me.z]);
  }
  function prepPath(path) {
    const floors = path.map(r => r[6]);                  // our paths know the floor (crouching = lower than it)
    NM.prep({p: path});
    path.forEach((r, k) => { if (floors[k] !== undefined) r[6] = floors[k]; });
    return path;
  }
  function foe(i, path, extra = {}) {
    const agent = extra.agent || pick(AGENTS.length ? AGENTS : ['']);
    prepPath(path);
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

  // post-plant: a retaker on his real way in (a point every half second, at his real speed), then straight to the
  // spike and down on it to defuse; f.at: when he gets there
  function retakePath(R, delay) {
    const out = [], row = (t, p, yaw, dy = 0) => out.push([t, p[0], p[1] + dy, p[2], yaw, 0, p[1]]);
    let yaw = yawTo(R[0], R.find(q => Math.hypot(q[0] - R[0][0], q[2] - R[0][2]) > 1) || SP.plant);
    row(-1, R[0], yaw);
    R.forEach((q, i) => {
      const n = R[i + 1];
      if (n && Math.hypot(n[0] - q[0], n[2] - q[2]) > 0.05) yaw = yawTo(q, n);
      row(delay + i * 0.5, q, yaw);
    });
    let t = delay + (R.length - 1) * 0.5, cur = R[R.length - 1].slice();
    const P = SP.plant, d = Math.hypot(P[0] - cur[0], P[2] - cur[2]), n = Math.max(1, Math.ceil(d / (RUN * 0.1)));
    yaw = yawTo(cur, P);
    for (let i = 1; i <= n; i++) {
      const k = i / n, x = cur[0] + (P[0] - cur[0]) * k, z = cur[2] + (P[2] - cur[2]) * k;
      t += d / RUN / n; row(t, [x, floor(x, z, cur[1]) ?? cur[1], z], yaw);
    }
    const at = t, end = [P[0], floor(P[0], P[2], cur[1]) ?? P[1], P[2]];
    row(t + 0.3, end, yaw, -0.45); row(t + 60, end, yaw, -0.45);
    return [out, at];
  }
  // entry: the defender who swings you when you get close (he heard you): out of his place towards you, at a run
  function swing(f, delay = 0) {          // 4.72: delay: he reacts to a sound first
    const p = foeAt(f, S.t), dx = S.me.x - p[0], dz = S.me.z - p[2], L = Math.hypot(dx, dz) || 1;
    const fl = floor(p[0], p[2], p[1]) ?? p[1];
    const before = (f.path || []).filter(r => r[0] < S.t).map(r => r.slice(0, 7));   // kept for the death replay
    const out = [...(before.length ? before : [[-1, p[0], fl, p[2], p[3], 0, fl]]), ...(delay > 0 ? [[S.t, p[0], p[1], p[2], p[3], 0, fl]] : []),
                 [S.t + delay, p[0], fl, p[2], yawTo(p, eye()), 0, fl]];
    let cur = [p[0], fl, p[2]], t = S.t + delay;
    for (let s = 0.2; s <= 2.4; s += 0.2) {
      const x = p[0] + dx / L * s, z = p[2] + dz / L * s, y = floor(x, z, cur[1]);
      if (y === null || V().blocked(x, z, y)) break;
      t += 0.2 / RUN; cur = [x, y, z];
      out.push([t, x, y, z, yawTo(cur, eye()), 0, y]);
    }
    out.push([t + 60, cur[0], cur[1], cur[2], yawTo(cur, eye()), 0, cur[1]]);
    f.path = prepPath(out); f.swing = 'done';
  }

  // 4.72 retake: an attacker who shifts: on his place until at, then walks (quietly) to the other place and holds
  // there, looking where retakers come from
  function shiftPath(from, to, at, R, crouch) {
    const y0 = from[1] - (crouch ? 0.45 : 0), yaw0 = yawTo(from, nearestOn(R, from));
    const out = [[-1, from[0], y0, from[2], yaw0, 0, from[1]], [at, from[0], y0, from[2], yaw0, 0, from[1]]];
    const d = Math.hypot(to[0] - from[0], to[2] - from[2]), n = Math.max(1, Math.ceil(d / 0.2)), yaw = yawTo(from, to);
    let t = at, cur = from.slice();
    for (let i = 1; i <= n; i++) {
      const k = i / n, x = from[0] + (to[0] - from[0]) * k, z = from[2] + (to[2] - from[2]) * k, y = floor(x, z, cur[1]);
      if (y === null || V().blocked(x, z, y)) break;
      t += d / n / WALK; cur = [x, y, z];
      out.push([t, x, y, z, yaw, 0, y]);
    }
    const look = yawTo(cur, nearestOn(R, cur));
    out.push([t + 0.3, cur[0], cur[1], cur[2], look, 0, cur[1]], [t + 999, cur[0], cur[1], cur[2], look, 0, cur[1]]);
    return out;
  }
  // a defuse is heard: whoever can't see you peeks the spike (a moment to react, then a swing at a run)
  function heard() {
    S.heard = true;
    for (const f of S.foes) if (!f.dead && f.swing !== 'done' && !seesMe(f)) swing(f, 0.25 + Math.random() * 0.45);
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
      if (MODE === 'clear' || MODE === 'entry') SP._from = clearStart();
      if (MODE === 'entry') SP._fair = fairHides();
      if (MODE === 'postplant') SP._posts = postStands();
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
    if (S.phase !== 'run' || S.dead || S.defusing) return;
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
    if (hit) {                                             // a wall in the way?
      // 4.70.1: the wall you see (the drawn map, along the shot); the see-through grid only when that can't tell
      // (the grid only ever errs toward "blocked", so the drawn map is asked only then: it costs a draw)
      if (!V().visible(o, add(o, d, Math.max(0, hit[2] - 0.05)))) {
        const wall = V().wallAlong ? V().wallAlong(o, d) : null;
        if (wall === null || wall < hit[2] - 0.02) hit = null;
      }
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
    } else if (MODE === 'attack' || MODE === 'entry') {
      S.reps.push(Math.round(S.t * 1000) / 1000);
      endRep(S.t, T(MODE === 'entry' ? 'Site taken' : 'Spot taken'));
    } else if (MODE === 'postplant') {      // how fast you got each of them once he could be seen
      const mine = avg(S.foes.map(x => Math.max(0, x.dead.t - (x.seen ?? x.dead.t))));
      S.reps.push(Math.round(mine * 1000) / 1000);
      endRep(mine);
    } else if (MODE === 'retake') S.msg = `<b class="good">${esc(T('All down: defuse the spike'))}</b>`;
  }

  // ------------------------------------------------------------------------------------------ the reps
  function startRep() {
    S.t = MODE === 'death' ? D.t0 : 0; S.lastT = S.t; S.t0 = S.t;
    place(home());
    S.dead = false; S.ammo = gun.mag; S.reload = 0; S.next = 0; S.first = null; S.flash = 0; S.msg = '';
    S.foes = []; S.spike = null; S.defusing = false; S.heard = false; S.trail = []; S.rp = null;
    S.U = []; S.hp = HP_ME; S.revealed = 0; S.slowed = false;
    resetKit();
    const uset = chooseUtil();
    if (MODE === 'death') {
      S.foes = [foe(0, S.R.paths[D.killer], {key: D.killer, agent: D.killer_agent, weapon: D.weapon, replay: true})];
    } else if (MODE === 'hold') {
      const styles = (O.styles || ['wide']).filter(s => s !== 'two');
      const two = (O.styles || []).includes('two') && SP.peeks.length > 1 && (!styles.length || Math.random() < 0.35);
      const open = SP.peeks.filter(P => seeFrom(eye(), [P[0], P[1] + 1.6, P[2]]));   // the corners you can see
      const from = (open.length ? open : SP.peeks).slice().sort(() => Math.random() - 0.5);
      const delay = Math.max(0.6 + Math.random() * 1.8, lead(uset));      // time for a flash before the peek
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
    } else if (MODE === 'entry') {
      const order = SP._fair.slice().sort(() => Math.random() - 0.5).slice(0, Math.min(NFOES, SP._fair.length));
      S.foes = order.map((i, k) => foe(k, still(SP.hides[i], yawTo(SP.hides[i], nearestOnRoute(SP.hides[i])), Math.random() < 0.3), {fov: 60}));
      if (S.foes.length) pick(S.foes).swing = 'wait';
    } else if (MODE === 'retake') {           // 4.72: a crossfire on the spike, one of them shifts (drillai.js)
      const R = myRoute(), plan = AI.retakePlan(SP.posts.slice(0, 6), SP.plant, Math.min(NFOES, SP.posts.length), (a, b) => V().visible(a, b));
      S.foes = plan.map((x, k) => {
        const crouch = !x.shift && Math.random() < 0.35;
        return foe(k, x.shift ? shiftPath(x.post, x.shift, x.at, R, false) : still(x.post, yawTo(x.post, nearestOn(R, x.post)), crouch),
                   {fov: 60, cross: x.cross, shifts: !!x.shift});
      });
      S.spike = {left: SP.left, prog: 0, half: false};
    } else if (MODE === 'postplant') {
      S.spike = {left: SP.left};
      for (let k = 0; k < NFOES; k++) {
        const R = SP.routes[k % SP.routes.length].path, delay = k ? 0.5 + Math.random() * 2.5 + (k >= SP.routes.length ? 1.2 : 0) : Math.random();
        const [path, at] = retakePath(R, delay);
        S.foes.push(foe(k, path, {fov: 70, at}));
      }
    }
    placeUtil(uset);
    if (MODE === 'clear') {
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
  // ------------------------------------------------------------------------------------------ their utility (4.56)
  // One round's worth of what both sides threw around these fights (spot.util: [[type, agent, side, seconds from
  // the fight (after a plant: from the plant), how long, x, y, z], …] a set); now and then a round without.
  // 4.65: your team's utility from the same round too: their flashes and stuns hit the enemies, their smokes block
  // sight both ways, their recon reveals the enemies, their mollies burn the enemies (and you, if you stand in them).
  function chooseUtil() {
    if (!UTIL || !SP) return null;
    const sets = (SP.util || []).filter(s => s.length);
    if (!sets.length || Math.random() < 0.15) return null;
    S.utilReps++;
    return pick(sets);
  }
  function lead(set) {                      // hold: the peek waits for a flash thrown just before it
    let l = 0;
    for (const u of set || []) if (u[0] === 'flash' && u[3] <= 0 && u[3] > -4) l = Math.max(l, -u[3] + 0.5);
    return Math.min(5, l);
  }
  function placeUtil(set) {
    if (!set) return;
    const ref = SPIKE ? SP.plant : MODE === 'hold' ? SP.hold : MODE === 'attack' ? SP.defs[0] : SP.route[SP.route.length - 1];
    for (const u of set) {
      const y = u[6] !== null ? (floor(u[5], u[7], u[6]) ?? u[6]) : (floor(u[5], u[7], ref[1]) ?? ref[1]);
      const it = {type: u[0], agent: u[1], rel: u[3], dur: u[4], x: u[5], y, z: u[7], t0: Infinity, t1: null, arm: false};
      if (u[2] !== ENEMY_SIDE) {            // 4.65: a teammate's: works on them like yours (TEAM_UTIL: blind, daze)
        Object.assign(it, {mine: true, team: true}, TEAM_UTIL[u[0]] || {});
        S.teamUtil++;
      }
      if (SPIKE || MODE === 'hold') {       // at its real time: from the plant (the spike's time), or from the peek
        it.t0 = SPIKE ? u[3] - (SPIKE_S - SP.left) : (S.foes.length ? S.foes[0].appear : 1) + 0.35 + u[3];
        it.t1 = u[4] === null ? null : it.t0 + u[4];
        if ((it.type === 'flash' && it.t0 < 0) || (it.t1 !== null && it.t1 < 0)) continue;
      } else it.arm = true;                 // attack, entry: when you get there (the fight is where they are)
      S.U.push(it);
    }
  }
  const SPIKE_S = O.spike || 45;
  const AREA_UTIL = new Set(['smoke', 'wall', 'damage', 'slow']);
  const TEAM_UTIL = {flash: {blind: 1.6}, stun: {r: 4.5, daze: 2.5}, trap: {daze: 2.5, used: false}, damage: {dps: 40}};
  function utilTarget() { return MODE === 'attack' ? SP.defs[0] : MODE === 'entry' ? SP.route[SP.route.length - 1] : null; }
  function utilTick(dt) {
    if (!S.U.length) return;
    const T0 = utilTarget(), toGo = T0 ? Math.hypot(T0[0] - S.me.x, T0[2] - S.me.z) : Infinity;
    let slowed = false;
    for (const u of S.U) {
      if (u.arm && toGo <= Math.max(0, -u.rel) * RUN * 0.8 + 4) {
        u.arm = false; u.t0 = S.t + Math.max(0.05, u.rel); u.t1 = u.dur === null ? null : u.t0 + u.dur;
      }
      if (!NM.live(u, S.t)) continue;
      const dh = Math.hypot(u.x - S.me.x, u.z - S.me.z), dy = Math.abs(u.y - S.me.y);
      if (u.type === 'damage' && dh < NM.R_UTIL.damage && dy < 2.5) {          // yours burns you too
        S.hp -= (u.dps || DPS[u.agent] || DPS_DEFAULT) * dt; S.burnt = S.t;
        if (u.mine) for (const f of S.foes) {                                    // and them
          if (f.dead || hiding(f)) continue;
          const p = foeAt(f, S.t);
          if (Math.hypot(u.x - p[0], u.z - p[2]) < NM.R_UTIL.damage && Math.abs(u.y - p[1]) < 2.5) { f.hp -= (u.dps || DPS_DEFAULT) * dt; if (f.hp <= 0) kill(f); }
        }
      } else if (u.mine) continue;              // your own recon and traps don't reveal you
      else if (u.type === 'slow' && dh < NM.R_UTIL.slow && dy < 2.5) slowed = true;
      else if (u.type === 'recon' && dh < 30 && S.t - u.t0 < 4 && V().visible([u.x, u.y + 1, u.z], eye())) S.revealed = Math.max(S.revealed, S.t + 1.5);
      else if (u.type === 'trap' && dh < 2.5 && dy < 2.5) S.revealed = Math.max(S.revealed, S.t + 3);
    }
    for (const u of S.U) {                    // your molly where they stand (out of your own reach above)
      if (!u.mine || u.type !== 'damage' || !NM.live(u, S.t)) continue;
      if (Math.hypot(u.x - S.me.x, u.z - S.me.z) < NM.R_UTIL.damage && Math.abs(u.y - S.me.y) < 2.5) continue;
      for (const f of S.foes) {
        if (f.dead || hiding(f)) continue;
        const p = foeAt(f, S.t);
        if (Math.hypot(u.x - p[0], u.z - p[2]) < NM.R_UTIL.damage && Math.abs(u.y - p[1]) < 2.5) { f.hp -= (u.dps || DPS_DEFAULT) * dt; if (f.hp <= 0) kill(f); }
      }
    }
    S.slowed = slowed;
    if (S.hp <= 0) { S.hp = 0; failRep(T('Burnt in their utility')); }
  }
  function utilIntro() {                    // what they'll throw (and what you have), on the start screen
    const mine = KIT ? `<p class="small">${esc(T('You play'))} <b translate="no">${esc(AGENT)}</b>: ${['C', 'Q', 'E'].filter(k => KIT[k]).map(s => `<kbd>${esc(keyName({C: 'ab_c', Q: 'ab_q', E: 'ab_e'}[s]))}</kbd> <span translate="no">${esc(KIT[s].name)}</span> ×${KIT[s].charges}`).join(' · ')} — ${esc(T('quick-cast where you aim; no ultimates.'))}</p>` : '';
    return mine + theirs();
  }
  function theirs() {
    if (!UTIL || !SP) return '';
    const n = (SP.util || []).filter(s => s.some(u => u[2] === ENEMY_SIDE)).length;
    const own = (SP.util || []).filter(s => s.some(u => u[2] !== ENEMY_SIDE)).length;   // 4.65: your team's
    return (n ? `<p class="muted small">${esc(T('They use their utility, as in'))} ${n} ${esc(T(n === 1 ? 'round of your replays' : 'rounds of your replays'))}: ${esc(T('smokes and walls block sight, look away from flashes, mollies burn (you have 150), recon and traps reveal you.'))}</p>` : '')
      + (own ? `<p class="muted small">${esc(T('Your team uses theirs too, from the same rounds'))} (${own}): ${esc(T('their flashes and stuns hit the enemies, their recon shows them, their smokes block both sides.'))}</p>` : '');
  }
  const wallAt = (x, z) => S.U.some(u => u.type === 'wall' && NM.live(u, S.t) && Math.hypot(u.x - x, u.z - z) < 1.0);

  // ------------------------------------------------------------------------------------------ your abilities (4.58)
  function resetKit() {
    S.kit = {}; S.anchor = {}; S.tp = null; S.fast = 0; S.fastMult = 1;
    for (const k of ['C', 'Q', 'E'].filter(k => (KIT || {})[k])) S.kit[k] = KIT[k].charges;
  }
  function toast(msg) { S.toast = msg; S.toastT = performance.now() / 1000; }
  // where you aim: the first wall along your view (or the range; through walls for a few), on the floor below it
  function aimPoint(range, through = false) {
    const e = eye(), d = look();
    let last = e;
    for (let s = 0.5; s <= range; s += 0.5) {
      const p = add(e, d, s);
      if (!through && !V().visible(e, p)) break;
      last = p;
    }
    const y = floor(last[0], last[2], last[1]);
    return [last[0], y ?? Math.max(S.me.y, last[1] - EYE), last[2]];
  }
  function cast(slot) {
    const a = KIT && KIT[slot];
    if (!a || S.phase !== 'run' || S.dead || S.defusing) return;
    if (a.kind === 'anchor' && S.anchor[slot]) {             // the second press: back to the marker
      const p = S.anchor[slot];
      if (Math.hypot(p[0] - S.me.x, p[2] - S.me.z) > a.range) { toast(T('Too far from your marker')); return; }
      S.me.x = p[0]; S.me.y = p[1]; S.me.z = p[2]; S.me.vx = 0; S.me.vz = 0; S.anchor[slot] = null;
      return;
    }
    if (!(S.kit[slot] > 0)) { toast(`${a.name}: ${T('none left')}`); return; }
    S.kit[slot]--; S.casts++;
    const mk = (type, p, t0, dur, extra = {}) => S.U.push({type, agent: AGENT, x: p[0], y: p[1], z: p[2], t0,
      t1: dur === null ? null : t0 + dur, mine: true, arm: false, rel: 0, dur, ...extra});
    switch (a.kind) {
      case 'smoke': mk('smoke', aimPoint(a.range), S.t + 0.6, a.dur); break;
      case 'flash': case 'flash_wall': mk('flash', aimPoint(a.range, a.kind === 'flash_wall'), S.t + (a.delay || 0.5), 0.5, {blind: a.dur}); break;
      case 'damage': mk('damage', aimPoint(a.range), S.t + 0.7, a.dur, {dps: a.dps}); break;
      case 'stun': mk('stun', aimPoint(a.range), S.t + 0.6, 0.8, {r: a.r, daze: a.dur}); break;
      case 'recon': mk('recon', aimPoint(a.range), S.t + 0.6, a.dur); break;
      case 'trap': mk('trap', aimPoint(a.range), S.t + 0.3, null, {daze: a.dur, used: false}); break;
      case 'wall': {                          // across your view: a row of pieces
        const p = aimPoint(a.range), rx = Math.cos(S.yaw), rz = Math.sin(S.yaw);
        for (let k = -3; k <= 3; k++) mk('wall', [p[0] + rx * k * 1.2, p[1], p[2] + rz * k * 1.2], S.t + 0.3, a.dur);
        break;
      }
      case 'dash': {                          // the way you're moving (or looking), up to dist, not through walls
        const m = S.me, sp = Math.hypot(m.vx, m.vz);
        const dx = sp > 0.5 ? m.vx / sp : Math.sin(S.yaw), dz = sp > 0.5 ? m.vz / sp : -Math.cos(S.yaw);
        for (let s = 0.25; s <= a.dist; s += 0.25) {
          const x = m.x + dx * 0.25, z = m.z + dz * 0.25, y = floor(x, z, m.y);
          if (y === null || V().blocked(x, z, y) || wallAt(x, z)) break;
          m.x = x; m.z = z; m.y = y;
        }
        break;
      }
      case 'teleport': S.tp = {t: S.t + (a.delay || 0.8), p: aimPoint(a.range)}; break;
      case 'anchor': S.anchor[slot] = [S.me.x, S.me.y, S.me.z]; toast(`${a.name}: ${T('press again to go back')}`); break;
      case 'speed': S.fast = S.t + a.dur; S.fastMult = a.mult || 1.25; break;
    }
  }
  function myTick() {                         // what your abilities do to them
    if (S.tp && S.t >= S.tp.t) { const p = S.tp.p; S.me.x = p[0]; S.me.y = p[1]; S.me.z = p[2]; S.me.vx = 0; S.me.vz = 0; S.tp = null; }
    for (const u of S.U) {
      if (!u.mine) continue;
      const pops = u.t0 > S.lastT && u.t0 <= S.t, at = [u.x, u.y + 1.2, u.z];
      for (const f of S.foes) {
        if (f.dead || hiding(f)) continue;
        const p = foeAt(f, S.t), e = [p[0], p[1] + 1.6, p[2]];
        if (u.type === 'flash' && pops && V().visible(e, at)) {           // looking at it: blind
          const d = norm([at[0] - e[0], 0, at[2] - e[2]]), fwd = [Math.sin(p[3]), 0, -Math.cos(p[3])];
          if (dot(d, fwd) > Math.cos(80 * D2R)) { f.blind = S.t + u.blind; f.sees = null; }
        } else if (u.type === 'stun' && pops && Math.hypot(p[0] - u.x, p[2] - u.z) < u.r && Math.abs(p[1] - u.y) < 3) {
          f.daze = S.t + u.daze; f.sees = null;
        } else if (u.type === 'recon' && NM.live(u, S.t) && Math.hypot(p[0] - u.x, p[2] - u.z) < 30 && V().visible([u.x, u.y + 1, u.z], e)) {
          f.rev = S.t + 1.2;
        } else if (u.type === 'trap' && NM.live(u, S.t) && !u.used && Math.hypot(p[0] - u.x, p[2] - u.z) < 2.5 && Math.abs(p[1] - u.y) < 2.5) {
          f.rev = S.t + u.daze + 1; f.daze = S.t + u.daze; f.sees = null; u.used = true; u.t1 = S.t + 1;
        }
      }
    }
  }
  function kitHtml() {                        // your abilities, next to the ammo
    if (!KIT) return '';
    const parts = ['C', 'Q', 'E'].filter(k => KIT[k]).map(s => {
      const a = KIT[s], key = keyName({C: 'ab_c', Q: 'ab_q', E: 'ab_e'}[s]), n = S.kit[s] ?? a.charges;
      const back = a.kind === 'anchor' && S.anchor[s];
      return `<span class="${n > 0 || back ? '' : 'muted'}"><kbd>${esc(key)}</kbd> ${esc(a.name)} ${back ? '↩' : '×' + n}</span>`;
    });
    const t = S.toast && performance.now() / 1000 - S.toastT < 2 ? ` <span class="warn">${esc(S.toast)}</span>` : '';
    return `<div class="dr-kit">${parts.join(' ')}${t}</div>`;
  }

  function nearestOn(R, p) {                // where an enemy looks: the nearest bit of a route (not on top of him)
    let best = R[0], bd = Infinity;
    for (const q of R) { const d = Math.hypot(q[0] - p[0], q[2] - p[2]); if (d < bd && d > 3) { bd = d; best = q; } }
    return best;
  }
  const nearestOnRoute = p => nearestOn(SP.route, p);
  function endRep(mine, label) {
    S.phase = 'between'; S.firing = false;
    const his = MODE === 'death' ? D.his : MODE === 'hold' || MODE === 'postplant' ? react : null;
    if (mine === null) S.msg = `<b class="bad">${esc(label || T('He got you'))}</b>`;
    else if (MODE === 'track') S.msg = `<b class="good">${Math.round(mine)} % ${esc(T('on his head'))}</b>`;
    else if (MODE === 'clear') S.msg = `<b class="good">${Math.round(mine)} % ${esc(T('crosshair placement'))}</b>`;
    else if (MODE === 'retake') S.msg = `<b class="good">${esc(T('Defused'))} · ${Math.max(0, S.spike.left).toFixed(1)} s ${esc(T('left on the spike'))}</b>`;
    else if (his !== null && his !== undefined) S.msg = mine < his ? `<b class="good">${esc(T('Faster than him'))} · ${mine.toFixed(2)} s</b>` : `<b class="bad">${esc(T('Slower than him'))} · ${mine.toFixed(2)} s</b>`;
    else S.msg = `<b class="good">${esc(label || '')} ${mine.toFixed(2)} s</b>`;
    S.until = performance.now() / 1000 + (mine === null ? 1.3 : 1.6);
    hud(true);
  }
  function failRep(label, killer = null) {
    if (S.phase !== 'run') return;
    S.dead = true; S.deaths++;
    S.reps.push(MODE === 'clear' ? placement() : null);
    const onSpike = S.defusing;
    endRep(null, label || (onSpike ? T('Killed on the spike') : null));
    if (killer && opt.replay && AI) startReplay(killer, onSpike);
  }
  // ------------------------------------------------------------------------------------------ the death replay (4.72)
  // The last seconds again from your killer's eyes (a bit slowed down): you as an agent, where he looked, and why
  // you lost it. Your next key skips it.
  function startReplay(f, onSpike) {
    const t1 = S.t, t0 = Math.max(S.t0, t1 - REPLAY_S);
    if (S.trail.length < 2 || t1 - t0 < 0.3) return;
    const at = AI.trailAt(S.trail, t1), prev = AI.trailAt(S.trail, t1 - 0.15) || at;
    const moving = at && prev && at[0] > prev[0] ? Math.hypot(at[1] - prev[1], at[3] - prev[3]) / (at[0] - prev[0]) : 0;
    const why = AI.deathFacts({moving: MOVING ? moving : null, accurate: ACCURATE, defusing: onSpike, youSaw: f.seen,
                               heSaw: f.sees, reloading: S.reload > performance.now() / 1000});
    const mine = MODE === 'death' ? D.agent : AGENT;          // a death drill: the agent you played
    const myAgent = (C.agents || {})[mine] ? mine : (AGENTS.find(a => a !== f.agent) || AGENTS[0] || '');
    S.rp = {f, t0, t1, path: prepPath(AI.trailPath(S.trail)), url: (C.agents || {})[myAgent] || null,
            had: f.sees !== null ? Math.max(0, t1 - f.sees) : null};
    S.phase = 'replay'; S.t = t0;
    S.msg = `<b class="bad">${esc(T('His view'))}</b>` + (S.rp.had !== null ? ` · ${esc(T('he had you for'))} ${S.rp.had.toFixed(2)} s` : '') +
      (why.length ? ` · ${why.map(w => esc(T(w))).join(' · ')}` : '') + ` <span class="muted small">(${esc(keyName('next'))} ${esc(T('skip'))})</span>`;
    hud(true);
  }
  function replayTick(dt) {
    S.t += dt * REPLAY_SPEED;
    if (S.t >= S.rp.t1 + 0.35) endReplay();
  }
  function endReplay() {
    if (S.phase !== 'replay') return;
    S.t = S.rp.t1; S.phase = 'between'; S.until = performance.now() / 1000 + 0.4;
  }
  function replayCam() {                   // from his eyes, onto your chest
    const p = foeAt(S.rp.f, S.t), me = NM.atClamped(S.rp.path, S.t) || [S.me.x, S.me.y, S.me.z];
    const e = [p[0], p[1] + 1.6, p[2]], to = [me[0], me[1] + 1.3, me[2]], v = sub(to, e), L = Math.hypot(...v) || 1;
    V().view({x: e[0], y: e[1] - MAP_EYE, z: e[2], yaw: Math.atan2(v[0], -v[2]), pitch: Math.asin(v[1] / L), fly: true, fov: VFOV});
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
    S.reps = []; S.firsts = {head: 0, body: 0, legs: 0, miss: 0}; S.offs = []; S.saved = false; S.styles = {}; S.histHasMe = false;
    S.shots = []; S.deaths = 0; S.kills = 0; startRep();
  }
  function watch() {
    if (MODE !== 'death' || !S.R) return;
    startRep(); S.phase = 'watch'; S.msg = esc(T('Watching how he did it (slowed down)'));
    panel();
  }

  // ------------------------------------------------------------------------------------------ the clock
  const holds = a => (keys[a] || []).some(k => k && S.held.has(k));
  function move(dt) {                       // your feet: Valorant's speeds, speeding up and stopping
    const m = S.me, has = holds;
    m.crouch = has('crouch');
    if (S.defusing) { m.vx = 0; m.vz = 0; m.still += dt; return; }          // down on the spike
    const max = (m.crouch ? CROUCH : has('walk') ? WALK : RUN) * (S.slowed ? SLOW : 1) * (S.t < S.fast ? S.fastMult : 1);
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
    const ok = (x, z) => !V().blocked(x, z, m.y) && !wallAt(x, z);
    if (ok(nx, nz)) { m.x = nx; m.z = nz; } else if (ok(nx, m.z)) { m.x = nx; m.vz = 0; } else if (ok(m.x, nz)) { m.z = nz; m.vx = 0; } else { m.vx = 0; m.vz = 0; }
    const fl = floor(m.x, m.z, m.y);
    if (fl !== null) m.y = fl;
  }
  function tick(dt) {
    if (S.phase === 'loading' || S.phase === 'error') { camera(); return; }
    const now = performance.now() / 1000;
    if (S.phase === 'count' && now >= S.until) { S.phase = 'run'; panel(); }
    if (S.phase === 'between' && now >= S.until) afterRep();
    if (S.phase === 'replay') replayTick(dt);
    if (S.phase === 'run' || S.phase === 'watch') {
      S.lastT = S.t;
      S.t += dt * (S.phase === 'watch' ? WATCH : (MODE === 'death' ? opt.speed : 1));
      if (MOVING && S.phase === 'run') move(dt);
      if (S.phase === 'run') {                 // 4.72: your last seconds, for the death replay
        const tr = S.trail, last = tr[tr.length - 1];
        if (!last || S.t - last[0] >= 1 / 30) tr.push([S.t, S.me.x, S.me.y, S.me.z, S.yaw, S.me.crouch || S.defusing ? 1 : 0]);
        while (tr.length > 2 && tr[0][0] < S.t - TRAIL_S) tr.shift();
      }
      for (const f of S.foes) {
        if (f.dead) continue;
        if (f.seen === null && seenBy(f)) {
          f.seen = S.t;
          if (S.phase === 'run' && MODE !== 'track') S.offs.push(angleTo(hitboxes(f)[0][1]));
        }
        if (MODE === 'death' || f.harmless || S.phase !== 'run') continue;
        if (seesMe(f)) { if (f.sees === null) f.sees = S.t; } else f.sees = null;
        if (f.sees !== null && S.t - f.sees >= react * (S.t < S.revealed ? REVEAL_REACT : 1)) { failRep(null, f); break; }
      }
      if (MODE === 'death' && S.phase === 'run' && !S.foes[0].dead && S.t >= D.t_kill) {
        if (S.foes[0].sees === null) S.foes[0].sees = D.t_kill - (D.his ?? react);
        failRep(null, S.foes[0]);
      }
      if (MODE === 'death' && S.phase === 'watch' && S.t >= D.t_kill) { S.phase = 'between'; S.msg = ''; S.until = now + 0.8; }
      if (MODE === 'track' && S.phase === 'run') trackTick(dt);
      if (MODE === 'clear' && S.phase === 'run') clearTick();
      if (MODE === 'attack' && S.phase === 'run' && S.t > 60) failRep(T('Out of time'));
      if (MODE === 'entry' && S.phase === 'run') entryTick();
      if (SPIKE && S.phase === 'run') spikeTick(dt);
      if (MODE === 'hold' && S.phase === 'run' && S.t > 40) failRep(T('Out of time'));
      if ((UTIL || KIT) && S.phase === 'run') { utilTick(dt); if (KIT) myTick(); }
      flashes();
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
  function entryTick() {
    const end = SP.route[SP.route.length - 1], onSite = Math.hypot(end[0] - S.me.x, end[2] - S.me.z) < 3;
    for (const f of S.foes) {                 // he heard you coming: he swings (on the site, whoever's still hiding)
      if (f.dead || f.swing === 'done' || (f.swing !== 'wait' && !(onSite && f.seen === null))) continue;
      const p = foeAt(f, S.t);
      if (onSite || Math.hypot(p[0] - S.me.x, p[2] - S.me.z) < 14) swing(f);
    }
    if (S.t > 60) failRep(T('Out of time'));
  }
  function spikeTick(dt) {
    const sp = S.spike;
    sp.left = SP.left - S.t;
    if (MODE === 'retake') {
      const P = SP.plant, on = Math.hypot(S.me.x - P[0], S.me.z - P[2]) < 1.6 && Math.abs(S.me.y - P[1]) < 1.8;
      S.defusing = on && holds('defuse');
      if (S.defusing && !S.heard) heard();          // 4.72: they hear it
      if (S.defusing) {
        sp.prog += dt;
        if (sp.prog >= DEFUSE / 2) sp.half = true;
        if (sp.prog >= DEFUSE) {
          S.defusing = false;
          S.reps.push(Math.round(S.t * 1000) / 1000); S.lefts.push(Math.max(0, sp.left));
          endRep(S.t);
          return;
        }
      } else sp.prog = sp.half ? DEFUSE / 2 : 0;
      if (sp.left <= 0) failRep(T('The spike went off'));
      return;
    }
    for (const f of S.foes) {                 // post-plant: a retaker on the spike long enough
      if (!f.dead && S.t >= f.at + DEFUSE) { failRep(T('They defused the spike')); return; }
    }
    if (sp.left <= 0) {                       // it went off: they didn't make it
      const got = S.foes.filter(f => f.dead).map(f => Math.max(0, f.dead.t - (f.seen ?? f.dead.t)));
      if (got.length) { const v = avg(got); S.reps.push(Math.round(v * 1000) / 1000); endRep(v); }
      else { S.reps.push(null); endRep(null, T('The spike went off before they came')); }
    }
  }
  function flashes() {                      // a flash that popped in your view while you looked
    for (const u of utilList()) {
      if (u.type !== 'flash' || u.t0 <= S.lastT || u.t0 > S.t) continue;
      const p = [u.x, (u.y !== null ? u.y : S.me.y) + 1.2, u.z];
      if (angleTo(p) < 60 && V().visible(eye(), p)) S.flash = 1;
    }
  }
  function camera() {
    if (S.phase === 'replay' && S.rp) { replayCam(); return; }
    V().view({x: S.me.x, y: S.me.y + eyeH() - MAP_EYE, z: S.me.z, yaw: S.yaw, pitch: S.pitch, fly: true, fov: VFOV / zoom()});
  }

  // ------------------------------------------------------------------------------------------ for map3d.js
  // 4.56.1: someone fully behind (or in) a smoke isn't drawn: his head and his chest both behind it
  function smoked(f) {
    const hb = hitboxes(f), hd = hb[0], chest = hb.find(h => h[0] === 'body');
    return !!hd && throughSmoke(eye(), hd[1]) && (!chest || throughSmoke(eye(), chest[2]));
  }
  function models() {
    const out = [];
    const replay = S.phase === 'replay' && S.rp;
    for (const f of S.foes) {
      if (!f.url || hiding(f) || (!replay && smoked(f))) continue;
      const dead = f.dead && !(replay && S.t < f.dead.t);       // the replay: alive until he died
      const p = foeAt(f, dead ? f.dead.t : S.t);
      if (!p) continue;
      if (replay && f === S.rp.f) continue;                     // his eyes are the camera
      const o = {key: f.key, url: f.url, x: p[0], y: p[1], z: p[2], yaw: p[3], col: ENEMY};
      if (dead) {
        o.anim = {lb: [[NM.deathClip(p, eye()), performance.now() / 1000 - f.dead.wall, 1]], ub: null};
      } else if (C.anims) {
        const m = NM.motion(f.path, S.t, p, NM.holdFor(f.weapon));
        o.anim = m.anim; o.y += m.lift; o.gun = (C.guns && C.guns[f.weapon]) || null; o.hold = NM.holdFor(f.weapon);
      }
      out.push(o);
    }
    if (replay && S.rp.url) {                // you, as he saw you
      const p = NM.atClamped(S.rp.path, S.t);
      if (p) {
        const o = {key: 99, url: S.rp.url, x: p[0], y: p[1], z: p[2], yaw: p[3], col: ME_COL};
        if (C.anims) {
          const m = NM.motion(S.rp.path, S.t, p, NM.holdFor(gun.name));
          o.anim = m.anim; o.y += m.lift; o.gun = (C.guns && C.guns[gun.name]) || null; o.hold = NM.holdFor(gun.name);
        }
        out.push(o);
      }
    }
    return out;
  }
  function objects() {
    // 4.56.1: smokes and walls are solid here, as in the game (the replay viewer keeps them see-through): an alpha
    // over 1 leaves only the soft rim see-through
    // 4.70.1: your team's flashes, stuns, recon and traps aren't drawn as balls where they popped (that's often right
    // where you stand); their smokes, walls and mollies are
    const list = utilList().filter(u => !u.team || AREA_UTIL.has(u.type));
    const out = NM.utilObjects(list, S.t, C.util_col).map(o => (o.block ? {...o, a: SOLID_A} : o));
    if (SPIKE && SP && SP.plant) {           // the spike (blinking faster as it runs out)
      const P = SP.plant, y = floor(P[0], P[2], P[1]) ?? P[1], left = S.spike ? S.spike.left : SP.left;
      const on = Math.sin(performance.now() / 1000 * Math.PI * (left < 10 ? 8 : 3)) > -0.2;
      out.push({x: P[0], y: y + 0.18, z: P[2], r: 0.3, sc: [1, 0.6, 1], col: on ? [1, 0.22, 0.28] : [0.45, 0.1, 0.12], a: 0.95, seed: 0, cloudy: false});
    }
    return out;
  }
  // the way to go on the minimap: a dark edge under a bright dashed line (it stands out on any map), an arrow at its
  // end; the bit you've walked past fades
  function routeOnRadar(g, toR, R) {
    if (!R || R.length < 2) return;
    const pts = R.map(p => toR(p[0], p[2]));
    let k = 0, bd = Infinity;
    R.forEach((p, i) => { const d = Math.hypot(p[0] - S.me.x, p[2] - S.me.z); if (d < bd) { bd = d; k = i; } });
    const path = (from, to) => { g.beginPath(); pts.slice(from, to + 1).forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); };
    g.lineCap = 'round'; g.lineJoin = 'round';
    if (k > 0) { path(0, k); g.strokeStyle = 'rgba(255,79,139,.35)'; g.lineWidth = 2; g.setLineDash([4, 6]); g.stroke(); }
    path(k, pts.length - 1); g.setLineDash([]); g.strokeStyle = 'rgba(0,0,0,.75)'; g.lineWidth = 7; g.stroke();
    path(k, pts.length - 1); g.strokeStyle = '#ff4f8b'; g.lineWidth = 4; g.setLineDash([9, 6]); g.stroke(); g.setLineDash([]);
    const [ax, ay] = pts[pts.length - 1], [bx, by] = pts[Math.max(0, pts.length - 3)], a = Math.atan2(ay - by, ax - bx);
    g.fillStyle = '#ff4f8b'; g.strokeStyle = 'rgba(0,0,0,.75)'; g.lineWidth = 2; g.beginPath();
    g.moveTo(ax + Math.cos(a) * 9, ay + Math.sin(a) * 9);
    g.lineTo(ax + Math.cos(a + 2.5) * 9, ay + Math.sin(a + 2.5) * 9); g.lineTo(ax + Math.cos(a - 2.5) * 9, ay + Math.sin(a - 2.5) * 9);
    g.closePath(); g.stroke(); g.fill();
  }
  function radar(g, toR) {                  // the route, the hiding places, the spike on the minimap
    if (!SP) return;
    if (MODE === 'clear' || MODE === 'entry') routeOnRadar(g, toR, SP.route.slice(SP._from || 0));
    if (MODE === 'retake') routeOnRadar(g, toR, myRoute());
    if (SPIKE && SP.plant) {
      const [x, y] = toR(SP.plant[0], SP.plant[2]);
      g.fillStyle = '#ff3b4e'; g.strokeStyle = '#fff'; g.lineWidth = 2;
      g.beginPath(); g.moveTo(x, y - 8); g.lineTo(x + 7, y); g.lineTo(x, y + 8); g.lineTo(x - 7, y); g.closePath(); g.fill(); g.stroke();
    }
    for (const f of S.foes) {                 // revealed by your recon / trap (4.58)
      if (f.dead || !(S.t < (f.rev || 0))) continue;
      const p = foeAt(f, S.t), [x, y] = toR(p[0], p[2]);
      g.fillStyle = '#ff3b4e'; g.strokeStyle = '#fff'; g.lineWidth = 1.5;
      g.beginPath(); g.arc(x, y, 5, 0, Math.PI * 2); g.fill(); g.stroke();
    }
    if (MODE !== 'clear') return;
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
      case 'entry': return `${T('Entry:')} ${fromTo(SP.dz, SP.az)}`;
      case 'retake': return `${T('Retake')} ${SP.dz}`;
      case 'postplant': return `${T('Post-plant')} ${SP.dz}`;
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
    else if (MODE === 'attack' || MODE === 'entry') clock = S.phase === 'run' || S.phase === 'between' ? S.t.toFixed(1) + ' s' : '–';
    else if (SPIKE) clock = S.spike ? Math.max(0, S.spike.left).toFixed(1) + ' s' : (SP.left || 45).toFixed(0) + ' s';
    else if (S.phase === 'run' && seen.length && live.length) clock = (S.t - Math.min(...seen)).toFixed(2) + ' s';
    else if (S.reps.length && S.phase === 'between' && S.reps[S.reps.length - 1] !== null) clock = S.reps[S.reps.length - 1].toFixed(2) + ' s';
    $('dr-clock').textContent = clock;
    const sub2 = MODE === 'death' ? [T('his time'), D.his !== null && D.his !== undefined ? D.his.toFixed(2) + ' s' : '–']
      : MODE === 'hold' ? [T('they shoot after'), react.toFixed(2) + ' s']
      : MODE === 'track' ? [T('time left'), Math.max(0, (S.track ? S.track.secs : 30) - S.t).toFixed(0) + ' s']
      : MODE === 'attack' || MODE === 'entry' ? [T('defenders left'), `${live.length} / ${S.foes.length}`]
      : MODE === 'retake' ? (S.spike && S.spike.prog > 0 ? [T('defusing'), `${S.spike.prog.toFixed(1)} / ${DEFUSE} s`] : [T('attackers left'), `${live.length} / ${S.foes.length}`])
      : MODE === 'postplant' ? (() => {
        const on = live.find(f => S.t >= f.at);
        return on ? [T('defusing!'), `${Math.min(DEFUSE, S.t - on.at).toFixed(1)} / ${DEFUSE} s`] : [T('retakers left'), `${live.length} / ${S.foes.length}`];
      })()
      : [T('spots checked'), `${S.hides.filter(h => h.off !== null).length} / ${S.hides.filter(h => h.open !== -1).length}`];
    $('dr-his-l').textContent = sub2[0]; $('dr-his').textContent = sub2[1];
    const pct = MODE === 'track' || MODE === 'clear';
    $('dr-reps').innerHTML = Array.from({length: Math.min(opt.reps, 40)}, (_, i) => {
      const v = S.reps[i];
      const good = v !== null && v !== undefined && (pct ? v >= 60 : MODE === 'death' ? (D.his === null || D.his === undefined || v < D.his) : MODE === 'hold' || MODE === 'postplant' ? v < react : true);
      const cls = i < S.reps.length ? (v === null ? 'miss' : good ? 'beat' : 'slow') : (i === S.reps.length ? 'now' : '');
      return `<i class="${cls}" title="${esc(T('Rep'))} ${i + 1}"></i>`;
    }).join('');
    $('dr-rep').textContent = `${T('Rep')} ${Math.min(opt.reps, S.reps.length + (S.phase === 'between' ? 0 : 1))} / ${opt.reps}`;
    const rel = S.reload > performance.now() / 1000;
    const state = !(UTIL || KIT) || S.phase === 'done' ? '' : [
      S.hp < HP_ME ? `<span class="${S.hp < 60 ? 'bad' : 'warn'}">♥ ${Math.ceil(S.hp)}</span>` : '',
      S.t < S.revealed ? `<span class="bad">${esc(T('revealed'))}</span>` : '',
      S.slowed ? `<span class="warn">${esc(T('slowed'))}</span>` : ''].filter(Boolean).map(x => x + ' · ').join('');
    $('dr-ammo').innerHTML = kitHtml() + state + (rel ? `<b>${esc(T('Reloading…'))}</b>` : `<b>${S.ammo}</b> / ${gun.mag} · <span translate="no">${esc(gun.name)}</span>`);
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
    clear: 'Walk the route onto the site. Have your crosshair on each hiding place, at head height, the moment it opens. Some have an enemy.',
    entry: 'You are first onto the site. Defenders wait on the places they hid in your replays, and one of them swings you when you get close. Take the site.',
    retake: 'The spike is down. Come back in on the defenders\' way, kill the attackers where they played the spike, and defuse before it goes off (hold your defuse key; half a defuse stays). They hold a crossfire and shift; when they hear the defuse, they peek the spike: tap it to bait them.',
    postplant: 'You play the spike after the plant. The retakers come in on their real routes at their real speed. Kill each before he has you, and before anyone defuses.'};
  function panel(err) {
    const el = $('dr-panel');
    if (err) { el.hidden = false; el.innerHTML = `<p class="bad">${esc(err)}</p><p><a class="btn" href="${esc(C.list)}">${esc(T('Back to the list'))}</a></p>`; return; }
    if (S.phase === 'loading') { el.hidden = false; el.innerHTML = `<p>${esc(T('Loading the drill…'))}</p>`; return; }
    if (S.phase === 'ready' || S.paused) {
      el.hidden = false;
      const moveKeys = MOVING ? ` · ${['forward', 'left', 'back', 'right'].map(keyName).join('')} ${esc(T('move'))} · ${esc(keyName('walk'))} ${esc(T('walk'))} · ${esc(keyName('crouch'))} ${esc(T('crouch'))}` : '';
      el.innerHTML = `<h2>${C.step ? `<span class="muted">${esc(T('Warm-up'))} ${esc(C.step)} · </span>` : ''}${esc(S.paused ? T('Paused') : MODE === 'death' ? T('Your death as a drill') : title())}</h2>` +
        `<p>${esc(T(INTRO[MODE]))}</p>` + utilIntro() +
        (MODE === 'death' ? `<p class="dr-his">${esc(T('His time'))}: <b>${D.his !== null && D.his !== undefined ? D.his.toFixed(2) + ' s' : '–'}</b></p>` : '') +
        `<p class="muted small">${esc(keyName('shoot'))} ${esc(T('shoot'))} · ${esc(keyName('reload'))} ${esc(T('reload'))}${moveKeys}${MODE === 'retake' ? ` · ${esc(keyName('defuse'))} ${esc(T('defuse (hold)'))}` : ''} · ${esc(keyName('restart'))} ${esc(T('again'))}${MODE === 'death' ? ` · ${esc(keyName('watch'))} ${esc(T('watch how he did it'))}` : ''} · Esc ${esc(T('stop'))}</p>` +
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
    if (MODE === 'retake' && S.lefts.length) out.left = median(S.lefts);
    return out;
  }
  function result() {
    const el = $('dr-panel'), vals = S.reps.filter(v => v !== null);
    const pct = MODE === 'track' || MODE === 'clear';
    const his = MODE === 'death' ? D.his ?? null : MODE === 'hold' || MODE === 'postplant' ? react : null;
    const good = v => (pct ? v >= 60 : his === null || v < his);
    const beat = vals.filter(good).length;
    const best = vals.length ? (pct ? Math.max(...vals) : Math.min(...vals)) : null, med = median(vals);
    const fmt = v => (v === null ? '–' : pct ? Math.round(v) + ' %' : v.toFixed(2) + ' s');
    const top = pct ? 100 : Math.max(his || 0, ...vals, 0.3) * 1.15;
    const bars = S.reps.map((v, i) => `<div class="dr-bar"><span>${v === null ? T('miss') : pct ? Math.round(v) + '%' : v.toFixed(2)}</span>` +
      `<i class="${v === null ? 'miss' : good(v) ? 'beat' : 'slow'}" style="height:${v === null ? 100 : Math.max(3, Math.round(v / top * 100))}%"></i><small>${i + 1}</small></div>`).join('');
    const off = avg(S.offs), mo = matchOff();
    const h = C.history || {}, meds = (h.medians || []).concat(med !== null && !S.histHasMe ? [med] : []);
    const head = MODE === 'death' && his !== null ? `${esc(T('You beat him'))} <span class="good">${beat} / ${S.reps.length}</span>`
      : MODE === 'hold' ? `${esc(T('Peeks won'))} <span class="good">${beat} / ${S.reps.length}</span>`
      : MODE === 'attack' ? `${esc(T('Spot taken'))} <span class="good">${vals.length} / ${S.reps.length}</span>`
      : MODE === 'track' ? `${esc(T('On his head'))} <span class="good">${fmt(best)}</span>`
      : MODE === 'clear' ? `${esc(T('Crosshair placement'))} <span class="good">${fmt(med)}</span>`
      : MODE === 'entry' ? `${esc(T('Site taken'))} <span class="good">${vals.length} / ${S.reps.length}</span>`
      : MODE === 'retake' ? `${esc(T('Retakes won'))} <span class="good">${vals.length} / ${S.reps.length}</span>`
      : MODE === 'postplant' ? `${esc(T('Post-plants won'))} <span class="good">${vals.length} / ${S.reps.length}</span>`
      : `${esc(T('Kills'))} <span class="good">${vals.length} / ${S.reps.length}</span>`;
    const facts = [];
    if (MODE !== 'track') facts.push(`<div><b>${esc(T('Your first shots'))}</b><p><span class="hd">${esc(T('head'))} ${S.firsts.head}</span> <span>${esc(T('body'))} ${S.firsts.body}</span> <span>${esc(T('legs'))} ${S.firsts.legs}</span> <span class="bad">${esc(T('missed'))} ${S.firsts.miss}</span></p></div>`);
    if (['death', 'hold', 'attack', 'entry', 'retake', 'postplant'].includes(MODE))
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
    if (MODE === 'retake') facts.push(`<div><b>${esc(T('Left on the spike'))}</b><p>${S.lefts.length ? S.lefts.map(v => v.toFixed(1) + ' s').join(' · ') : '–'} · ${esc(T('kills'))} ${S.kills} · ${esc(T('deaths'))} ${S.deaths}</p></div>`);
    if (MODE === 'entry') facts.push(`<div><b>${esc(T('Kills and deaths'))}</b><p>${esc(T('kills'))} ${S.kills} · ${esc(T('deaths'))} ${S.deaths}</p></div>`);
    if (MODE === 'clear') facts.push(`<div><b>${esc(T('Hiding places'))}</b><p>${S.hides.map(h2 => `<span class="${h2.off === null ? '' : h2.off <= 7 ? 'good' : 'bad'}">${h2.off === null ? '–' : Math.round(h2.off) + '°'}</span>`).join(' ')} · ${esc(T('kills'))} ${S.kills} · ${esc(T('deaths'))} ${S.deaths}</p></div>`);
    facts.push(`<div${C.chart ? ' class="dr-wide"' : ''}><b>${esc(T('Since the first time'))}</b><p>${meds.length > 1 ? `${esc(T('Median per session'))}: ${meds.slice(-5).map(fmt).join(' → ')}` : esc(T('Your first session on this spot.'))}</p>${C.chart || ''}</div>`);   // 4.73: the chart from the server
    el.hidden = false;
    el.innerHTML = `<div class="dr-res">
      <p class="muted small" translate="no">${esc(D.map)} · ${esc(MODE === 'death' ? `${D.where} · ${D.killer_agent} · ${D.weapon}` : title())}</p>
      <h2>${head}</h2>
      <div class="dr-nums"><div><b class="good">${fmt(best)}</b><small>${esc(T('your best'))}</small></div>
        <div><b>${fmt(med)}</b><small>${esc(T('your median'))}</small></div>
        ${his !== null && !pct ? `<div><b class="bad">${his.toFixed(2)} s</b><small>${esc(T(MODE === 'death' ? 'his time' : 'their reaction'))}</small></div>` : ''}</div>
      ${S.reps.length > 1 ? `<div class="dr-bars">${his !== null && !pct ? `<div class="dr-his-line" style="bottom:${Math.round(his / top * 100)}%"><span>${esc(T(MODE === 'death' ? 'his' : 'theirs'))} ${his.toFixed(2)} s</span></div>` : ''}${bars}</div>` : ''}
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
        body: JSON.stringify({kind: MODE, reps: S.reps, his: MODE === 'death' ? D.his ?? null : MODE === 'hold' || MODE === 'postplant' ? react : null,
                              first: S.firsts, off: avg(S.offs), detail: details(),
                              // 4.65: what the weekly view calls it
                              map: C.map || D.map || '', where: MODE === 'death' ? [D.where, D.killer_agent].filter(Boolean).join(' vs ') : (C.title || '')})});
      const d = await r.json();
      if (r.ok && d.history) { C.history = d.history; S.histHasMe = true; }
      if (r.ok && d.chart !== undefined) { C.chart = d.chart; if (S.phase === 'done') result(); }   // 4.73: with this session
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
    if (['run', 'count', 'watch', 'between', 'replay'].includes(S.phase)) {
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
      else if (SLOT_OF[a]) cast(SLOT_OF[a]);
      else if (a === 'restart') { if (document.pointerLockElement !== canvas) lock(); S.paused = false; restart(); }
      else if (a === 'next') { if (S.phase === 'replay') endReplay(); if (S.phase === 'between' && !S.paused) S.until = 0; }
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
    if ($('dr-o-replay')) $('dr-o-replay').checked = !!opt.replay;
    $('dr-o-speed').closest('label').hidden = MODE !== 'death';
    $('dr-o-reps').closest('label').hidden = MODE !== 'death';
    KB.editor($('dr-keys'), {keys, defaults: C.defaults || keys, actions: C.actions, api: C.keys_api, onSave: k => { keys = k; panel(); }});
  }
  $('dr-opts').addEventListener('change', () => {
    opt.heads = $('dr-o-heads').checked;
    if ($('dr-o-replay')) opt.replay = $('dr-o-replay').checked;
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
      : MODE === 'attack' ? `${Math.min(3, SP.defs.length)} ${T('defenders')}`
      : MODE === 'entry' ? `${Math.min(NFOES, SP.hides.length)} ${T('defenders')}`
      : MODE === 'retake' ? `${Math.min(NFOES, SP.posts.length)} ${T('attackers')}`
      : MODE === 'postplant' ? `${NFOES} ${T('retakers')}` : `${SP.hides.length} ${T('hiding places')}`;
    const diff = (O.diff || 'medium').replace(/^./, c => c.toUpperCase());
    $('dr-info').innerHTML = `<b translate="no">${esc(D.map)} · ${esc(title())}</b><small>${esc(T(diff))} · <span translate="no">${esc(gun.name)}</span> · ${esc(what)}</small>`;
  }
  if (C.anims && V().anims) V().anims(C.anims);
  V().setLayer({tick, models, objects, radar, ready: () => camera()});
  V().setOpt('labels', false); V().setOpt('radar', true);    // like the game: the minimap in the corner (not saved)
  panel();
  load();
  window.nexusDrill = {state: () => ({phase: S.phase, t: S.t, teamUtil: S.teamUtil, reps: S.reps.slice(), seen: S.foes.length ? S.foes[0].seen : null,
                                      kill: S.foes.some(f => f.dead), ammo: S.ammo, yaw: S.yaw, pitch: S.pitch,
                                      hp: S.foes.length ? S.foes[0].hp : null, firsts: {...S.firsts}, paused: S.paused,
                                      foes: S.foes.length, me: {...S.me}, speed: speed(), mode: MODE, dead: S.dead,
                                      hides: S.hides.map(h => ({open: h.open, off: h.off})),
                                      spike: S.spike ? {...S.spike} : null, defusing: S.defusing,
                                      myhp: S.hp, revealed: S.t < S.revealed, slowed: S.slowed, util: S.U.length}),
                       utilNow: () => S.U.map(u => ({type: u.type, agent: u.agent, t0: u.t0, t1: u.t1, x: u.x, z: u.z, arm: u.arm, live: NM.live(u, S.t), team: !!u.team})),
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
                       foeInfo: (i = 0) => (S.foes[i] ? {at: S.foes[i].at, swing: S.foes[i].swing || null, seen: S.foes[i].seen,
                                                          hp: S.foes[i].hp, blind: S.foes[i].blind || 0, daze: S.foes[i].daze || 0, rev: S.foes[i].rev || 0} : null),
                       kit: () => ({...S.kit}),
                       replay: () => (S.rp ? {t0: S.rp.t0, t1: S.rp.t1, had: S.rp.had, killer: S.foes.indexOf(S.rp.f), on: S.phase === 'replay'} : null),
                       heard: () => S.heard, plan: () => S.foes.map(f => ({cross: !!f.cross, shifts: !!f.shifts})),
                       foeDead: i => !!(S.foes[i] && S.foes[i].dead)};
})();
