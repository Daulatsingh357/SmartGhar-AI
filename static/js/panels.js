/* Right-hand properties panel, drawings tab, cost tab, report tab, live Vastu panel. */
const CATS = { living: 'living', master: 'sleeping', guest: 'sleeping', kids: 'sleeping', kitchen: 'service', dining: 'living', bathroom: 'wet', toilet: 'wet', pooja: 'service', balcony: 'outdoor', parking: 'parking', garden: 'outdoor', staircase: 'circulation', store: 'service', utility: 'service', lounge: 'living' };
const LABEL = Object.fromEntries([...ROOMS.map(r => [r[0], r[1]]), ['lounge', 'Family Lounge']]);
const stIcon = { ideal: '&#9989;', acceptable: '&#128993;', neutral: '&#9898;', ok: '&#128993;', avoid: '&#10060;' };
const stCls = { ideal: 'ok', acceptable: 'warn', neutral: '', ok: 'warn', avoid: 'err' };

function summaryHTML(p) {
  const m = p.metrics, v = p.vastu;
  return `<h4>${esc(p.title)}</h4>
  <div class="pcard" style="padding:12px"><div style="display:flex;justify-content:space-between;align-items:center"><div><div class="vs">${v.score}<small style="font-size:14px">/100</small></div><span class="tag">${esc(v.grade)}</span></div><small style="color:var(--mute);text-align:right">Vastu score<br>${esc(p.vastu_mode)} mode</small></div></div>
  <div class="res"><div><span>Built-up (all floors)</span><b>${m.built_total_sqft} sq ft</b></div><div><span>Footprint</span><b>${m.footprint_sqft} sq ft</b></div><div><span>Ground coverage</span><b>${m.coverage_pct}%</b></div><div><span>FAR</span><b>${m.far}</b></div><div><span>Open space</span><b>${m.open_space_sqft} sq ft</b></div></div>
  ${p.warnings.map(w => `<p class="warn" style="font-size:12.5px">&#9888; ${esc(w)}</p>`).join('')}
  ${p.validation.length ? `<h4 style="margin-top:16px;font-size:14px">Validation</h4>` + p.validation.slice(0, 12).map(v => `<p class="${v.level === 'error' ? 'err' : 'warn'}" style="font-size:12.5px;margin:4px 0">${v.level === 'error' ? '&#10060;' : '&#9888;'} ${esc(v.floor)}: ${esc(v.msg)}</p>`).join('') : '<p class="ok">&#10003; Geometry valid: no overlaps, rooms within setbacks.</p>'}
  <p class="hint" style="margin-top:14px">Click a room to edit it. Drag a room onto another to swap their functions; drag the gold handles to move shared walls; drag doors and windows along their wall. Ctrl+Z / Ctrl+Y for undo / redo.</p>`;
}
function renderProps() {
  const p = plan(), box = $('#props'); if (!p) { box.innerHTML = '<p class="hint">Generated plans appear here with room details, Vastu notes and validation.</p>'; return; }
  const sel = S.view === '3d' ? S.sel3 : S.sel;
  if (!sel) { box.innerHTML = summaryHTML(p); return; }
  if (sel.kind === 'furn') {
    const it = sel.item; box.innerHTML = `<h4>${esc(it.kind.replace('_', ' '))}</h4><div class="res"><div><span>Size</span><b>${fmtFt(it.w)} x ${fmtFt(it.h)}</b></div></div><div style="display:flex;gap:8px;margin-top:12px"><button class="btn sm" id="f-rot">Rotate 90&deg;</button><button class="btn sm danger" id="f-del">Delete</button></div><p class="hint">Drag in the 3D view to move it within its room.</p>`;
    $('#f-rot').onclick = () => { const f = p.floors[sel.fi]; [it.w, it.h] = [it.h, it.w]; f.custom_furniture = true; onEdit(p, 'furniture'); S.v3dDirty = false; v3.setPlan(p, true); };
    $('#f-del').onclick = () => { const f = p.floors[sel.fi]; f.furniture = f.furniture.filter(x => x !== it); f.custom_furniture = true; S.sel3 = null; onEdit(p, 'furniture'); v3.setPlan(p, true); renderProps(); };
    return;
  }
  const fi = sel.fi ?? S.fi, f = p.floors[fi];
  if (sel.kind === 'room') {
    const r = f.rooms.find(x => x.id === sel.id); if (!r) { box.innerHTML = summaryHTML(p); return; }
    const vi = p.vastu.items.find(i => i.room === r.name && i.floor === f.name);
    const typeOpts = Object.entries(LABEL).filter(([k]) => !['garden', 'staircase'].includes(r.type) || k === r.type).map(([k, l]) => `<option value="${k}" ${k === r.type ? 'selected' : ''}>${l}</option>`).join('');
    box.innerHTML = `<h4>${esc(r.name)}</h4><span class="tag">${esc(f.name)}</span>
    <div class="res"><div><span>Size</span><b>${fmtFt(r.w)} x ${fmtFt(r.h)}</b></div><div><span>Area</span><b>${(r.w * r.h).toFixed(0)} sq ft (${(r.w * r.h * .0929).toFixed(1)} m&sup2;)</b></div></div>
    <label>Room name</label><input id="r-name" value="${esc(r.name)}">
    ${S.view === '2d' ? `<label>Function</label><select id="r-type">${typeOpts}</select>
    <div class="two"><div><label>Width (ft)</label><input id="r-w" type="number" step=".5" value="${r.w}"></div><div><label>Depth (ft)</label><input id="r-h" type="number" step=".5" value="${r.h}"></div></div>
    <button class="btn sm gold" id="r-apply" style="margin-top:8px">Apply size</button>
    <label>Add opening on wall</label><div class="two"><select id="o-wall"><option value="N">North</option><option value="E">East</option><option value="S">South</option><option value="W">West</option></select><div style="display:flex;gap:6px"><button class="btn sm ghost" id="o-door">+ Door</button><button class="btn sm ghost" id="o-win">+ Window</button></div></div>` :
    `<label>Floor material</label><select id="r-fm"><option value="">Default</option><option value="tile">Tile</option><option value="wood">Wood</option><option value="marble">Marble</option><option value="concrete">Concrete</option></select>`}
    ${vi ? `<div class="pcard" style="margin-top:14px;padding:12px"><b class="${stCls[vi.status]}">${stIcon[vi.status]} Vastu: ${esc(vi.zone)} zone (${esc(vi.status)})</b><p class="hint" style="margin:6px 0 0">${esc(vi.why)}<br><i>${esc(vi.advice)}</i></p></div>` : ''}`;
    $('#r-name').onchange = e => ed.update('room', r.id, { name: e.target.value.slice(0, 40) || r.name });
    if (S.view === '3d') { $('#r-fm').value = r.floor_mat || ''; $('#r-fm').onchange = e => { r.floor_mat = e.target.value || undefined; S.dirty = true; v3.setPlan(p, true); }; return; }
    $('#r-type').onchange = e => { const t = e.target.value; ed.update('room', r.id, { type: t, name: LABEL[t], cat: CATS[t] }); };
    $('#r-apply').onclick = () => ed.setRoomSize(r.id, parseFloat($('#r-w').value), parseFloat($('#r-h').value));
    $('#o-door').onclick = () => ed.addOpening('door', r.id, $('#o-wall').value); $('#o-win').onclick = () => ed.addOpening('window', r.id, $('#o-wall').value);
    return;
  }
  const arr = sel.kind === 'door' ? f.doors : f.windows, o = (arr || []).find(x => x.id === sel.id); if (!o) { box.innerHTML = summaryHTML(p); return; }
  const rm = f.rooms.find(r => r.id === o.room), len = o.wall === 'N' || o.wall === 'S' ? rm.w : rm.h;
  box.innerHTML = `<h4>${sel.kind === 'door' ? (o.kind === 'main' ? 'Main entrance' : 'Door') : 'Window'}</h4><span class="tag">${esc(rm.name)} - ${o.wall} wall</span>
  <label>Width (ft)</label><input id="o-w" type="number" step=".5" min="1.5" max="${len - 1}" value="${o.width}">
  <label>Position along wall: ${fmtFt(o.t)}</label><input id="o-t" type="range" min="${o.width / 2 + .5}" max="${len - o.width / 2 - .5}" step=".25" value="${o.t}">
  ${sel.kind === 'window' ? `<div class="two"><div><label>Sill (ft)</label><input id="o-s" type="number" step=".5" value="${o.sill}"></div><div><label>Head (ft)</label><input id="o-h" type="number" step=".5" value="${o.head}"></div></div>` : ''}
  <button class="btn sm danger" id="o-del" style="margin-top:12px">Delete</button><p class="hint">Or drag it along the wall on the plan.</p>`;
  $('#o-w').onchange = e => ed.update(sel.kind, o.id, { width: Math.min(Math.max(+e.target.value, 1.5), len - 1) });
  $('#o-t').oninput = e => ed.update(sel.kind, o.id, { t: +e.target.value });
  if (sel.kind === 'window') { $('#o-s').onchange = e => ed.update('window', o.id, { sill: +e.target.value }); $('#o-h').onchange = e => ed.update('window', o.id, { head: +e.target.value }); }
  $('#o-del').onclick = () => ed.deleteSel();
}
function renderVastuLive() {
  const p = plan(), b = $('#vastu-live'); if (!p) { b.innerHTML = ''; return; }
  const v = p.vastu, e = v.entrance;
  b.innerHTML = `<div class="pcard"><div class="vs">${v.score}<small style="font-size:14px">/100</small> <span class="tag">${esc(v.grade)}</span></div><div class="bar"><i style="width:${v.score}%"></i></div></div>
  <p class="hint"><b class="${stCls[e.status]}">${stIcon[e.status]} Entrance: ${esc(e.zone)}</b> - ${esc(e.advice)}</p><p class="hint">${esc(v.windows.advice)}</p>
  ${v.items.map(i => `<p style="font-size:12.5px;margin:6px 0"><b class="${stCls[i.status]}">${stIcon[i.status]} ${esc(i.room)}</b> <small>(${esc(i.floor.replace(' Floor', ''))}, ${esc(i.zone)})</small><br><span class="hint">${esc(i.advice)}</span></p>`).join('')}`;
}
/* ---------- drawings ---------- */
function renderDraw() {
  const p = plan(); if (!p) return;
  $('#drawlist').innerHTML = Drawings.LIST.map(([k, l, perFloor]) => `<button data-d="${k}" class="${k === S.draw ? 'on' : ''}">${l}${perFloor ? ' <small>(per floor)</small>' : ''}</button>`).join('');
  $$('#drawlist button').forEach(b => b.onclick = () => { S.draw = b.dataset.d; renderDraw(); });
  try { $('#drawsvg').innerHTML = Drawings.render(S.draw, p, S.fi); } catch (e) { $('#drawsvg').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
/* ---------- cost ---------- */
async function renderCost(force) {
  const p = plan(), box = $('#cost'); if (!p) return;
  if (!S.est || force) { box.innerHTML = '<p>Calculating...</p>'; try { S.est = await api('/api/estimate', { plan: p, city: $('#in-city').value, overrides: S.overrides }); } catch (e) { box.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; } }
  const { estimate: e, prices, city } = S.est, q = e.quantities, budget = parseFloat($('#in-budget').value) || 0, tot = Math.max(...Object.values(e.cost_groups));
  const qc = [['Cement', q.cement_bags + ' bags'], ['Sand', q.sand_m3 + ' m³'], ['Aggregate', q.aggregate_m3 + ' m³'], ['Bricks', q.bricks.toLocaleString('en-IN')], ['Steel', q.steel_tonnes + ' t'], ['Concrete', q.concrete_m3 + ' m³'], ['Tiles', q.tiles_sqft.toLocaleString('en-IN') + ' sq ft'], ['Paint', q.paint_litres + ' L']];
  box.innerHTML = `<div class="grid g3"><div class="pcard"><small>Total construction cost (approx.)</small><div class="vs">${inr(e.total)}</div><small>${inr(e.per_sqft)} per sq ft - ${e.built_sqft} sq ft built-up</small>${budget ? `<p class="${e.total <= budget ? 'ok' : 'err'}">${e.total <= budget ? 'Within' : 'Over'} budget of ${inr(budget)} by ${inr(Math.abs(budget - e.total))}</p>` : ''}</div>
  <div class="pcard" style="grid-column:span 2"><b>Cost breakup</b>${Object.entries(e.cost_groups).map(([k, v]) => `<div style="display:grid;grid-template-columns:100px 1fr 110px;gap:10px;align-items:center;margin:8px 0;font-size:13px"><span>${k}</span><div class="bar"><i style="width:${v / tot * 100}%"></i></div><b style="text-align:right">${inr(v)}</b></div>`).join('')}</div></div>
  <div class="grid g4" style="margin-bottom:16px">${qc.map(([a, b]) => `<div class="pcard" style="margin:0;padding:12px"><small>${a}</small><div style="font-size:20px;font-weight:700">${b}</div></div>`).join('')}</div>
  <div class="grid g2"><div class="pcard"><b>Bill of quantities</b><table class="t"><tr><th>Item</th><th>Qty</th><th>Rate</th><th style="text-align:right">Amount</th></tr>${e.rows.map(r => `<tr><td>${esc(r.item)}</td><td>${(+r.qty).toLocaleString('en-IN', { maximumFractionDigits: 1 })} ${esc(r.unit)}</td><td>${(+r.rate).toLocaleString('en-IN')}</td><td style="text-align:right">${inr(r.amount)}</td></tr>`).join('')}<tr><td colspan="3"><b>Contingency (${e.contingency_pct}%)</b></td><td style="text-align:right">${inr(e.contingency)}</td></tr></table></div>
  <div class="pcard"><b>Material prices - ${esc(city)}</b> <small>(edit to match your local rates)</small><div style="display:flex;gap:8px;margin:10px 0"><input id="cost-city" list="cities" value="${esc(city)}" style="max-width:150px"><button class="btn sm ghost" id="cost-load">Load city rates</button></div>
  <table class="t">${Object.entries(prices).map(([k, v]) => `<tr><td>${esc(v.label)}<br><small style="color:var(--mute)">per ${esc(v.unit)}</small></td><td><input data-pk="${k}" type="number" min="0" step="any" value="${v.price}" style="max-width:110px"></td></tr>`).join('')}</table>
  <button class="btn gold sm" id="cost-calc" style="margin-top:10px">Recalculate</button> <button class="btn sm" id="cost-pdf">Estimate PDF</button></div></div>
  <ul class="hint">${e.assumptions.map(a => `<li>${esc(a)}</li>`).join('')}</ul>`;
  $('#cost-calc').onclick = () => { S.overrides = {}; $$('[data-pk]').forEach(i => { if (i.value !== '') S.overrides[i.dataset.pk] = parseFloat(i.value); }); renderCost(true); };
  $('#cost-load').onclick = () => { S.overrides = {}; $('#in-city').value = $('#cost-city').value; renderCost(true); };
  $('#cost-pdf').onclick = () => exportPdf('estimate');
}
/* ---------- report ---------- */
function renderReport() {
  const p = plan(), box = $('#report'); if (!p) return; const m = p.metrics, pl = p.plot;
  box.innerHTML = `<div class="grid g2"><div class="pcard"><h3 class="serif" style="margin-top:0">${esc(p.title)}</h3>
  <div class="res"><div><span>Plot</span><b>${pl.ex} x ${pl.ny} ft (${pl.shape})</b></div><div><span>Area</span><b>${pl.areas.sqft} sq ft / ${pl.areas.sqm} m&sup2; / ${pl.areas.sqyd} sq yd</b></div><div><span>Road</span><b>${pl.road} side</b></div><div><span>Setbacks F/R/S</span><b>${pl.setbacks.front}/${pl.setbacks.rear}/${pl.setbacks.side} ft</b></div><div><span>Built-up total</span><b>${m.built_total_sqft} sq ft</b></div><div><span>Coverage / FAR</span><b>${m.coverage_pct}% / ${m.far}</b></div><div><span>Open space</span><b>${m.open_space_sqft} sq ft</b></div><div><span>Vastu score</span><b>${p.vastu.score}/100 ${esc(p.vastu.grade)}</b></div></div>
  <h4>Space utilisation</h4>${m.utilisation.map(u => `<div style="display:grid;grid-template-columns:140px 1fr 90px;gap:10px;align-items:center;font-size:13px;margin:6px 0"><span>${esc(u.category)}</span><div class="bar"><i style="width:${u.pct}%"></i></div><span>${u.sqft.toFixed(0)} sq ft</span></div>`).join('')}</div>
  <div class="pcard"><h4 style="margin-top:0">Design recommendations</h4><ul style="line-height:1.7;font-size:14px">${p.recommendations.map(r => `<li>${esc(r)}</li>`).join('')}</ul>
  <button class="btn sm gold" id="ai-btn">&#10024; AI design commentary</button><div id="ai-out" class="hint" style="margin-top:10px;white-space:pre-wrap"></div></div></div>
  <div class="pcard"><h4 style="margin-top:0">Room-wise dimensions</h4><table class="t"><tr><th>Floor</th><th>Room</th><th>Size</th><th>Area (sq ft)</th></tr>${m.rooms.map(r => `<tr><td>${esc(r.floor)}</td><td>${esc(r.name)}</td><td>${esc(r.dims)}</td><td>${r.area_sqft}</td></tr>`).join('')}</table></div>
  <p class="hint">${esc(SG.disclaimer)}</p>`;
  $('#ai-btn').onclick = async e => { e.target.disabled = true; $('#ai-out').textContent = 'Thinking...'; try { const r = await api('/api/commentary', { plan: p, inputs: S.inputs || {} }); $('#ai-out').textContent = r.text + (r.source === 'rules' ? '\n\n(Rule-based summary - add LLM_API_KEY in .env for AI commentary.)' : ''); } catch (er) { $('#ai-out').textContent = er.message; } e.target.disabled = false; };
}
