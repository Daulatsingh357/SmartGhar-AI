/* Studio controller: inputs -> /api/generate -> editors/viewers/panels. */
const S = { inputs: null, plans: [], opt: 0, fi: 0, pid: SG.pid, view: '2d', draw: 'plan', dirty: false, overrides: {}, est: null, vmode: 'flexible', sel: null, v3dDirty: true };
const ROOMS = [['living', 'Living Room', 1], ['master', 'Master Bedroom', 1], ['guest', 'Guest Bedroom', 0], ['kids', "Children's Bedroom", 1], ['kitchen', 'Kitchen', 1], ['dining', 'Dining Room', 1],
  ['bathroom', 'Bathroom', 2], ['toilet', 'Toilet', 0], ['pooja', 'Pooja Room', 1], ['balcony', 'Balcony', 0], ['parking', 'Parking', 1], ['garden', 'Garden', 1], ['staircase', 'Staircase', 1], ['store', 'Store Room', 0], ['utility', 'Utility Room', 0]];
const CITIES = ['Jaipur', 'Delhi', 'Mumbai', 'Bengaluru', 'Hyderabad', 'Pune', 'Lucknow', 'Ahmedabad', 'Chennai', 'Kolkata', 'Indore', 'Patna'];
let ed, v3, finTimer;

