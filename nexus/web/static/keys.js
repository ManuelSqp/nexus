// 4.51: your own keys (Practice › Aim on maps, and in a drill). Every action can have two keys or mouse buttons;
// they're saved with your account (POST /api/aim/keys) and the same on every PC. Esc always stops and can't be
// changed. Codes: the keyboard's e.code names ("KeyR", "Space", …), "Mouse0".."Mouse4" (e.button), "WheelUp",
// "WheelDown".
(function () {
  'use strict';
  const T = s => (window.vcT ? window.vcT(s) : s);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const NAMES = {Mouse0: 'Mouse 1', Mouse2: 'Mouse 2', Mouse1: 'Mouse 3', Mouse3: 'Mouse 4', Mouse4: 'Mouse 5',
                 WheelUp: 'Wheel up', WheelDown: 'Wheel down', Space: 'Space', Backspace: 'Backspace', Enter: 'Enter',
                 Tab: 'Tab', ControlLeft: 'Ctrl', ControlRight: 'Right Ctrl', ShiftLeft: 'Shift', ShiftRight: 'Right Shift',
                 AltLeft: 'Alt', AltRight: 'Alt Gr', CapsLock: 'Caps Lock', ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←',
                 ArrowRight: '→', Backquote: '`', Minus: '-', Equal: '=', BracketLeft: '[', BracketRight: ']',
                 Semicolon: ';', Quote: "'", Comma: ',', Period: '.', Slash: '/', Backslash: '\\'};
  function label(code) {
    if (!code) return '';
    if (NAMES[code]) return T(NAMES[code]);
    let m = /^Key([A-Z])$/.exec(code); if (m) return m[1];
    m = /^Digit(\d)$/.exec(code); if (m) return m[1];
    m = /^Numpad(.+)$/.exec(code); if (m) return 'Num ' + m[1];
    return code;
  }
  function normalize(keys, defaults) {
    const out = {};
    for (const a of Object.keys(defaults || keys || {})) {
      const v = (keys || {})[a] || (defaults || {})[a] || ['', ''];
      out[a] = [v[0] || '', v[1] || ''];
    }
    return out;
  }
  const actionsOf = (keys, code) => Object.keys(keys).filter(a => keys[a].includes(code));
  function clashes(keys) {
    const seen = {}, out = [];
    for (const [a, ks] of Object.entries(keys)) for (const k of ks) {
      if (!k) continue;
      if (seen[k] && seen[k] !== a) out.push([k, seen[k], a]); else seen[k] = a;
    }
    return out;
  }
  const codeOfMouse = b => 'Mouse' + b;

  // the editor: rows of actions with two key buttons each; click one, then press a key, a mouse button or turn the
  // wheel (Esc cancels). opts: {keys, defaults, actions: {action: label}, api, onSave(keys)}
  const pairs = acts => (Array.isArray(acts) ? acts : Object.entries(acts || {}));    // [[action, label], …] in order
  function editor(box, opts) {
    let keys = normalize(opts.keys, opts.defaults), wait = null;
    const names = Object.fromEntries(pairs(opts.actions));
    function render(msg) {
      const cl = clashes(keys), bad = new Set(cl.map(c => c[0]));
      box.innerHTML = `<div class="kb-rows">${pairs(opts.actions).map(([a, name]) =>
        `<div class="kb-row"><span class="kb-name">${esc(T(name))}</span>` +
        [0, 1].map(i => {
          const k = keys[a][i], on = wait && wait[0] === a && wait[1] === i;
          return `<button type="button" class="kb-key ${on ? 'on' : ''} ${k && bad.has(k) ? 'bad' : ''} ${!k ? 'empty' : ''}" data-kb="${a}:${i}" ` +
                 `aria-label="${esc(T(name))} ${i ? T('second key') : T('key')}: ${esc(k ? label(k) : T('none'))}">` +
                 `${on ? esc(T('press a key…')) : esc(k ? label(k) : (i ? T('+ second key') : T('none')))}</button>` +
                 (i && k ? `<button type="button" class="kb-x" data-kbx="${a}" aria-label="${esc(T('Remove the second key'))}">×</button>` : '');
        }).join('') + '</div>').join('')}</div>` +
        (cl.length ? `<p class="kb-clash">${cl.map(([k, a, b]) => `<b>${esc(label(k))}</b> ${esc(T('is on two actions:'))} ${esc(T(names[a]))}, ${esc(T(names[b]))}`).join('<br>')}</p>` : '') +
        `<p class="kb-foot"><button type="button" class="btn sm primary" data-kbsave>${esc(T('Save'))}</button> ` +
        `<button type="button" class="btn sm ghost" data-kbreset>${esc(T('Back to the defaults'))}</button> ` +
        `<span class="muted small">${esc(T('Esc always stops a drill and can\'t be changed.'))}</span> <span class="kb-msg">${esc(msg || '')}</span></p>`;
    }
    function set(code) {
      if (!wait) return;
      const [a, i] = wait;
      keys[a][i] = code;
      wait = null; render();
    }
    let swallow = false;                         // the click after a mouse button was taken as the answer
    box.addEventListener('click', e => {
      if (swallow) { swallow = false; return; }
      const b = e.target.closest('[data-kb]');
      if (b) { const [a, i] = b.dataset.kb.split(':'); wait = [a, +i]; render(); return; }
      const x = e.target.closest('[data-kbx]');
      if (x) { keys[x.dataset.kbx][1] = ''; render(); return; }
      if (e.target.closest('[data-kbreset]')) { keys = normalize(opts.defaults, opts.defaults); wait = null; render(); return; }
      if (e.target.closest('[data-kbsave]')) save();
    });
    // while waiting, the next key or button is the answer (and nothing else gets it)
    const grab = e => {
      if (!wait || !box.isConnected || box.closest('[hidden]')) return;
      e.preventDefault(); e.stopPropagation();
      if (e.type === 'keydown') { if (e.code === 'Escape') { wait = null; render(); } else set(e.code); }
      else if (e.type === 'mousedown') { swallow = true; set(codeOfMouse(e.button)); }
      else if (e.type === 'wheel') set(e.deltaY < 0 ? 'WheelUp' : 'WheelDown');
    };
    document.addEventListener('keydown', grab, true);
    box.addEventListener('mousedown', e => {
      if (!wait) return;
      const tb = e.target.closest('[data-kb]');
      if (!tb || tb.classList.contains('on') || e.button !== 0) grab(e);   // another key's button: pick that one
    }, true);
    box.addEventListener('wheel', e => { if (wait) grab(e); }, {passive: false});
    box.addEventListener('contextmenu', e => { if (wait) e.preventDefault(); });
    async function save() {
      try {
        const r = await fetch(opts.api, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(keys)});
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
        keys = normalize(d.keys, opts.defaults);
        render(T('Saved.'));
        if (opts.onSave) opts.onSave(keys);
      } catch (err) { render(err.message); }
    }
    render();
    return {keys: () => keys};
  }

  window.NexusKeys = {label, normalize, actionsOf, clashes, editor, codeOfMouse, pairs};
})();
