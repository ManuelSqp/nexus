// 4.51: Practice › Aim on maps: the list of your deaths as drills (web/drills.py). One card per spot: the same
// angle killing you again is "×2", "×3". The drills of new matches are worked out on the server in the
// background; the page asks again until they're all there.
(function () {
  'use strict';
  const C = window.NEXUS_DRILLS;
  if (!C) return;
  const $ = id => document.getElementById(id);
  const T = s => (window.vcT ? window.vcT(s) : s);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
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
    const sel = $('am-map'), keep = f.map;
    sel.innerHTML = `<option value="">${esc(T('All maps'))}</option>` + d.maps.map(m => `<option value="${esc(m)}" translate="no">${esc(m)}</option>`).join('');
    sel.value = d.maps.includes(keep) ? keep : '';
    const spots = d.spots.filter(s => (!sel.value || s.map === sel.value) && (!f.first || s.first === 'killer'));
    const beaten = spots.filter(s => s.beaten).length;
    $('am-stats').innerHTML = `<div><b>${d.deaths}</b><small>${esc(T('deaths with a replay'))}</small></div>` +
      `<div><b>${spots.length}</b><small>${esc(T('spots'))}${sel.value ? ' · <span translate="no">' + esc(sel.value) + '</span>' : ''}</small></div>` +
      `<div><b class="good">${beaten} / ${spots.length}</b><small>${esc(T('beaten (faster than him)'))}</small></div>`;
    $('am-n').textContent = '· ' + d.deaths;
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
  let ed = null;
  $('am-keys-btn').addEventListener('click', () => {
    const box = $('am-keys');
    box.hidden = !box.hidden;
    if (!box.hidden && !ed) ed = window.NexusKeys.editor($('am-keys-box'), {keys: C.keys, defaults: C.defaults, actions: C.actions, api: C.keys_api});
  });
  load();
})();