function buildRoomList(sel = {}) {
  $('#roomlist').innerHTML = ROOMS.map(([k, label, def]) => {
    const s = sel[k], on = s ? s.count > 0 : !!def, cnt = s ? s.count : def || 1;
    return `<div class="room-row ${on ? 'on' : ''}" data-k="${k}"><input type="checkbox" ${on ? 'checked' : ''}><span>${label}</span><input type="number" min="1" max="8" value="${cnt}">
    <div class="dims"><input type="number" step=".5" min="3" placeholder="width ft" value="${s?.w || ''}"><input type="number" step=".5" min="3" placeholder="depth ft" value="${s?.h || ''}"></div></div>`;
  }).join('');
  $$('#roomlist .room-row').forEach(row => row.querySelector('input[type=checkbox]').onchange = e => row.classList.toggle('on', e.target.checked));
}
function readInputs() {
  const v = id => $('#' + id).value, n = id => v(id) === '' ? undefined : parseFloat(v(id));
  const shape = v('in-shape'), sp = {};
  if (shape === 'trapezium') sp.rear_width = n('sx-rear');
  if (shape === 'lshape') { sp.cut_w = n('sx-cw'); sp.cut_h = n('sx-ch'); }
  if (shape === 'custom') sp.points = v('sx-pts');
  const rooms = $$('#roomlist .room-row').filter(r => r.querySelector('input[type=checkbox]').checked).map(r => {
    const [cnt] = $$('input[type=number]', r), [w, h] = $$('.dims input', r);
    return { type: r.dataset.k, count: parseInt(cnt.value) || 1, w: parseFloat(w.value) || undefined, h: parseFloat(h.value) || undefined };
  });
  const sb = { front: n('sb-front'), rear: n('sb-rear'), side: n('sb-side') };
  return { name: v('in-name'), length: n('in-length'), width: n('in-width'), area: n('in-area'), shape, shape_params: sp, usage: v('in-usage'), road: v('in-road'), north_pos: v('in-north'),
    city: v('in-city'), budget: n('in-budget'), floors: parseInt(v('in-floors')), basement: $('#in-basement').checked, terrace: $('#in-terrace').checked, setbacks: sb, vastu_mode: S.vmode, rooms };
}
function fillInputs(i) {
  const set = (id, val) => { if (val !== undefined && val !== null) $('#' + id).value = val; };
  set('in-name', i.name); set('in-length', i.length); set('in-width', i.width); set('in-area', i.area); set('in-shape', i.shape || 'rectangle'); set('in-usage', i.usage || 'residential');
  set('in-road', i.road || 'N'); set('in-north', i.north_pos || 'up'); set('in-city', i.city || 'Jaipur'); set('in-budget', i.budget); set('in-floors', i.floors || 1);
  $('#in-basement').checked = !!i.basement; $('#in-terrace').checked = i.terrace !== false;
  set('sb-front', i.setbacks?.front); set('sb-rear', i.setbacks?.rear); set('sb-side', i.setbacks?.side);
  shapeExtra(i.shape_params || {}); S.vmode = i.vastu_mode || 'flexible'; $$('#vmode button').forEach(b => b.classList.toggle('on', b.dataset.v === S.vmode));
  const m = {}; (i.rooms || []).forEach(r => m[r.type] = r); buildRoomList(m);
}
function shapeExtra(p = {}) {
  const s = $('#in-shape').value, h = $('#shape-extra');
  h.innerHTML = s === 'trapezium' ? `<label>Rear width (ft)</label><input id="sx-rear" type="number" value="${p.rear_width || ''}" placeholder="e.g. 70% of front">`
    : s === 'lshape' ? `<div class="two"><div><label>Cut-out width (ft)</label><input id="sx-cw" type="number" value="${p.cut_w || ''}"></div><div><label>Cut-out depth (ft)</label><input id="sx-ch" type="number" value="${p.cut_h || ''}"></div></div>`
    : s === 'custom' ? `<label>Boundary points (feet, "x,y; x,y; ...")</label><textarea id="sx-pts" rows="3" placeholder="0,0; 40,0; 40,30; 20,45; 0,30">${p.points || ''}</textarea><p class="hint">Also enter approximate length and width above.</p>` : '';
}
let calcT;
function liveCalc() {
  clearTimeout(calcT); calcT = setTimeout(async () => {
    const box = $('#plotcalc'); try {
      const p = await api('/api/plot/calc', readInputs()), a = p.areas;
      box.innerHTML = `<div><span>Plot area</span><b>${a.sqft} sq ft</b></div><div><span>Square metre</span><b>${a.sqm}</b></div><div><span>Square yard</span><b>${a.sqyd}</b></div><div><span>Buildable footprint</span><b>${p.buildable.w} x ${p.buildable.h} ft</b></div><div><span>Construction area (all floors)</span><b>${p.construction_area_available} sq ft</b></div><div><span>Open space</span><b>${p.open_space} sq ft</b></div><div><span>Setbacks F/R/S</span><b>${p.setbacks.front}/${p.setbacks.rear}/${p.setbacks.side} ft</b></div>`;
    } catch (e) { box.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  }, 350);
}
/* ---------- generation ---------- */
async function generate() {
  const btn = $('#btn-gen'), msg = $('#gen-msg'); msg.textContent = ''; btn.disabled = true; btn.textContent = 'Designing...';
  try {
    S.inputs = readInputs(); const res = await api('/api/generate', S.inputs);
    S.plans = res.options; S.opt = 0; S.fi = 0; S.est = null; S.sel = null; S.dirty = true; S.v3dDirty = true;
    if (res.warnings?.length) msg.textContent = res.warnings.join(' ');
    afterPlanChange(true); toast('3 layouts generated');
  } catch (e) { msg.textContent = e.message; } finally { btn.disabled = false; btn.innerHTML = '&#10024; Generate 3 designs'; }
}
const plan = () => S.plans[S.opt];
function afterPlanChange(reset) {
  $('#empty').classList.add('hide'); ed.setPlan(plan(), S.fi, !reset); renderSubbar(); renderProps(); S.v3dDirty = true; S.est = null;
  if (S.view === '3d') ensure3D(); if (S.view === 'draw') renderDraw(); if (S.view === 'cost') renderCost(); if (S.view === 'report') renderReport(); renderVastuLive();
}
function onEdit(p, kind) {
  S.plans[S.opt] = p; S.dirty = true; S.v3dDirty = true; S.est = null; clearTimeout(finTimer);
  finTimer = setTimeout(async () => {
    try { const q = await api('/api/finalize', { plan: S.plans[S.opt] }); const si = S.opt; S.plans[si] = q; ed.plan = q; ed.render(); S.v3dDirty = true; renderSubbar(); renderProps(); renderVastuLive(); }
    catch (e) { toast(e.message, 3500); }
  }, 450);
  renderSubbar();
}
/* ---------- views ---------- */
function switchView(v) {
  S.view = v; $$('#views button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); $$('.view').forEach(x => x.classList.toggle('on', x.id === 'v-' + v));
  if (!plan()) return; renderSubbar();
  if (v === '3d') ensure3D(); if (v === 'draw') renderDraw(); if (v === 'cost') renderCost(); if (v === 'report') renderReport();
}
function renderSubbar() {
  const p = plan(), bar = $('#subbar'); if (!p) { bar.innerHTML = ''; return; }
  const opts = S.plans.map((x, i) => `<button class="chip ${i === S.opt ? 'on' : ''}" data-o="${i}">${esc(x.title)}<span class="score">Vastu ${x.vastu.score}</span></button>`).join('');
  const fl = p.floors.map((f, i) => `<button class="chip ${i === S.fi ? 'on' : ''}" data-f="${i}">${esc(f.name)}</button>`).join('');
  const errs = p.validation.filter(v => v.level === 'error').length, warns = p.validation.filter(v => v.level !== 'error').length;
  bar.innerHTML = `<span style="font-weight:700">Layout</span>${opts}<span style="margin-left:10px;font-weight:700">Floor</span>${fl}<span class="spacer"></span>
    <span class="${errs ? 'err' : 'ok'}">${errs ? errs + ' error(s)' : 'No overlaps'}</span><span class="warn">${warns ? warns + ' note(s)' : ''}</span>`;
  $$('[data-o]', bar).forEach(b => b.onclick = () => { S.opt = +b.dataset.o; S.sel = null; S.fi = Math.min(S.fi, plan().floors.length - 1); afterPlanChange(true); });
  $$('[data-f]', bar).forEach(b => b.onclick = () => { S.fi = +b.dataset.f; ed.setFloor(S.fi); renderSubbar(); if (S.view === 'draw') renderDraw(); if (S.view === '3d' && v3) { v3.showFloor(S.fi); syncFloorBtns(); } });
}
function renderLayers() {
  $('#layers2d').innerHTML = [['furniture', 'Furniture'], ['electrical', 'Electrical'], ['grid', 'Grid'], ['chain', 'Chain dims']].map(([k, l]) => `<label><input type="checkbox" data-l="${k}" ${ed.layers[k] ? 'checked' : ''}>${l}</label>`).join('');
  $$('#layers2d input').forEach(i => i.onchange = () => { ed.layers[i.dataset.l] = i.checked; ed.render(); });
}
/* ---------- 3D ---------- */
function ensure3D() {
  if (typeof THREE === 'undefined') { $('#canvas3d').innerHTML = '<p style="padding:30px">3D engine could not load (check internet access to the CDN).</p>'; return; }
  if (!v3) { v3 = new Viewer3D($('#canvas3d'), { onSelect: s => { S.sel3 = s; renderProps(); }, onFurnitureMoved: (fi, it) => { plan().floors[fi].custom_furniture = true; onEdit(plan(), 'furniture'); } }); build3DTools(); }
  if (S.v3dDirty) { v3.setPlan(plan(), !!v3.camera.userData.set); v3.camera.userData.set = true; S.v3dDirty = false; v3.plan = plan(); v3.resize(); }
  v3.resize();
}
function build3DTools() {
  const t = $('#tools3d'), p = () => plan();
  t.innerHTML = `<div class="row"><button data-m="day" class="on">Day</button><button data-m="night">Night</button></div>
  <label>Camera</label><div class="row"><button data-c="persp">Exterior</button><button data-c="interior">Interior</button><button data-c="top">Top</button><button data-c="front">Front</button><button data-c="side">Side</button><button data-c="rot">360 spin</button></div>
  <div class="row"><button data-z="in">Zoom +</button><button data-z="out">Zoom -</button></div>
  <label>Floors</label><div class="row" id="fl3d"></div>
  <label>Roof</label><div class="row"><button data-r="vis">Hide roof</button><select id="roofsel" style="padding:5px;font-size:12px"><option value="flat">Flat</option><option value="gable">Gable</option><option value="hip">Hip</option></select></div>
  <label>Wall colour</label><input type="color" id="wallcol" value="#f4efe6" style="padding:0;height:28px">
  <label>Floor material</label><select id="floormat" style="padding:5px;font-size:12px"><option value="vitrified">Vitrified tile</option><option value="wood">Wood</option><option value="marble">Marble</option><option value="kota">Kota / concrete</option></select>
  <button data-c="shot" style="margin-top:6px">&#128247; Screenshot</button><div style="font-size:11px;opacity:.7;margin-top:4px">Drag furniture to move it. Click a floor to edit its material.</div>`;
  const q = s => $(s, t);
  $$('[data-m]', t).forEach(b => b.onclick = () => { b.dataset.m === 'day' ? v3.setDay() : v3.setNight(); $$('[data-m]', t).forEach(x => x.classList.toggle('on', x === b)); });
  $$('[data-c]', t).forEach(b => b.onclick = () => { const c = b.dataset.c; if (c === 'rot') { v3.setAutoRotate(!v3.controls.autoRotate); b.classList.toggle('on', v3.controls.autoRotate); } else if (c === 'shot') exportShot(); else { v3.setView(c); if (c !== 'interior') v3.setRoofVisible(!q('[data-r]').classList.contains('on')); } });
  $$('[data-z]', t).forEach(b => b.onclick = () => v3.zoom(b.dataset.z === 'in' ? 1.25 : 1 / 1.25));
  q('[data-r]').onclick = e => { const on = e.target.classList.toggle('on'); e.target.textContent = on ? 'Show roof' : 'Hide roof'; v3.setRoofVisible(!on); };
  const style = (k, val) => { p().style = { ...(p().style || {}), [k]: val }; S.dirty = true; S.v3dDirty = false; S.est = null; v3.setPlan(p(), true); };
  q('#roofsel').onchange = e => style('roof', e.target.value); q('#wallcol').onchange = e => style('wall_color', e.target.value); q('#floormat').onchange = e => style('floor_material', e.target.value);
  const fl = q('#fl3d'); fl.innerHTML = `<button data-fl="all" class="on">All</button>` + p().floors.map((f, i) => `<button data-fl="${i}">${esc(f.name.replace(' Floor', ''))}</button>`).join('') + `<button data-fl="up">Up to...</button>`;
  $$('button', fl).forEach(b => b.onclick = () => { const k = b.dataset.fl; if (k === 'all') v3.showAll(); else if (k === 'up') v3.showUpTo(Math.max(0, S.fi)); else v3.showFloor(+k); $$('button', fl).forEach(x => x.classList.toggle('on', x === b)); });
  q('#roofsel').value = p().style?.roof || 'flat'; q('#wallcol').value = p().style?.wall_color || '#f4efe6'; q('#floormat').value = p().style?.floor_material || 'vitrified';
}
function syncFloorBtns() { $$('#fl3d button').forEach(x => x.classList.toggle('on', x.dataset.fl === String(S.fi))); }
/* ---------- save / export ---------- */
async function save() {
  if (!plan()) return toast('Generate a design first.');
  const body = { name: $('#in-name').value || 'Untitled', inputs: S.inputs || readInputs(), plans: S.plans, selected_option: S.opt };
  try {
    const r = S.pid ? await api('/api/projects/' + S.pid, body, 'PUT') : await api('/api/projects', body);
    S.pid = r.id; S.dirty = false; history.replaceState(null, '', '/studio/' + r.id); toast('Project saved');
  } catch (e) { toast(e.message, 4000); }
}
async function exportShot() { const b = await v3.screenshot(); saveBlob(b, 'smartghar-3d.png'); logDl('screenshot_3d'); }
const logDl = kind => S.pid && api('/api/log-download', { project_id: S.pid, kind }).catch(() => {});
async function exportPdf(kind) {
  if (!plan()) return toast('Generate a design first.'); toast('Preparing PDF...');
  try { const b = await api('/api/export/' + kind, { plan: plan(), inputs: S.inputs, name: $('#in-name').value, project_id: S.pid, city: $('#in-city').value, overrides: S.overrides }); saveBlob(b, `${$('#in-name').value || 'smartghar'}-${kind}.pdf`); }
  catch (e) { toast(e.message, 4000); }
}
function currentSVG() {
  if (S.view === 'draw') return Drawings.render(S.draw, plan(), S.fi);
  const f = plan().floors[S.fi]; return PlanDraw.wrapSVG(plan(), f, PlanDraw.floorMarkup(plan(), f, { ...ed.layers, dims: true }), { grid: false });
}
function svgEl(str) { const d = document.createElement('div'); d.innerHTML = str; return d.firstElementChild; }
async function doExport(e) {
  $('#exp-menu').classList.remove('open'); if (!plan()) return toast('Generate a design first.');
  if (e === 'pdf_plan') return exportPdf('plan'); if (e === 'pdf_estimate') return exportPdf('estimate');
  if (e === 'shot') { if (!v3) { switchView('3d'); await new Promise(r => setTimeout(r, 600)); } return exportShot(); }
  const str = currentSVG(), name = `${$('#in-name').value || 'plan'}-${S.view === 'draw' ? S.draw : plan().floors[S.fi].name}`.replace(/\s+/g, '_');
  if (e === 'svg') { saveBlob(new Blob([str], { type: 'image/svg+xml' }), name + '.svg'); logDl('svg'); }
  if (e === 'png') { const el = svgEl(str); el.setAttribute('width', 2400); el.setAttribute('height', Math.round(2400 * el.viewBox.baseVal.height / el.viewBox.baseVal.width)); saveBlob(await svgToPng(el, 1), name + '.png'); logDl('png'); }
  if (e === 'print') { const w = window.open('', '_blank'); w.document.write(`<html><title>${esc(name)}</title><body style="margin:0">${str.replace('<svg ', '<svg style="width:100%;height:auto" ')}<p style="font:11px sans-serif;color:#666;margin:6px 14px">${esc(SG.disclaimer)}</p></body></html>`); w.document.close(); setTimeout(() => w.print(), 400); logDl('print'); }
}
/* ---------- boot ---------- */
document.addEventListener('DOMContentLoaded', async () => {
  $('#cities').innerHTML = CITIES.map(c => `<option>${c}</option>`).join(''); buildRoomList();
  ed = new Editor2D($('#canvas2d'), { onChange: onEdit, onSelect: s => { S.sel = s; renderProps(); } });
  ed.undoBtns = () => { $('#u-undo').disabled = !ed.hist.length; $('#u-redo').disabled = !ed.fut.length; };
  renderLayers();
  $$('.ptabs button').forEach(b => b.onclick = () => { $$('.ptabs button').forEach(x => x.classList.toggle('on', x === b)); $$('.pane').forEach(p => p.classList.toggle('on', p.id === 'p-' + b.dataset.p)); });
  $$('#vmode button').forEach(b => b.onclick = () => { S.vmode = b.dataset.v; $$('#vmode button').forEach(x => x.classList.toggle('on', x === b)); });
  $('#in-shape').onchange = () => { shapeExtra(); liveCalc(); };
  $$('#p-plot input,#p-plot select,#p-plot textarea').forEach(i => i.addEventListener('input', liveCalc)); $('#p-plot').addEventListener('input', liveCalc);
  $$('#views button').forEach(b => b.onclick = () => switchView(b.dataset.v));
  $('#btn-gen').onclick = generate; $('#btn-save').onclick = save;
  $('#btn-exp').onclick = () => $('#exp-menu').classList.toggle('open'); $$('#exp-menu button').forEach(b => b.onclick = () => doExport(b.dataset.e));
  document.addEventListener('click', e => { if (!e.target.closest('.menu')) $('#exp-menu').classList.remove('open'); });
  $('#z-in').onclick = () => ed.zoom(1.25); $('#z-out').onclick = () => ed.zoom(.8); $('#z-fit').onclick = () => { ed.fit(); ed.render(); }; $('#u-undo').onclick = () => ed.undo(); $('#u-redo').onclick = () => ed.redo();
  window.addEventListener('beforeunload', e => { if (S.dirty && plan()) { e.preventDefault(); e.returnValue = ''; } });
  const defaults = { length: 30, width: 40, road: 'E', floors: 2, city: 'Jaipur', budget: 3500000, vastu_mode: 'flexible' };
  if (SG.pid) {
    try { const p = await api('/api/projects/' + SG.pid); S.inputs = p.inputs; fillInputs(p.inputs); fillInputs({ ...p.inputs, name: p.name }); S.plans = p.plans; S.opt = p.selected_option || 0; S.dirty = false; if (S.plans.length) afterPlanChange(true); }
    catch (e) { toast(e.message); }
  } else if (SG.preset) { fillInputs(SG.preset); await generate(); S.dirty = false; } else fillInputs(defaults);
  liveCalc();
});
