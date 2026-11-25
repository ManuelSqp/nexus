// 4.72: how the enemies in the drills think, and the death replay (drill.js uses these; no page, no map in here:
// line of sight and randomness come in as functions, so tests can run it in node).
//
// Retakes: attackers play the spike like in the game. They stand on the places attackers played the spike from in
// your replays (stats/drills.py "posts"), preferring ones that can see the spike; two of them in a crossfire (the
// widest angle on the spike there is); one of them shifts to another place after a few seconds (they don't stand
// still the whole time); and a defuse is heard: whoever can't see you peeks the spike (drill.js swing()), so a
// tapped defuse baits them out.
(function (root) {
  'use strict';
  const EYE = 1.75, SPIKE_Y = 0.3;
  const CROSS_MIN = 40;                  // degrees between two attackers on the spike to count as a crossfire
  const SHIFT_NEAR = 3, SHIFT_FAR = 15;  // metres: how far a shift goes
  const SHIFT_AT = [3, 8];               // seconds into the retake

  const eyeOf = p => [p[0], p[1] + EYE, p[2]];
  const flat = (a, b) => Math.hypot(a[0] - b[0], a[2] - b[2]);
  function angleOn(plant, a, b) {        // the angle at the spike between two places (degrees)
    const u = [a[0] - plant[0], a[2] - plant[2]], v = [b[0] - plant[0], b[2] - plant[2]];
    const L = (Math.hypot(...u) * Math.hypot(...v)) || 1;
    return Math.acos(Math.max(-1, Math.min(1, (u[0] * v[0] + u[1] * v[1]) / L))) * 180 / Math.PI;
  }

  // posts: [[x, y, z], …] most used first; n attackers; vis(a, b): line of sight; rnd(): 0..1
  // -> [{post, i, cross, shift: [x, y, z] | null, at}] (i: index in posts)
  function retakePlan(posts, plant, n, vis, rnd = Math.random) {
    if (!posts.length || n < 1) return [];
    const spike = [plant[0], plant[1] + SPIKE_Y, plant[2]];
    const watching = posts.map((p, i) => i).filter(i => vis(eyeOf(posts[i]), spike));
    const pool = watching.length >= Math.min(n, 2) ? watching : posts.map((p, i) => i);
    const first = pool[Math.floor(rnd() * Math.min(pool.length, 3))];
    const picked = [first];
    let cross = false;
    if (n >= 2) {                        // the crossfire: the widest angle on the spike from the first
      let best = null, bestA = -1;
      for (const i of pool) {
        if (i === first) continue;
        const a = angleOn(plant, posts[first], posts[i]);
        if (a > bestA) { bestA = a; best = i; }
      }
      if (best === null) best = posts.map((p, i) => i).find(i => i !== first);
      if (best !== undefined && best !== null) { picked.push(best); cross = bestA >= CROSS_MIN; }
    }
    const rest = posts.map((p, i) => i).filter(i => !picked.includes(i));
    while (picked.length < Math.min(n, posts.length) && rest.length) picked.push(rest.splice(Math.floor(rnd() * rest.length), 1)[0]);
    const out = picked.map((i, k) => ({post: posts[i], i, cross: cross && k < 2, shift: null, at: null}));
    // one shifts (never the first: he keeps his angle): to another place near his own, one that sees the spike
    // if there is one
    if (out.length >= 2) {
      const who = out[1 + Math.floor(rnd() * (out.length - 1))];
      const free = posts.map((p, i) => i).filter(i => !picked.includes(i) && flat(posts[i], who.post) >= SHIFT_NEAR && flat(posts[i], who.post) <= SHIFT_FAR);
      const good = free.filter(i => watching.includes(i));
      const to = (good.length ? good : free)[0];
      if (to !== undefined) { who.shift = posts[to]; who.at = SHIFT_AT[0] + rnd() * (SHIFT_AT[1] - SHIFT_AT[0]); }
    }
    return out;
  }

  // the death replay: what you did in your last seconds ([t, x, y, z, yaw, crouch] every tick) as a path the agent
  // models can play ([t, x, y, z, yaw, 0, floor], crouched a bit lower)
  function trailPath(trail, crouchDy = 0.45) {
    return trail.map(r => [r[0], r[1], r[2] - (r[5] ? crouchDy : 0), r[3], r[4], 0, r[2]]);
  }
  function trailAt(trail, t) {           // where you were at t (the last sample at or before it)
    let best = trail[0] || null;
    for (const r of trail) { if (r[0] <= t) best = r; else break; }
    return best;
  }
  // why you lost the duel, in a few words: {moving (m/s when he shot), accurate (m/s you can shoot at), defusing,
  // youSaw (when you first could see him, or null), heSaw (since when he had you), end (when he shot), reloading}
  function deathFacts(d) {
    const out = [];
    if (d.defusing) out.push('you were on the spike');
    if (d.reloading) out.push('you were reloading');
    if (d.moving !== null && d.moving !== undefined && d.moving > d.accurate) out.push('you were moving');
    if (d.youSaw === null || d.youSaw === undefined) out.push('you never saw him');
    else if (d.heSaw !== null && d.heSaw !== undefined && d.heSaw < d.youSaw - 0.05) out.push('he saw you first');
    return out;
  }
  // ---- 4.77: crosshair placement. Where your crosshair was the moment a head came into view, before you could move
  // the mouse: the angle off it in all (off), how far above (+) or below (-) it (up), and to the side (side), in
  // degrees. eye: [x, y, z]; yaw, pitch: radians (the drill's own: yaw 0 looks along -z); head: [x, y, z].
  const D2R = Math.PI / 180;
  function placeError(eye, yaw, pitch, head) {
    const v = [head[0] - eye[0], head[1] - eye[1], head[2] - eye[2]], L = Math.hypot(...v) || 1e-9;
    const d = [Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch)];
    const off = Math.acos(Math.max(-1, Math.min(1, (d[0] * v[0] + d[1] * v[1] + d[2] * v[2]) / L))) / D2R;
    const hp = Math.asin(Math.max(-1, Math.min(1, v[1] / L))), hy = Math.atan2(v[0], -v[2]);
    let dy = yaw - hy;
    while (dy > Math.PI) dy -= 2 * Math.PI;
    while (dy < -Math.PI) dy += 2 * Math.PI;
    return {off, up: (pitch - hp) / D2R, side: Math.abs(dy) / D2R * Math.cos(hp)};
  }
  const ON_IT = 2;                       // degrees: "on it"
  // a rep's (or a session's) errors -> {n, median, up (the average above/below), on (within ON_IT), worst}
  function placeSummary(errs) {
    const xs = errs.filter(e => e && Number.isFinite(e.off));
    if (!xs.length) return {n: 0, median: null, up: null, on: 0, worst: null};
    const o = xs.map(e => e.off).sort((a, b) => a - b), m = o.length >> 1;
    return {n: xs.length, median: o.length % 2 ? o[m] : (o[m - 1] + o[m]) / 2,
            up: xs.reduce((a, e) => a + e.up, 0) / xs.length, on: xs.filter(e => e.off <= ON_IT).length, worst: o[o.length - 1]};
  }
  // a point along a route ([[x, y, z], …]) d metres from its start -> [x, y, z, yaw of the leg, at the end?]
  function routeAt(R, d) {
    let left = Math.max(0, d);
    for (let i = 1; i < R.length; i++) {
      const a = R[i - 1], b = R[i], L = Math.hypot(b[0] - a[0], b[2] - a[2]);
      if (L <= 1e-6) continue;
      const yaw = Math.atan2(b[0] - a[0], -(b[2] - a[2]));
      if (left <= L) { const k = left / L; return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k, yaw, false]; }
      left -= L;
    }
    const e = R[R.length - 1], f = R[Math.max(0, R.length - 2)];
    return [e[0], e[1], e[2], Math.atan2(e[0] - f[0], -(e[2] - f[2])), true];
  }
  const api = {retakePlan, trailPath, trailAt, deathFacts, angleOn, CROSS_MIN, SHIFT_AT, placeError, placeSummary, routeAt, ON_IT};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.NexusDrillAI = api;
})(typeof window !== 'undefined' ? window : globalThis);
