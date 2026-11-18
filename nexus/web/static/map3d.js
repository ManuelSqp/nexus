// Practice › 3D maps: walk around a map rebuilt from replay files (stats/map3d.py). Plain WebGL, no libraries.
// The map is a grid of half-metre cells with one or more floor heights each; floors are drawn per cell, walls where a
// neighbour is missing or much higher. Frame: metres, x right and z down on the minimap, y up; yaw 0 looks "up" the
// minimap. Keys: WASD move, Shift walk, Ctrl crouch, Space jump, F fly, C callouts, R radar, H help, Esc stop.
(function () {
  'use strict';
  const C = window.NEXUS_MAP3D;
  if (!C) return;
  const $ = id => document.getElementById(id);
  const T = s => (window.vcT ? window.vcT(s) : s);
  const canvas = $('m3-canvas'), over = $('m3-over'), radar = $('m3-radar'), stage = $('m3-stage');
  const D2R = Math.PI / 180, EYE = 1.6, EYE_CROUCH = 1.15, STEP = 0.6, WALL_H = 3.6, R = 0.3;
  const SPEED = {run: 6.75, walk: 3.6, crouch: 2.4}, GRAV = 20, JUMP = 5.5;
  let gl = null, prog = null, loc = {}, mesh = null, M = null, grid = null, raf = 0, last = 0;
  let layer = null;                  // 4.44: something drawn on top (the replay viewer, replay.js)
  let G = null;                      // 4.48: the map built from the game's files: buffers, roof map, see-through grid
  const keys = new Set();
  const me = {x: 0, y: 0, z: 0, vy: 0, yaw: 0, pitch: 0, ground: true, fly: false, crouch: false};
  const opt = {labels: false, radar: true, help: true, colors: 'one', roofs: false, xray: false};   // colors (4.46): one | known | areas | height (4.48)
  try { Object.assign(opt, JSON.parse(localStorage.getItem('nexus.map3d') || '{}')); } catch (e) {}
  const saveOpt = () => { try { localStorage.setItem('nexus.map3d', JSON.stringify(opt)); } catch (e) {} };

  // ---------------------------------------------------------------- the grid
  function buildGrid(d) {
    const g = new Map();
    for (const [i, j, h, k, e] of d.cells) {
      const key = i + ',' + j;
      if (!g.has(key)) g.set(key, []);
      g.get(key).push({h, k, e: !!e});
    }
    for (const v of g.values()) v.sort((a, b) => a.h - b.h);
    return g;
  }
  const cellOf = (x, z) => [Math.floor(x / M.cell), Math.floor(z / M.cell)];
  const levels = (i, j) => grid.get(i + ',' + j) || null;
  // the floor you stand on at (x, z) from feet height y: the highest level not more than a step above you
  function floorAt(x, z, y) {
    const lv = levels(...cellOf(x, z));
    if (!lv) return null;
    let best = null;
    for (const l of lv) if (l.h <= y + STEP && (best === null || l.h > best)) best = l.h;
    return best;
  }
  // can't go there: no floor within a step at the centre, or at the edge of your body within a bit more (on a ramp
  // the cells beside you are already higher; a wall or a box has no floor near your height at all)
  function blocked(x, z, y) {
    if (floorAt(x, z, y) === null) return true;
    for (const [dx, dz] of [[R, 0], [-R, 0], [0, R], [0, -R]]) if (floorAt(x + dx, z + dz, y + 0.45) === null) return true;
    return false;
  }

  // ---------------------------------------------------------------- meshes
  const VS = `attribute vec3 p; attribute vec3 n; attribute vec3 c; uniform mat4 vp; uniform vec3 eye;
    varying vec3 vc; varying vec3 vn; varying vec3 wp; varying float fog;
    void main(){ gl_Position = vp * vec4(p, 1.0); vc = c; vn = n; wp = p; fog = clamp(length(p - eye) / 140.0, 0.0, 1.0); }`;
  const FS = `precision mediump float; varying vec3 vc; varying vec3 vn; varying vec3 wp; varying float fog;
    void main(){
      vec3 L = normalize(vec3(0.35, 0.9, 0.25));
      float d = 0.55 + 0.45 * max(dot(normalize(vn), L), 0.0);
      vec2 g = abs(fract((abs(vn.y) > 0.5 ? wp.xz : (abs(vn.x) > 0.5 ? wp.zy : wp.xy)) / 2.0) - 0.5);
      float line = 1.0 - 0.07 * step(0.47, max(g.x, g.y));
      vec3 col = vc * d * line;
      gl_FragColor = vec4(mix(col, vec3(0.55, 0.62, 0.72), fog * 0.6), 1.0);
    }`;
  function initGL() {
    if (gl) return true;
    gl = canvas.getContext('webgl', {antialias: true});
    if (!gl) return false;
    const sh = (t, src) => { const s = gl.createShader(t); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    prog = gl.createProgram(); gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog);
    gl.useProgram(prog);
    loc = {p: gl.getAttribLocation(prog, 'p'), n: gl.getAttribLocation(prog, 'n'), c: gl.getAttribLocation(prog, 'c'),
           vp: gl.getUniformLocation(prog, 'vp'), eye: gl.getUniformLocation(prog, 'eye')};
    gl.enable(gl.DEPTH_TEST);
    return true;
  }
  const ONE = [0.74, 0.71, 0.66], KNOWN = [0.80, 0.69, 0.50], GUESSED = [0.56, 0.63, 0.74];
  const KINDS = [[0.74, 0.72, 0.68], [0.84, 0.66, 0.46], [0.66, 0.74, 0.62], [0.82, 0.60, 0.54], [0.60, 0.66, 0.80]];
  function baseColor(l) {                          // 4.46: one colour, measured vs. guessed, or the map's areas
    if (opt.colors === 'areas') return M.game ? KINDS[l.k] || KINDS[0] : (M.palette[l.k] || M.palette[0]);
    if (opt.colors === 'known') return l.e ? GUESSED : KNOWN;
    return ONE;
  }
  function shade(l, i, j) {                        // a little different per cell
    const base = baseColor(l);
    const n = (((i * 73856093) ^ (j * 19349663)) >>> 0) % 1000 / 1000;
    const f = 0.92 + 0.12 * n;
    return [base[0] * f, base[1] * f, base[2] * f];
  }
  function buildMesh() {
    const v = [];
    const quad = (a, b, c2, d, n, col) => { for (const q of [a, b, c2, a, c2, d]) v.push(q[0], q[1], q[2], n[0], n[1], n[2], col[0], col[1], col[2]); };
    const s = M.cell;
    for (const [key, lv] of grid) {
      const [i, j] = key.split(',').map(Number), x0 = i * s, z0 = j * s, x1 = x0 + s, z1 = z0 + s;
      for (const l of lv) {
        const col = shade(l, i, j);
        quad([x0, l.h, z0], [x0, l.h, z1], [x1, l.h, z1], [x1, l.h, z0], [0, 1, 0], col);
        // walls on the four sides: up to the next floor, or a full wall where there's nothing to stand on
        for (const [di, dj, a, b, n] of [[1, 0, [x1, z0], [x1, z1], [1, 0, 0]], [-1, 0, [x0, z1], [x0, z0], [-1, 0, 0]],
                                          [0, 1, [x1, z1], [x0, z1], [0, 0, 1]], [0, -1, [x0, z0], [x1, z0], [0, 0, -1]]]) {
          const nb = levels(i + di, j + dj);
          let top = null;
          if (!nb) top = l.h + WALL_H;
          else if (nb.some(o => Math.abs(o.h - l.h) <= STEP)) continue;
          else {
            const up = nb.filter(o => o.h > l.h + STEP && o.h <= l.h + WALL_H);
            const down = nb.some(o => o.h < l.h - STEP && o.h >= l.h - WALL_H);
            if (up.length) top = Math.min(...up.map(o => o.h));
            else if (down) continue;                  // the lower cell draws this face
            else top = l.h + WALL_H;
          }
          const wc = col.map(c => c * 0.82);
          quad([a[0], l.h, a[1]], [a[0], top, a[1]], [b[0], top, b[1]], [b[0], l.h, b[1]], [-n[0], 0, -n[2]], wc);
        }
      }
    }
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(v), gl.STATIC_DRAW);
    return {buf, n: v.length / 9};
  }
  function persp(fy, asp, n, f) { const t = 1 / Math.tan(fy / 2); return [t / asp, 0, 0, 0, 0, t, 0, 0, 0, 0, (f + n) / (n - f), -1, 0, 0, 2 * f * n / (n - f), 0]; }
  function mul(a, b) { const o = new Array(16).fill(0); for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) for (let k = 0; k < 4; k++) o[j * 4 + i] += a[k * 4 + i] * b[j * 4 + k]; return o; }
  function viewM() {
    const e = eyePos(), cy = Math.cos(me.yaw), sy = Math.sin(me.yaw), cp = Math.cos(me.pitch), sp = Math.sin(me.pitch);
    const f = [sy * cp, sp, -cy * cp], r = [cy, 0, sy], u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]];
    return [r[0], u[0], -f[0], 0, r[1], u[1], -f[1], 0, r[2], u[2], -f[2], 0,
            -(r[0] * e[0] + r[1] * e[1] + r[2] * e[2]), -(u[0] * e[0] + u[1] * e[1] + u[2] * e[2]), f[0] * e[0] + f[1] * e[1] + f[2] * e[2], 1];
  }
  const eyePos = () => [me.x, me.y + (me.fly ? EYE : me.crouch ? EYE_CROUCH : EYE), me.z];
  let VP = null;
  function project(x, y, z) {        // world -> screen pixels (and the distance), or null behind the camera
    if (!VP) return null;
    const q = [0, 0, 0, 0];
    for (let i = 0; i < 4; i++) q[i] = VP[i] * x + VP[4 + i] * y + VP[8 + i] * z + VP[12 + i];
    if (q[3] <= 0.1) return null;
    return {x: (q[0] / q[3] * 0.5 + 0.5) * canvas.width, y: (1 - (q[1] / q[3] * 0.5 + 0.5)) * canvas.height, d: q[3],
            px: canvas.height / 2 / Math.tan(71 * D2R / 2) / q[3]};   // pixels per metre at that distance
  }
  function draw() {
    const dpr = window.devicePixelRatio || 1, w = Math.round(canvas.clientWidth * dpr), h = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; over.width = w; over.height = h; }
    gl.viewport(0, 0, w, h);
    gl.clearColor(0.55, 0.62, 0.72, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (!mesh) return;
    VP = mul(persp((me.fov || 71) * D2R, w / h, 0.05, 600), viewM());   // 4.51: me.fov (the drills zoom when aiming down sights)
    if (G && G.ready) drawGame();
    else {
      gl.useProgram(prog);
      gl.uniformMatrix4fv(loc.vp, false, VP); gl.uniform3fv(loc.eye, eyePos());
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.buf);
      gl.enableVertexAttribArray(loc.p); gl.vertexAttribPointer(loc.p, 3, gl.FLOAT, false, 36, 0);
      gl.enableVertexAttribArray(loc.n); gl.vertexAttribPointer(loc.n, 3, gl.FLOAT, false, 36, 12);
      gl.enableVertexAttribArray(loc.c); gl.vertexAttribPointer(loc.c, 3, gl.FLOAT, false, 36, 24);
      gl.drawArrays(gl.TRIANGLES, 0, mesh.n);
      gl.disableVertexAttribArray(loc.p); gl.disableVertexAttribArray(loc.n); gl.disableVertexAttribArray(loc.c);
    }
    if (layer && layer.models) drawModels(layer.models());
    if (G && G.ready && G.glass) drawGlass();
    if (layer && layer.objects) drawObjects(layer.objects());
    overlay(w, h, dpr);
  }
  // ---------------------------------------------------------------- 4.48: the map from the game's files
  // One binary file (stats/mapmesh.py pack()): vertices as 16-bit numbers between lo and hi, a zone number per vertex
  // (for "Map areas"), triangles (32-bit), glass, the roof map (per square metre the highest floor; whatever is
  // more than ROOF above it is cut away so the view from above shows the floors) and a coarse see-through grid
  // (half a metre) for hiding names behind walls. Light comes from the screen-space slope (flat faces, no normals).
  const ROOF = 3.4;
  const GVS = `attribute vec3 q; attribute float a; uniform vec3 lo; uniform vec3 span; uniform mat4 vp; uniform vec3 eye;
    varying vec3 wp; varying float va; varying float fog;
    void main(){ wp = lo + q * span; va = a; gl_Position = vp * vec4(wp, 1.0); fog = clamp(length(wp - eye) / 220.0, 0.0, 1.0); }`;
  const GFS = `#ifdef GL_OES_standard_derivatives
    #extension GL_OES_standard_derivatives : enable
    #endif
    #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
    #else
    precision mediump float;
    #endif
    uniform sampler2D roof; uniform vec4 rg; uniform float rmin; uniform float cut; uniform float rcut; uniform float ey;
    uniform sampler2D pal; uniform float paln; uniform float mode; uniform vec3 one; uniform vec2 hr; uniform float alpha;
    varying vec3 wp; varying float va; varying float fog;
    void main(){
      vec3 n = vec3(0.0, 1.0, 0.0);
      #ifdef GL_OES_standard_derivatives
      n = normalize(cross(dFdx(wp), dFdy(wp)));
      #endif
      if (cut > 0.5) {
        vec4 t = texture2D(roof, (wp.xz - rg.xy) / rg.zw);
        float h = floor(t.r * 65280.0 + t.a * 255.0 + 0.5) / 100.0 + rmin;
        if (wp.y > h + rcut) discard;
      }
      if (va > 254.5 && ey < wp.y) discard;                  // a lid is only seen from above
      if (va > 254.5) { gl_FragColor = vec4(mix(vec3(0.19, 0.22, 0.29), vec3(0.55, 0.62, 0.72), fog * 0.5), 1.0); return; }
      vec3 L = normalize(vec3(0.35, 0.9, 0.25));
      float d = 0.52 + 0.48 * abs(dot(n, L));
      vec3 base = one;
      if (mode > 1.5 && va > 0.5) base = texture2D(pal, vec2((va - 0.5) / paln, 0.5)).rgb;
      else if (mode > 0.5 && mode < 1.5) { float k = clamp((wp.y - hr.x) / max(0.1, hr.y - hr.x), 0.0, 1.0);
        base = mix(vec3(0.42, 0.55, 0.72), vec3(0.93, 0.80, 0.55), k); }
      if (abs(n.y) < 0.45) base *= 0.86;
      vec2 g = abs(fract((abs(n.y) > 0.5 ? wp.xz : (abs(n.x) > 0.5 ? wp.zy : wp.xy)) / 2.0) - 0.5);
      float line = 1.0 - 0.06 * step(0.47, max(g.x, g.y)) * (1.0 - smoothstep(0.08, 0.3, fog));
      vec3 col = base * d * line;
      gl_FragColor = vec4(mix(col, vec3(0.55, 0.62, 0.72), fog * 0.55), alpha);
    }`;
  let gprog = null, gloc = {};
  function initGame() {
    if (gprog !== null) return !!gprog;
    gl.getExtension('OES_standard_derivatives');
    if (!gl.getExtension('OES_element_index_uint')) { gprog = false; return false; }
    const sh = (t, src) => { const x = gl.createShader(t); gl.shaderSource(x, src); gl.compileShader(x);
      if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) console.error('map shader:', gl.getShaderInfoLog(x)); return x; };
    gprog = gl.createProgram(); gl.attachShader(gprog, sh(gl.VERTEX_SHADER, GVS)); gl.attachShader(gprog, sh(gl.FRAGMENT_SHADER, GFS)); gl.linkProgram(gprog);
    if (!gl.getProgramParameter(gprog, gl.LINK_STATUS)) { console.error('map shader:', gl.getProgramInfoLog(gprog)); gprog = false; return false; }
    for (const u of ['lo', 'span', 'vp', 'eye', 'ey', 'roof', 'rg', 'rmin', 'cut', 'rcut', 'pal', 'paln', 'mode', 'one', 'hr', 'alpha']) gloc[u] = gl.getUniformLocation(gprog, u);
    gloc.q = gl.getAttribLocation(gprog, 'q'); gloc.a = gl.getAttribLocation(gprog, 'a');
    return true;
  }
  function parseGame(buf) {
    const dv = new DataView(buf);
    if (String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3)) !== 'NXM1') throw new Error('not a map file');
    const n = dv.getUint32(4, true), head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 8, n))), base = 8 + n;
    const sec = (k, T, size) => { const [o, l] = head.sections[k]; return new T(buf, base + o, l / size); };
    return {head, pos: sec('pos', Uint16Array, 2), area: sec('area', Uint8Array, 1), idx: sec('idx', Uint32Array, 4),
            gpos: sec('gpos', Uint16Array, 2), gidx: sec('gidx', Uint32Array, 4), roof: sec('roof', Uint16Array, 2), vox: sec('vox', Uint8Array, 1)};
  }
  async function loadGame(d) {
    const tok = d;
    G = {loading: true, ready: false};
    $('m3-msg').textContent = T('Loading the map…'); $('m3-msg').hidden = false;
    try {
      const r = await fetch(d.mesh, {credentials: 'same-origin'});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const buf = await r.arrayBuffer();
      if (M !== tok) return;                          // another map was chosen meanwhile
      const p = parseGame(buf);
      if (!initGame()) throw new Error(T('This browser can\'t draw the full map.'));
      const g = {ready: true, head: p.head, lo: p.head.lo, span: p.head.hi.map((h, i) => h - p.head.lo[i])};
      const buffer = (target, data) => { const b = gl.createBuffer(); gl.bindBuffer(target, b); gl.bufferData(target, data, gl.STATIC_DRAW); return b; };
      g.pos = buffer(gl.ARRAY_BUFFER, p.pos); g.area = buffer(gl.ARRAY_BUFFER, p.area);
      g.idx = buffer(gl.ELEMENT_ARRAY_BUFFER, p.idx); g.n = p.idx.length;
      if (p.gidx.length) {
        g.glass = {pos: buffer(gl.ARRAY_BUFFER, p.gpos), area: buffer(gl.ARRAY_BUFFER, new Uint8Array(p.gpos.length / 3)),
                   idx: buffer(gl.ELEMENT_ARRAY_BUFFER, p.gidx), n: p.gidx.length};
      }
      // roof map: 16 bits per cell as luminance (high byte) + alpha (low byte)
      const R = p.head.roof, rb = new Uint8Array(R.w * R.h * 2);
      for (let i = 0; i < R.w * R.h; i++) { rb[2 * i] = p.roof[i] >> 8; rb[2 * i + 1] = p.roof[i] & 255; }
      g.roofT = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, g.roofT);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.LUMINANCE_ALPHA, R.w, R.h, 0, gl.LUMINANCE_ALPHA, gl.UNSIGNED_BYTE, rb);
      for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.NEAREST], [gl.TEXTURE_MAG_FILTER, gl.NEAREST], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
      g.roof = {R, v: p.roof};
      // lids: where a building was cut away, a dark square at the cut (zone 255 = the lid colour in the shader)
      const lp = [], li = [];
      for (let i = 0; i < R.h; i++) for (let j = 0; j < R.w; j++) {
        const v = p.roof[i * R.w + j];
        if (!(v & 2)) continue;
        const y = (v & ~3) / 100 + R.ymin + ROOF - 0.02, x0 = R.x0 + j * R.cell, z0 = R.z0 + i * R.cell, k = lp.length / 3;
        lp.push(x0, y, z0, x0 + R.cell, y, z0, x0 + R.cell, y, z0 + R.cell, x0, y, z0 + R.cell);
        li.push(k, k + 1, k + 2, k, k + 2, k + 3);
      }
      if (li.length) {
        const llo = [0, 1, 2].map(a => { let m = Infinity; for (let k = a; k < lp.length; k += 3) m = Math.min(m, lp[k]); return m - 0.01; });
        const lsp = [0, 1, 2].map(a => { let m = -Infinity; for (let k = a; k < lp.length; k += 3) m = Math.max(m, lp[k]); return m + 0.01 - llo[a]; });
        const q = new Uint16Array(lp.length);
        for (let k = 0; k < lp.length; k++) q[k] = Math.round((lp[k] - llo[k % 3]) / lsp[k % 3] * 65535);
        g.lid = {lo: llo, span: lsp, pos: buffer(gl.ARRAY_BUFFER, q), area: buffer(gl.ARRAY_BUFFER, new Uint8Array(lp.length / 3).fill(255)),
                 idx: buffer(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(li)), n: li.length};
      }
      // zone colours
      const pal = M.palette && M.palette.length ? M.palette : [[0.74, 0.72, 0.68]], pb = new Uint8Array(pal.length * 4);
      pal.forEach((c, i) => { pb[4 * i] = c[0] * 255; pb[4 * i + 1] = c[1] * 255; pb[4 * i + 2] = c[2] * 255; pb[4 * i + 3] = 255; });
      g.palT = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, g.palT);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, pal.length, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, pb);
      for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.NEAREST], [gl.TEXTURE_MAG_FILTER, gl.NEAREST], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
      g.paln = pal.length;
      const ys = M.cells.map(c => c[2]).sort((a, b) => a - b);
      g.hr = ys.length ? [ys[Math.floor(ys.length * 0.02)], ys[Math.floor(ys.length * 0.98)] + 2] : [0, 10];
      g.vox = {...p.head.vox, bits: p.vox};
      G = g;
      $('m3-msg').hidden = true;
    } catch (e) {
      if (M === tok) { G = null; $('m3-msg').textContent = e.message; $('m3-msg').hidden = false; setTimeout(() => { $('m3-msg').hidden = true; }, 4000); }
    }
  }
  function gameUniforms(alpha) {
    gl.useProgram(gprog);
    const e = eyePos();
    gl.uniformMatrix4fv(gloc.vp, false, VP); gl.uniform3fv(gloc.eye, e); gl.uniform1f(gloc.ey, e[1]);
    gl.uniform3fv(gloc.lo, G.lo); gl.uniform3fv(gloc.span, G.span);
    const R = G.roof.R;
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, G.roofT); gl.uniform1i(gloc.roof, 0);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, G.palT); gl.uniform1i(gloc.pal, 1);
    gl.activeTexture(gl.TEXTURE0);
    gl.uniform4f(gloc.rg, R.x0, R.z0, R.w * R.cell, R.h * R.cell); gl.uniform1f(gloc.rmin, R.ymin);
    gl.uniform1f(gloc.cut, opt.roofs ? 0 : 1); gl.uniform1f(gloc.rcut, ROOF);
    gl.uniform1f(gloc.paln, G.paln); gl.uniform1f(gloc.mode, {height: 1, areas: 2}[opt.colors] || 0);
    gl.uniform3fv(gloc.one, ONE); gl.uniform2fv(gloc.hr, G.hr); gl.uniform1f(gloc.alpha, alpha);
  }
  function drawBuffers(b) {
    gl.bindBuffer(gl.ARRAY_BUFFER, b.pos); gl.enableVertexAttribArray(gloc.q); gl.vertexAttribPointer(gloc.q, 3, gl.UNSIGNED_SHORT, true, 6, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, b.area); gl.enableVertexAttribArray(gloc.a); gl.vertexAttribPointer(gloc.a, 1, gl.UNSIGNED_BYTE, false, 1, 0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, b.idx);
    gl.drawElements(gl.TRIANGLES, b.n, gl.UNSIGNED_INT, 0);
    gl.disableVertexAttribArray(gloc.q); gl.disableVertexAttribArray(gloc.a);
  }
  function drawGame() {
    gameUniforms(1); drawBuffers(G);
    if (G.lid && !opt.roofs) {
      gl.uniform1f(gloc.cut, 0); gl.uniform3fv(gloc.lo, G.lid.lo); gl.uniform3fv(gloc.span, G.lid.span);
      drawBuffers(G.lid);
    }
    gl.useProgram(prog);
  }
  function drawGlass() {
    gameUniforms(0.22);
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false);
    drawBuffers(G.glass);
    gl.depthMask(true); gl.disable(gl.BLEND); gl.useProgram(prog);
  }
  function roofAt(x, z) {                          // the height above which things are cut away (or Infinity)
    if (!G || !G.ready || opt.roofs) return Infinity;
    const R = G.roof.R, j = Math.floor((x - R.x0) / R.cell), i = Math.floor((z - R.z0) / R.cell);
    if (i < 0 || j < 0 || i >= R.h || j >= R.w) return Infinity;
    return (G.roof.v[i * R.w + j] & ~3) / 100 + R.ymin + ROOF;
  }
  function solidAt(x, y, z) {
    const V = G.vox, c = V.cell;
    const ix = Math.floor((x - V.origin[0]) / c), iy = Math.floor((y - V.origin[1]) / c), iz = Math.floor((z - V.origin[2]) / c);
    if (ix < 0 || iy < 0 || iz < 0 || ix >= V.shape[0] || iy >= V.shape[1] || iz >= V.shape[2]) return false;
    const k = ix + V.shape[0] * (iz + V.shape[2] * iy);
    return (V.bits[k >> 3] >> (7 - (k & 7)) & 1) === 1 && y < roofAt(x, z);
  }
  // a clear line between two points? (true without the game's map: nothing to hide behind)
  function visible(a, b) {
    if (!G || !G.ready || !G.vox) return true;
    const d = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]), n = Math.ceil(d / (G.vox.cell * 0.5));
    for (let k = 1; k < n; k++) {
      const s = k / n, along = s * d;
      if (along < 0.6 || d - along < 0.5) continue;
      if (solidAt(a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s, a[2] + (b[2] - a[2]) * s)) return false;
    }
    return true;
  }

  // ---------------------------------------------------------------- 4.48: agent models
  // stats/agentmesh.py pack(): millimetres (x forward, y right, z up), normals, skin (4.50: animated, see below).
  // Placed per player: forward f = (sin yaw, -cos yaw) on the map, right = hand · (f.z, −f.x) (the map's minimap
  // may be mirrored: hand comes with the map). Drawn in the team's colour; walls hide them unless "see through
  // walls" is on (then the hidden parts show as a faint outline).
  const AVS = `attribute vec3 p; attribute vec3 nn; uniform mat4 vp; uniform vec3 at; uniform vec2 f; uniform vec2 r; uniform float sc; uniform float pu;
    varying vec3 vn; varying vec3 wp;
    void main(){ vec3 q = p * pu * sc; wp = at + vec3(q.x * f.x + q.y * r.x, q.z, q.x * f.y + q.y * r.y);
      vn = vec3(nn.x * f.x + nn.y * r.x, nn.z, nn.x * f.y + nn.y * r.y); gl_Position = vp * vec4(wp, 1.0); }`;
  const AFS = `precision mediump float; uniform vec3 col; uniform float alpha; uniform vec3 eye; varying vec3 vn; varying vec3 wp;
    void main(){ vec3 n = normalize(vn); vec3 L = normalize(vec3(0.3, 1.0, 0.2));
      float d = 0.45 + 0.55 * max(dot(n, L), 0.0); float rim = pow(1.0 - abs(dot(n, normalize(eye - wp))), 2.0);
      gl_FragColor = vec4(col * d + rim * 0.25, alpha); }`;
  let aprog = null, aloc = {};
  const models = new Map();                        // url -> {state, buf…}
  function initAgents() {
    if (aprog !== null) return !!aprog;
    const sh = (t, src) => { const x = gl.createShader(t); gl.shaderSource(x, src); gl.compileShader(x); return x; };
    aprog = gl.createProgram(); gl.attachShader(aprog, sh(gl.VERTEX_SHADER, AVS)); gl.attachShader(aprog, sh(gl.FRAGMENT_SHADER, AFS)); gl.linkProgram(aprog);
    if (!gl.getProgramParameter(aprog, gl.LINK_STATUS)) { console.error('agent shader:', gl.getProgramInfoLog(aprog)); aprog = false; return false; }
    for (const u of ['vp', 'at', 'f', 'r', 'sc', 'pu', 'col', 'alpha', 'eye']) aloc[u] = gl.getUniformLocation(aprog, u);
    aloc.p = gl.getAttribLocation(aprog, 'p'); aloc.nn = gl.getAttribLocation(aprog, 'nn');
    return true;
  }
  const head8 = buf => { const dv = new DataView(buf), n = dv.getUint32(4, true); return [JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 8, n))), 8 + n]; };
  function model(url) {                            // an agent or a gun (the same file format; guns have no skeleton)
    let m = models.get(url);
    if (m) return m.state === 'ready' ? m : null;
    m = {state: 'loading'}; models.set(url, m);
    fetch(url, {credentials: 'same-origin'}).then(r => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); }).then(buf => {
      const [head, base] = head8(buf);
      const sec = (k, Tp, size) => { const [o, l] = head.sections[k]; return new Tp(buf, base + o, l / size); };
      const b = (target, data) => { const x = gl.createBuffer(); gl.bindBuffer(target, x); gl.bufferData(target, data, gl.STATIC_DRAW); return x; };
      if (head.u32 && !gl.getExtension('OES_element_index_uint')) throw new Error('index');
      const pos = sec('pos', Int16Array, 2), nrm = sec('nrm', Int8Array, 1);
      Object.assign(m, {state: 'ready', head, pos: b(gl.ARRAY_BUFFER, pos), nrm: b(gl.ARRAY_BUFFER, nrm),
                        idx: b(gl.ELEMENT_ARRAY_BUFFER, head.u32 ? sec('idx', Uint32Array, 4) : sec('idx', Uint16Array, 2)), n: head.nt * 3, u32: head.u32});
      // 4.50: a copy for the CPU (skinning, the gun in the hand)
      const nv = head.nv, P = new Float32Array(nv * 3), N = new Float32Array(nv * 3);
      for (let i = 0; i < nv; i++) for (let c = 0; c < 3; c++) { P[i * 3 + c] = pos[i * 3 + c] * 0.001; N[i * 3 + c] = nrm[i * 4 + c] / 127; }
      m.cpu = {P, N, nv};
      if (head.joints && head.joints.length && head.sections.bind && head.sections.bind[1] === head.joints.length * 64) {
        const W = sec('weight', Uint8Array, 1), Wf = new Float32Array(W.length);
        for (let i = 0; i < W.length; i++) Wf[i] = W[i] / 255;
        Object.assign(m.cpu, {J: sec('joint', Uint8Array, 1), W: Wf, bind: new Float32Array(sec('bind', Float32Array, 4))});
      }
    }).catch(() => { m.state = 'failed'; });
    return null;
  }

  // ---------------------------------------------------------------- 4.50: animations
  // stats/agentanim.py pack(): the core skeleton's clips, played on every agent by joint name: rotations from the
  // clip, the bone lengths of the agent (its bind pose), the root and the pelvis moved by the clip (scaled to the
  // agent's size). The legs and the upper body ("Spine1" and below) can come from different clips. Skinned on the
  // CPU (a few thousand vertices per agent) into a buffer per player; the gun follows the right hand.
  // A pose: {lb: [[clip, seconds, weight], …], ub: [[clip, seconds, weight], …] | null}; o.hold: which grip
  // the gun sits in ("hold" a rifle, "pistol" both hands on a sidearm).
  let A = null, animUrl = null;
  function setAnims(url) {
    if (!url || url === animUrl) return;
    animUrl = url; A = null;
    fetch(url, {credentials: 'same-origin'}).then(r => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); }).then(buf => {
      const [head, base] = head8(buf), nj = head.joints.length, nm = head.move.length;
      const sec = (ol, Tp, size) => new Tp(buf, base + ol[0], ol[1] / size);
      const clips = {};
      for (const [k, c] of Object.entries(head.clips)) clips[k] = {...c, R: sec(c.rot, Int16Array, 2), T: sec(c.move, Float32Array, 4)};
      const ji = {}; head.joints.forEach((n, i) => { ji[n] = i; });
      const mi = {}; head.move.forEach((n, i) => { mi[n] = i; });
      const grips = {};
      for (const [k, g] of Object.entries(head.grips || {})) grips[k] = new Float32Array(g);
      A = {head, nj, nm, clips, ji, mi, fps: head.fps, rest: sec(head.sections.rest, Float32Array, 4), grip: head.grip ? new Float32Array(head.grip) : null, grips};
      for (const m of models.values()) m.rig = undefined;
    }).catch(() => { A = false; });
  }
  // 4x4 column-major helpers on Float32Arrays (o: offset in floats)
  function mulAt(out, oo, a, ao, b, bo) {
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
      out[oo + c * 4 + r] = a[ao + r] * b[bo + c * 4] + a[ao + 4 + r] * b[bo + c * 4 + 1] + a[ao + 8 + r] * b[bo + c * 4 + 2] + a[ao + 12 + r] * b[bo + c * 4 + 3];
    }
  }
  function invRigid(out, oo, m, mo) {              // the inverse of rotation (+ uniform scale) and translation
    const s2 = m[mo] * m[mo] + m[mo + 1] * m[mo + 1] + m[mo + 2] * m[mo + 2] || 1;
    for (let c = 0; c < 3; c++) for (let r = 0; r < 3; r++) out[oo + c * 4 + r] = m[mo + r * 4 + c] / s2;
    for (let r = 0; r < 3; r++) out[oo + 12 + r] = -(out[oo + r] * m[mo + 12] + out[oo + 4 + r] * m[mo + 13] + out[oo + 8 + r] * m[mo + 14]);
    out[oo + 3] = out[oo + 7] = out[oo + 11] = 0; out[oo + 15] = 1;
  }
  // 4.51: joints whose places the aim drills need for hits (head, body, arms, legs), in the map's frame
  const HIT = ['Head', 'Neck', 'Spine2', 'Spine4', 'Pelvis', 'L_Shoulder', 'L_Elbow', 'L_Hand', 'R_Shoulder', 'R_Elbow',
               'R_Hand', 'L_Hip', 'L_Knee', 'L_Foot', 'R_Hip', 'R_Knee', 'R_Foot'];
  function rig(m) {                                 // how the clips map onto this model's skeleton
    if (m.rig !== undefined) return m.rig;
    if (!A || !m.cpu || !m.cpu.bind) return (m.rig = A === null ? undefined : null) || null;
    const names = m.head.joints, par = m.head.parents, nj = names.length, bind = m.cpu.bind;
    const inv = new Float32Array(nj * 16), local = new Float32Array(nj * 16), tmp = new Float32Array(16);
    for (let j = 0; j < nj; j++) invRigid(inv, j * 16, bind, j * 16);
    for (let j = 0; j < nj; j++) {
      if (par[j] >= 0) mulAt(local, j * 16, inv, par[j] * 16, bind, j * 16);
      else local.set(bind.subarray(j * 16, j * 16 + 16), j * 16);
    }
    const aj = names.map(n => (n in A.ji ? A.ji[n] : -1)), mv = names.map(n => (n in A.mi ? A.mi[n] : -1));
    const scaled = names.map(n => (A.head.scaled || []).includes(n));
    const up = names.map((n, j) => { for (let p = j; p >= 0; p = par[p]) if (names[p] === A.head.upper) return true; return false; });
    let ps = 1;
    const sp = names.indexOf('Splitter'), as = A.ji.Splitter;
    if (sp >= 0 && as !== undefined) {
      const a = Math.hypot(local[sp * 16 + 12], local[sp * 16 + 13], local[sp * 16 + 14]);
      const b = Math.hypot(A.rest[as * 16 + 12], A.rest[as * 16 + 13], A.rest[as * 16 + 14]);
      if (b > 1e-6) ps = a / b;
    }
    const nv = m.cpu.nv;
    const hit = HIT.map(n => names.indexOf(n));
    return (m.rig = {nj, par, inv, local, aj, mv, scaled, up, ps, hit, hand: names.indexOf(A.head.gun || 'R_Hand'),
                     W: new Float32Array(nj * 16), S: new Float32Array(nj * 16), q: new Float32Array(4), t: new Float32Array(3),
                     L: new Float32Array(16), P: new Float32Array(nv * 3), N: new Float32Array(nv * 3), tmp});
  }
  function frameOf(c, secs) {                       // -> [f0, f1, frac]
    const n = c.frames;
    if (n <= 1) return [0, 0, 0];
    let f = Math.max(0, secs) * A.fps;
    if (c.loop) f %= (n - 1); else f = Math.min(f, n - 1);
    const f0 = Math.floor(f), f1 = Math.min(f0 + 1, n - 1);
    return [f0, f1, f - f0];
  }
  function blend(list, a, mi, q, t) {               // the weighted rotation (and move) of anim joint a from a list of clips
    q[0] = q[1] = q[2] = q[3] = 0; t[0] = t[1] = t[2] = 0;
    let wsum = 0;
    for (const [name, secs, w] of list) {
      const c = A.clips[name]; if (!c || w <= 0) continue;
      const [f0, f1, k] = frameOf(c, secs), o0 = (f0 * A.nj + a) * 4, o1 = (f1 * A.nj + a) * 4;
      let x0 = c.R[o0], y0 = c.R[o0 + 1], z0 = c.R[o0 + 2], w0 = c.R[o0 + 3];
      let x1 = c.R[o1], y1 = c.R[o1 + 1], z1 = c.R[o1 + 2], w1 = c.R[o1 + 3];
      if (x0 * x1 + y0 * y1 + z0 * z1 + w0 * w1 < 0) { x1 = -x1; y1 = -y1; z1 = -z1; w1 = -w1; }
      let qw = x0 + (x1 - x0) * k, qx = y0 + (y1 - y0) * k, qy = z0 + (z1 - z0) * k, qz = w0 + (w1 - w0) * k;  // stored (w, x, y, z)
      if (wsum > 0 && qw * q[0] + qx * q[1] + qy * q[2] + qz * q[3] < 0) { qw = -qw; qx = -qx; qy = -qy; qz = -qz; }
      q[0] += qw * w; q[1] += qx * w; q[2] += qy * w; q[3] += qz * w;
      if (mi >= 0) for (let i = 0; i < 3; i++) t[i] += (c.T[(f0 * A.nm + mi) * 3 + i] * (1 - k) + c.T[(f1 * A.nm + mi) * 3 + i] * k) * w;
      wsum += w;
    }
    if (wsum <= 0) return false;
    const n = Math.hypot(q[0], q[1], q[2], q[3]) || 1;
    for (let i = 0; i < 4; i++) q[i] /= n;
    for (let i = 0; i < 3; i++) t[i] /= wsum;
    return true;
  }
  function pose(R, spec) {                          // world matrices of the model's joints
    const {q, t, L, W, local} = R;
    for (let j = 0; j < R.nj; j++) {
      L.set(local.subarray(j * 16, j * 16 + 16));
      const a = R.aj[j];
      if (a >= 0) {
        const list = (R.up[j] && spec.ub) ? spec.ub : spec.lb;
        if (blend(list, a, R.mv[j], q, t)) {
          const [w, x, y, z] = q;
          L[0] = 1 - 2 * (y * y + z * z); L[1] = 2 * (x * y + w * z); L[2] = 2 * (x * z - w * y);
          L[4] = 2 * (x * y - w * z); L[5] = 1 - 2 * (x * x + z * z); L[6] = 2 * (y * z + w * x);
          L[8] = 2 * (x * z + w * y); L[9] = 2 * (y * z - w * x); L[10] = 1 - 2 * (x * x + y * y);
          if (R.mv[j] >= 0) { const s = R.scaled[j] ? R.ps : 1; L[12] = t[0] * s; L[13] = t[1] * s; L[14] = t[2] * s; }
        }
      }
      if (R.par[j] >= 0) mulAt(W, j * 16, W, R.par[j] * 16, L, 0); else W.set(L, j * 16);
    }
    return W;
  }
  function skin(m, R) {                             // the posed vertices (model frame, metres)
    const {S, W, inv, P, N} = R, cpu = m.cpu;
    for (let j = 0; j < R.nj; j++) mulAt(S, j * 16, W, j * 16, inv, j * 16);
    const VP0 = cpu.P, VN0 = cpu.N, J = cpu.J, Wt = cpu.W;
    for (let i = 0; i < cpu.nv; i++) {
      const x = VP0[i * 3], y = VP0[i * 3 + 1], z = VP0[i * 3 + 2], nx = VN0[i * 3], ny = VN0[i * 3 + 1], nz = VN0[i * 3 + 2];
      let px = 0, py = 0, pz = 0, qx = 0, qy = 0, qz = 0;
      for (let k = 0; k < 4; k++) {
        const w = Wt[i * 4 + k]; if (w <= 0) continue;
        const o = J[i * 4 + k] * 16;
        px += w * (S[o] * x + S[o + 4] * y + S[o + 8] * z + S[o + 12]);
        py += w * (S[o + 1] * x + S[o + 5] * y + S[o + 9] * z + S[o + 13]);
        pz += w * (S[o + 2] * x + S[o + 6] * y + S[o + 10] * z + S[o + 14]);
        qx += w * (S[o] * nx + S[o + 4] * ny + S[o + 8] * nz);
        qy += w * (S[o + 1] * nx + S[o + 5] * ny + S[o + 9] * nz);
        qz += w * (S[o + 2] * nx + S[o + 6] * ny + S[o + 10] * nz);
      }
      P[i * 3] = px; P[i * 3 + 1] = py; P[i * 3 + 2] = pz; N[i * 3] = qx; N[i * 3 + 1] = qy; N[i * 3 + 2] = qz;
    }
  }
  const inst = new Map();                          // player key -> {pb, nb, gb, gnb, gp, gn}: buffers of the posed model
  function dyn(buf, data) { gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW); }
  function animate(o, m) {                          // -> the instance with fresh buffers, or null (draw it standing)
    if (!o.anim || !A) return null;
    const R = rig(m); if (!R) return null;
    const W = pose(R, o.anim);
    skin(m, R);
    let it = inst.get(o.key);
    if (!it) { it = {pb: gl.createBuffer(), nb: gl.createBuffer(), gb: gl.createBuffer(), gnb: gl.createBuffer(), gun: null}; inst.set(o.key, it); }
    dyn(it.pb, R.P); dyn(it.nb, R.N);
    it.bones = {};                                  // 4.51: the hit joints on the map (model frame -> map frame)
    {
      const hd = (M && M.hand) || 1, f = [Math.sin(o.yaw), -Math.cos(o.yaw)], r = [hd * f[1], -hd * f[0]], sc = o.scale || 1;
      HIT.forEach((n, k) => {
        const j = R.hit[k]; if (j < 0) return;
        const x = W[j * 16 + 12] * sc, y = W[j * 16 + 13] * sc, z = W[j * 16 + 14] * sc;
        it.bones[n] = [o.x + x * f[0] + y * r[0], o.y + z, o.z + x * f[1] + y * r[1]];
      });
    }
    it.gun = null;
    const g = o.gun ? model(o.gun) : null;
    const grip = A.grips[o.hold] || A.grip;          // 4.50.1: a rifle or a pistol grip
    if (g && g.cpu && R.hand >= 0 && grip) {        // the gun: hand · grip · its vertices
      const G = R.tmp; mulAt(G, 0, W, R.hand * 16, grip, 0);
      const n = g.cpu.nv;
      if (!it.gp || it.gp.length !== n * 3) { it.gp = new Float32Array(n * 3); it.gn = new Float32Array(n * 3); }
      for (let i = 0; i < n; i++) {
        const x = g.cpu.P[i * 3], y = g.cpu.P[i * 3 + 1], z = g.cpu.P[i * 3 + 2], a = g.cpu.N[i * 3], b = g.cpu.N[i * 3 + 1], c = g.cpu.N[i * 3 + 2];
        for (let r = 0; r < 3; r++) {
          it.gp[i * 3 + r] = G[r] * x + G[4 + r] * y + G[8 + r] * z + G[12 + r];
          it.gn[i * 3 + r] = G[r] * a + G[4 + r] * b + G[8 + r] * c;
        }
      }
      dyn(it.gb, it.gp); dyn(it.gnb, it.gn);
      it.gun = g;
    }
    return it;
  }
  const GUN_COL = [0.16, 0.17, 0.19];
  // list: [{key, url, x, y, z, yaw, col: [r, g, b], anim?, gun?}] -> which of them were drawn as models (the rest need a marker)
  const drawn = new Set();
  function drawModels(list) {
    drawn.clear();
    if (!list || !list.length || !initAgents()) return;
    const hand = (M && M.hand) || 1, e = eyePos();
    gl.useProgram(aprog);
    gl.uniformMatrix4fv(aloc.vp, false, VP); gl.uniform3fv(aloc.eye, e);
    const ready = [];
    for (const o of list) {
      const m = o.url ? model(o.url) : null;
      if (m) ready.push([o, m, animate(o, m)]);
    }
    const mesh = (pb, ptype, pstride, pu, nb, ntype, nnorm, nstride, idx, n, u32) => {
      gl.uniform1f(aloc.pu, pu);
      gl.bindBuffer(gl.ARRAY_BUFFER, pb); gl.enableVertexAttribArray(aloc.p); gl.vertexAttribPointer(aloc.p, 3, ptype, false, pstride, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, nb); gl.enableVertexAttribArray(aloc.nn); gl.vertexAttribPointer(aloc.nn, 3, ntype, nnorm, nstride, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, idx);
      gl.drawElements(gl.TRIANGLES, n, u32 ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT, 0);
    };
    const pass = (alpha) => {
      for (const [o, m, it] of ready) {
        const f = [Math.sin(o.yaw), -Math.cos(o.yaw)];
        gl.uniform3f(aloc.at, o.x, o.y, o.z); gl.uniform2fv(aloc.f, f); gl.uniform2f(aloc.r, hand * f[1], -hand * f[0]);
        gl.uniform1f(aloc.sc, o.scale || 1); gl.uniform3fv(aloc.col, o.col); gl.uniform1f(aloc.alpha, alpha);
        if (it) mesh(it.pb, gl.FLOAT, 12, 1, it.nb, gl.FLOAT, false, 12, m.idx, m.n, m.u32);
        else mesh(m.pos, gl.SHORT, 6, 0.001, m.nrm, gl.BYTE, true, 4, m.idx, m.n, m.u32);
        if (it && it.gun) {
          gl.uniform3fv(aloc.col, GUN_COL);
          mesh(it.gb, gl.FLOAT, 12, 1, it.gnb, gl.FLOAT, false, 12, it.gun.idx, it.gun.n, it.gun.u32);
        }
        drawn.add(o.key);
      }
    };
    pass(1);
    if (opt.xray) {                                  // the hidden parts, faint
      gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false); gl.depthFunc(gl.GREATER);
      pass(0.35);
      gl.depthFunc(gl.LESS); gl.depthMask(true); gl.disable(gl.BLEND);
    }
    gl.disableVertexAttribArray(aloc.p); gl.disableVertexAttribArray(aloc.nn);
    gl.useProgram(prog);
  }
  // ---------------------------------------------------------------- 3D objects: smokes and other utility (4.46)
  // A lumpy unit ball, scaled per object; drawn after the map with the depth test on (walls hide them) and blended.
  // The fragment shader makes it look like smoke: noise in world space, light from above, a soft edge.
  const OVS = `attribute vec3 p; uniform mat4 vp; uniform vec4 s; uniform vec3 sc; uniform float seed; varying vec3 wp; varying vec3 nn;
    void main(){ float bump = 1.0 + 0.07 * sin(p.x * 5.0 + seed) * sin(p.y * 4.0 + seed * 0.7) * sin(p.z * 5.0 - seed);
      wp = s.xyz + p * sc * s.w * bump; nn = p; gl_Position = vp * vec4(wp, 1.0); }`;
  const OFS = `precision mediump float; uniform vec3 eye; uniform vec3 col; uniform float alpha; uniform float fseed; uniform float inside; uniform float cloudy;
    varying vec3 wp; varying vec3 nn;
    float h(vec3 q){ return fract(sin(dot(q, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
    float n3(vec3 x){ vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
      return mix(mix(mix(h(i), h(i + vec3(1,0,0)), f.x), mix(h(i + vec3(0,1,0)), h(i + vec3(1,1,0)), f.x), f.y),
                 mix(mix(h(i + vec3(0,0,1)), h(i + vec3(1,0,1)), f.x), mix(h(i + vec3(0,1,1)), h(i + vec3(1,1,1)), f.x), f.y), f.z); }
    void main(){
      vec3 n = normalize(nn); vec3 v = normalize(eye - wp);
      float cl = 0.5 * n3(wp * 0.55 + fseed) + 0.3 * n3(wp * 1.2 - fseed) + 0.2 * n3(wp * 2.6);
      float light = 0.62 + 0.38 * clamp(dot(n, normalize(vec3(0.3, 1.0, 0.2))), 0.0, 1.0);
      vec3 c = col * light * (1.0 - cloudy * 0.25 + cloudy * 0.45 * cl);
      float edge = (inside > 0.5 || cloudy < 0.5) ? 1.0 : smoothstep(0.0, 0.45, abs(dot(n, v)));
      gl_FragColor = vec4(c, alpha * edge * (1.0 - cloudy * 0.2 + cloudy * 0.3 * cl));
    }`;
  let oprog = null, oloc = {}, ball = null;
  function initObjects() {
    if (oprog !== null) return;
    const sh = (t, src) => { const x = gl.createShader(t); gl.shaderSource(x, src); gl.compileShader(x); return x; };
    oprog = gl.createProgram(); gl.attachShader(oprog, sh(gl.VERTEX_SHADER, OVS)); gl.attachShader(oprog, sh(gl.FRAGMENT_SHADER, OFS)); gl.linkProgram(oprog);
    if (!gl.getProgramParameter(oprog, gl.LINK_STATUS)) { console.error('utility shader:', gl.getProgramInfoLog(oprog)); oprog = false; return; }
    for (const u of ['vp', 's', 'sc', 'seed', 'fseed', 'eye', 'col', 'alpha', 'inside', 'cloudy']) oloc[u] = gl.getUniformLocation(oprog, u);
    oloc.p = gl.getAttribLocation(oprog, 'p');
    const v = [], R = 18, C = 28;                    // a UV sphere: triangles, outward
    const pt = (a, b) => [Math.sin(a) * Math.cos(b), Math.cos(a), Math.sin(a) * Math.sin(b)];
    for (let i = 0; i < R; i++) for (let j = 0; j < C; j++) {
      const a0 = i / R * Math.PI, a1 = (i + 1) / R * Math.PI, b0 = j / C * 2 * Math.PI, b1 = (j + 1) / C * 2 * Math.PI;
      const p00 = pt(a0, b0), p01 = pt(a0, b1), p10 = pt(a1, b0), p11 = pt(a1, b1);
      v.push(...p00, ...p10, ...p11, ...p00, ...p11, ...p01);
    }
    ball = {buf: gl.createBuffer(), n: v.length / 3};
    gl.bindBuffer(gl.ARRAY_BUFFER, ball.buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(v), gl.STATIC_DRAW);
  }
  function drawObjects(list) {
    if (!list || !list.length) return;
    initObjects();
    if (!oprog) return;
    const e = eyePos();
    list = list.map(o => ({...o, d: Math.hypot(o.x - e[0], o.y - e[1], o.z - e[2])})).sort((a, b) => b.d - a.d);   // far first
    gl.useProgram(oprog);
    gl.bindBuffer(gl.ARRAY_BUFFER, ball.buf);
    gl.enableVertexAttribArray(oloc.p); gl.vertexAttribPointer(oloc.p, 3, gl.FLOAT, false, 12, 0);
    gl.uniformMatrix4fv(oloc.vp, false, VP); gl.uniform3fv(oloc.eye, e);
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false); gl.enable(gl.CULL_FACE);
    gl.frontFace(gl.CW);                              // the ball's triangles are wound clockwise from outside
    for (const o of list) {
      const sc = o.sc || [1, 1, 1];
      const q = [(e[0] - o.x) / (o.r * sc[0]), (e[1] - o.y) / (o.r * sc[1]), (e[2] - o.z) / (o.r * sc[2])];
      const inside = Math.hypot(...q) < 1.02;
      gl.cullFace(inside ? gl.FRONT : gl.BACK);         // inside a smoke: its inner side, as fog all around
      gl.uniform4f(oloc.s, o.x, o.y, o.z, o.r); gl.uniform3fv(oloc.sc, sc);
      gl.uniform1f(oloc.seed, o.seed || 0); gl.uniform1f(oloc.fseed, o.seed || 0); gl.uniform3fv(oloc.col, o.col);
      gl.uniform1f(oloc.alpha, inside ? Math.min(0.94, (o.a || 0.8) + 0.15) : (o.a || 0.8));
      gl.uniform1f(oloc.inside, inside ? 1 : 0); gl.uniform1f(oloc.cloudy, o.cloudy === false ? 0 : 1);
      gl.drawArrays(gl.TRIANGLES, 0, ball.n);
    }
    gl.frontFace(gl.CCW); gl.disable(gl.CULL_FACE); gl.depthMask(true); gl.disable(gl.BLEND);
    gl.disableVertexAttribArray(oloc.p);
    gl.useProgram(prog);
  }
  // ---------------------------------------------------------------- overlays: callout names, radar
  function overlay(w, h, dpr) {
    const g = over.getContext('2d');
    g.clearRect(0, 0, w, h);
    g.lineJoin = 'round';
    if (opt.labels && VP) {
      g.textAlign = 'center'; g.font = `600 ${Math.round(13 * dpr)}px system-ui, sans-serif`;
      for (const c of M.callouts) {
        if (c.y === null) continue;
        const p = [c.x, c.y + 1.4, c.z, 1], q = [0, 0, 0, 0];
        for (let i = 0; i < 4; i++) q[i] = VP[i] * p[0] + VP[4 + i] * p[1] + VP[8 + i] * p[2] + VP[12 + i];
        if (q[3] <= 0.1) continue;
        const d = Math.hypot(c.x - me.x, c.z - me.z);
        if (d > 70) continue;
        if (G && G.ready && !visible(eyePos(), [c.x, c.y + 1.4, c.z])) continue;
        const sx = (q[0] / q[3] * 0.5 + 0.5) * w, sy = (1 - (q[1] / q[3] * 0.5 + 0.5)) * h;
        g.globalAlpha = Math.max(0.35, 1 - d / 80);
        g.lineWidth = 3 * dpr; g.strokeStyle = 'rgba(0,0,0,.75)'; g.strokeText(c.label, sx, sy);
        g.fillStyle = '#fff'; g.fillText(c.label, sx, sy);
      }
      g.globalAlpha = 1;
    }
    if (layer && layer.draw) layer.draw(g, project, w, h, dpr);
    radar.hidden = !opt.radar;
    if (opt.radar) drawRadar();
  }
  function drawRadar() {
    const g = radar.getContext('2d'), S = radar.width, k = S / 70;          // 35 m around you
    g.clearRect(0, 0, S, S);
    g.fillStyle = 'rgba(10,14,20,.72)'; g.fillRect(0, 0, S, S);
    g.save(); g.translate(S / 2, S / 2); g.rotate(-me.yaw);                 // you always look up
    const [ci, cj] = cellOf(me.x, me.z), span = Math.ceil(36 / M.cell);
    for (let i = ci - span; i <= ci + span; i++) for (let j = cj - span; j <= cj + span; j++) {
      const lv = levels(i, j); if (!lv) continue;
      const near = lv.reduce((a, l) => (Math.abs(l.h - me.y) < Math.abs(a.h - me.y) ? l : a));
      const c = baseColor(near), up = near.h - me.y;
      const f = up > 1.5 ? 0.55 : up < -1.5 ? 0.45 : 0.85;
      g.fillStyle = `rgb(${c[0] * 255 * f | 0},${c[1] * 255 * f | 0},${c[2] * 255 * f | 0})`;
      g.fillRect(((i + 0.5) * M.cell - me.x) * k - M.cell * k / 2, ((j + 0.5) * M.cell - me.z) * k - M.cell * k / 2, M.cell * k + 0.6, M.cell * k + 0.6);
    }
    if (opt.labels) {
      g.fillStyle = '#fff'; g.font = '10px system-ui, sans-serif'; g.textAlign = 'center';
      for (const c of M.callouts) {
        const x = (c.x - me.x) * k, y = (c.z - me.z) * k;
        if (Math.abs(x) > S / 2 || Math.abs(y) > S / 2) continue;
        g.save(); g.translate(x, y); g.rotate(me.yaw); g.fillText(c.label, 0, 0); g.restore();
      }
    }
    if (layer && layer.radar) layer.radar(g, (x, z) => [(x - me.x) * k, (z - me.z) * k], me.yaw, S);
    g.restore();
    g.fillStyle = 'rgba(255, 209, 102, .25)';
    g.beginPath(); g.moveTo(S / 2, S / 2); g.arc(S / 2, S / 2, S * 0.3, -Math.PI / 2 - 0.62, -Math.PI / 2 + 0.62); g.fill();
    g.fillStyle = '#ffd166'; g.beginPath(); g.moveTo(S / 2, S / 2 - 7); g.lineTo(S / 2 - 5, S / 2 + 5); g.lineTo(S / 2 + 5, S / 2 + 5); g.fill();
  }
  // ---------------------------------------------------------------- moving
  function step(dt, k = keys) {
    if (!M) return;
    me.crouch = k.has('ControlLeft') || k.has('ControlRight') || k.has('KeyX');
    const sp = me.fly ? 14 : me.crouch ? SPEED.crouch : (k.has('ShiftLeft') || k.has('ShiftRight')) ? SPEED.walk : SPEED.run;
    let fx = 0, fz = 0;
    const f = [Math.sin(me.yaw), -Math.cos(me.yaw)], r = [Math.cos(me.yaw), Math.sin(me.yaw)];
    if (k.has('KeyW')) { fx += f[0]; fz += f[1]; }
    if (k.has('KeyS')) { fx -= f[0]; fz -= f[1]; }
    if (k.has('KeyD')) { fx += r[0]; fz += r[1]; }
    if (k.has('KeyA')) { fx -= r[0]; fz -= r[1]; }
    const len = Math.hypot(fx, fz);
    if (len) { fx = fx / len * sp * dt; fz = fz / len * sp * dt; }
    if (me.fly) {
      me.x += fx; me.z += fz;
      if (k.has('Space')) me.y += sp * dt;
      if (me.crouch) me.y -= sp * dt;
      return;
    }
    if (len) {                                        // move, or slide along the wall
      if (!blocked(me.x + fx, me.z + fz, me.y)) { me.x += fx; me.z += fz; }
      else if (!blocked(me.x + fx, me.z, me.y)) me.x += fx;
      else if (!blocked(me.x, me.z + fz, me.y)) me.z += fz;
    }
    const fl = floorAt(me.x, me.z, me.y);
    if (k.has('Space') && me.ground) { me.vy = JUMP; me.ground = false; }
    if (fl === null) { me.vy = 0; return; }
    if (me.ground && me.y - fl > 0 && me.y - fl <= STEP) { me.y = fl; }        // walking down a step or a ramp
    else if (me.y > fl || me.vy > 0) {
      me.vy -= GRAV * dt; me.y += me.vy * dt; me.ground = false;
      if (me.y <= fl) { me.y = fl; me.vy = 0; me.ground = true; }
    } else { me.y = fl; me.ground = true; }
  }
  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    if (layer && layer.tick) layer.tick(dt);
    if (document.pointerLockElement === canvas) step(dt);
    else if (touch.on) step(dt, touchKeys());
    draw();
    $('m3-pos').textContent = M ? `${nearest()}${me.fly ? ' · ' + T('flying') : ''}` : '';
  }
  function inPoly(poly, x, z) {
    let ins = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, zi] = poly[i], [xj, zj] = poly[j];
      if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / ((zj - zi) || 1e-9) + xi) ins = !ins;
    }
    return ins;
  }
  function zoneAt(x, y, z) {                       // 4.48: the game's callout zone at a point ('' outside them)
    if (!M || !M.zones) return '';
    if (!M._zs) M._zs = M.zones.map(zz => ({...zz, area: Math.abs(zz.poly.reduce((a, p, i) => { const q = zz.poly[(i + 1) % zz.poly.length]; return a + p[0] * q[1] - q[0] * p[1]; }, 0)) / 2}))
      .sort((a, b) => a.area - b.area);
    let loose = '';
    for (const zz of M._zs) {
      if (!inPoly(zz.poly, x, z)) continue;
      if (y === null || (y >= zz.y0 - 1.5 && y <= zz.y1 + 1.5)) return zz.label;
      loose = loose || zz.label;
    }
    return loose;
  }
  function nearest() {
    const zl = zoneAt(me.x, me.y, me.z);
    if (zl) return zl;
    let b = null, bd = Infinity;
    for (const c of M.callouts) { const d = Math.hypot(c.x - me.x, c.z - me.z) + (c.y === null ? 0 : Math.abs(c.y - me.y) * 2); if (d < bd) { bd = d; b = c; } }
    return b ? b.label : '';
  }
  // ---------------------------------------------------------------- load a map
  async function load(name) {
    $('m3-msg').textContent = T('Loading…'); $('m3-msg').hidden = false;
    try {
      const r = await fetch(C.api + encodeURIComponent(name), {credentials: 'same-origin'});
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
      $('m3-msg').hidden = true;
      use(d);
      $('m3-info').textContent = d.game ? T('From the game\'s files') + ` · ${d.matches} ${T(d.matches === 1 ? 'replay' : 'replays')}`
        : T(`${d.matches} replay${d.matches === 1 ? '' : 's'} · ${Math.round(d.cells.length * d.cell * d.cell)} m² of floor`)
          + (d.game_status === 'building' ? ' · ' + T('the map from the game\'s files is being built') : '');
    } catch (e) { $('m3-msg').textContent = e.message; }
  }
  function recolor(mode) {                         // 4.46: floor colours: one | known | areas
    if (mode) { opt.colors = mode; saveOpt(); }
    if (!M || !gl) return;
    if (mesh && mesh.buf) gl.deleteBuffer(mesh.buf);
    mesh = buildMesh();
  }
  function freeGame() {
    if (!G || !G.ready || !gl) { G = null; return; }
    for (const b of [G.pos, G.area, G.idx, ...(G.glass ? [G.glass.pos, G.glass.area, G.glass.idx] : []), ...(G.lid ? [G.lid.pos, G.lid.area, G.lid.idx] : [])]) gl.deleteBuffer(b);
    gl.deleteTexture(G.roofT); gl.deleteTexture(G.palT);
    G = null;
  }
  function colorChoices() {                        // 4.48: "Height" for the game's maps, "Measured · guessed" for the others
    const sel = $('m3-colors'); if (!sel) return;
    for (const o of sel.options) {
      if (o.value === 'height') o.hidden = o.disabled = !(M && M.game);
      if (o.value === 'known') o.hidden = o.disabled = !!(M && M.game);
    }
    if (M && M.game && opt.colors === 'known') opt.colors = 'height';
    if (M && !M.game && opt.colors === 'height') opt.colors = 'known';
    sel.value = opt.colors;
    document.querySelectorAll('[data-legend]').forEach(x => { x.hidden = x.dataset.legend !== (M && M.game ? 'game' : 'replays'); });
  }
  function use(d) {
    freeGame();
    M = d; grid = buildGrid(d);
    if (!initGL()) { $('m3-msg').textContent = T('This browser has no WebGL.'); $('m3-msg').hidden = false; return; }
    colorChoices();
    mesh = buildMesh();
    if (d.game && d.mesh) loadGame(d);
    [me.x, me.y, me.z] = d.start; me.vy = 0; me.ground = true; me.yaw = 0; me.pitch = 0;
    const fl = floorAt(me.x, me.z, me.y + 2); if (fl !== null) me.y = fl;
    if (C.replay || C.drill) { me.fly = true; if (layer && layer.ready) layer.ready(); }
    if (!raf) raf = requestAnimationFrame(frame);
  }
  // ---------------------------------------------------------------- input
  // 4.49: the replay viewer has its own controls (replay.js, like the game's replays): no walking, no pointer lock
  const OWN = !C.replay && !C.drill;                 // 4.51: the aim drills (drill.js) drive the camera too
  canvas.addEventListener('click', () => { if (OWN && M && document.pointerLockElement !== canvas) canvas.requestPointerLock(); });
  document.addEventListener('pointerlockchange', () => { $('m3-start').hidden = !OWN || document.pointerLockElement === canvas; if (document.pointerLockElement !== canvas) keys.clear(); });
  document.addEventListener('mousemove', e => {
    if (!OWN || document.pointerLockElement !== canvas) return;
    const k = 0.07 * (+C.sens || 0.4) * D2R;
    me.yaw += e.movementX * k; me.pitch = Math.max(-1.5, Math.min(1.5, me.pitch - e.movementY * k));
  });
  document.addEventListener('keydown', e => {
    if (!OWN || document.pointerLockElement !== canvas) return;
    keys.add(e.code);
    if (['Space', 'ControlLeft', 'KeyW', 'KeyA', 'KeyS', 'KeyD'].includes(e.code)) e.preventDefault();
    if (e.code === 'KeyC') { opt.labels = !opt.labels; saveOpt(); }
    else if (e.code === 'KeyR') { opt.radar = !opt.radar; saveOpt(); }
    else if (e.code === 'KeyH') { opt.help = !opt.help; $('m3-help').hidden = !opt.help; saveOpt(); }
    else if (e.code === 'KeyF') { me.fly = !me.fly; if (!me.fly) { const fl = floorAt(me.x, me.z, me.y + 50); if (fl !== null && fl <= me.y + STEP) { me.ground = false; } } }
  });
  document.addEventListener('keyup', e => keys.delete(e.code));
  // ---------------------------------------------------------------- touch: left thumb moves, right thumb looks
  const touch = {on: false, move: null, look: null, jump: false};
  const DEAD = 12;
  function touchKeys() {
    const k = new Set();
    if (touch.move) {
      const {dx, dy} = touch.move;
      if (dy < -DEAD) k.add('KeyW'); if (dy > DEAD) k.add('KeyS');
      if (dx > DEAD) k.add('KeyD'); if (dx < -DEAD) k.add('KeyA');
      if (Math.hypot(dx, dy) < 34) k.add('ShiftLeft');                // a short push walks
    }
    if (touch.jump) { k.add('Space'); touch.jump = false; }
    return k;
  }
  const stick = document.createElement('div'); stick.className = 'm3-stick'; stick.hidden = true;
  stick.innerHTML = '<i></i>'; stage.appendChild(stick);
  function touchStart(e) {
    if (!M) return;
    e.preventDefault();
    if (!touch.on) { touch.on = true; $('m3-start').hidden = true; $('m3-jump').hidden = false; }
    const r = stage.getBoundingClientRect();
    for (const t of e.changedTouches) {
      const x = t.clientX - r.left, y = t.clientY - r.top;
      if (x < r.width / 2 && !touch.move) {
        touch.move = {id: t.identifier, x0: x, y0: y, dx: 0, dy: 0};
        stick.hidden = false; stick.style.left = x + 'px'; stick.style.top = y + 'px'; stick.firstChild.style.transform = '';
      } else if (!touch.look) touch.look = {id: t.identifier, x: t.clientX, y: t.clientY};
    }
  }
  function touchMove(e) {
    if (!touch.on) return;
    e.preventDefault();
    const r = stage.getBoundingClientRect();
    for (const t of e.changedTouches) {
      if (touch.move && t.identifier === touch.move.id) {
        let dx = t.clientX - r.left - touch.move.x0, dy = t.clientY - r.top - touch.move.y0;
        const l = Math.hypot(dx, dy); if (l > 42) { dx *= 42 / l; dy *= 42 / l; }
        touch.move.dx = dx; touch.move.dy = dy; stick.firstChild.style.transform = `translate(${dx}px,${dy}px)`;
      } else if (touch.look && t.identifier === touch.look.id) {
        const k = 0.35 * D2R;                       // degrees per pixel dragged
        me.yaw += (t.clientX - touch.look.x) * k;
        me.pitch = Math.max(-1.5, Math.min(1.5, me.pitch - (t.clientY - touch.look.y) * k));
        touch.look.x = t.clientX; touch.look.y = t.clientY;
      }
    }
  }
  function touchEnd(e) {
    for (const t of e.changedTouches) {
      if (touch.move && t.identifier === touch.move.id) { touch.move = null; stick.hidden = true; }
      if (touch.look && t.identifier === touch.look.id) touch.look = null;
    }
  }
  if (OWN) canvas.addEventListener('touchstart', touchStart, {passive: false});
  $('m3-start').addEventListener('touchstart', touchStart, {passive: false});
  canvas.addEventListener('touchmove', touchMove, {passive: false});
  canvas.addEventListener('touchend', touchEnd); canvas.addEventListener('touchcancel', touchEnd);
  $('m3-jump').addEventListener('touchstart', e => { e.preventDefault(); touch.jump = true; }, {passive: false});
  $('m3-jump').addEventListener('click', () => { touch.jump = true; });
  if (matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window) stage.classList.add('touch');
  document.querySelectorAll('[data-map]').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('[data-map]').forEach(x => x.classList.toggle('on', x === b));
    load(b.dataset.map);
  }));
  $('m3-labels').addEventListener('change', e => { opt.labels = e.target.checked; saveOpt(); });
  $('m3-radar-t').addEventListener('change', e => { opt.radar = e.target.checked; saveOpt(); });
  $('m3-labels').checked = opt.labels; $('m3-radar-t').checked = opt.radar; $('m3-help').hidden = !opt.help;
  if ($('m3-colors')) { $('m3-colors').value = opt.colors; $('m3-colors').addEventListener('change', e => recolor(e.target.value)); }
  if ($('m3-roofs')) { $('m3-roofs').checked = opt.roofs; $('m3-roofs').addEventListener('change', e => { opt.roofs = e.target.checked; saveOpt(); }); }
  if ($('m3-xray')) { $('m3-xray').checked = opt.xray; $('m3-xray').addEventListener('change', e => { opt.xray = e.target.checked; saveOpt(); }); }
  $('m3-full').addEventListener('click', () => { if (stage.requestFullscreen) stage.requestFullscreen().catch(() => {}); });
  const first = document.querySelector('[data-map]:not([disabled])');
  if (first) first.click();
  window.nexusMap3D = {state: () => ({me, opt, loaded: !!M, cells: M ? M.cells.length : 0, mesh: mesh ? mesh.n : 0, touch: touch.on}), use, step: (dt, ks) => step(dt, new Set(ks)), draw, floorAt, touchKeys: () => [...touchKeys()],
    // 4.44: the replay viewer draws on top and moves the camera
    setLayer: l => { layer = l; if (M && l && l.ready) l.ready(); }, project, recolor,
    visible, roofAt, zoneAt, drawnModel: k => drawn.has(k), eye: () => eyePos(),
    anims: url => setAnims(url), animsReady: () => !!A, clips: () => (A ? Object.keys(A.clips) : []),
    bones: k => { const it = inst.get(k); return it && it.bones ? it.bones : null; },     // 4.51: for the drills' hits
    game: () => (G && G.ready ? {tris: G.n / 3, glass: G.glass ? G.glass.n / 3 : 0, vox: G.vox.shape} : null),
    view: o => { Object.assign(me, o); }, map: () => M, setOpt: (k, v) => { opt[k] = v; saveOpt(); }, opt: () => opt};
  if (C.map) load(C.map);
})();
