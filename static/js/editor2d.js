/* Interactive 2D editor built on PlanDraw. Emits onChange(plan) after every committed edit. */
class Editor2D {
  constructor(host, { onChange, onSelect }) {
    this.host = host; this.onChange = onChange; this.onSelect = onSelect;
    this.plan = null; this.fi = 0; this.sel = null; this.hist = []; this.fut = [];
    this.layers = { furniture: true, electrical: false, grid: true, chain: false };
    this.vb = null; this.drag = null;
    host.addEventListener('pointerdown', e => this.down(e));
    window.addEventListener('pointermove', e => this.move(e));
    window.addEventListener('pointerup', e => this.up(e));
    host.addEventListener('wheel', e => this.wheel(e), { passive: false });
    window.addEventListener('keydown', e => this.key(e));
  }
  get floor() { return this.plan?.floors[this.fi]; }
  setPlan(plan, fi = 0, keepView = false) {
    this.plan = plan; this.fi = Math.min(fi, plan.floors.length - 1);
    if (!keepView || !this.vb) this.fit(); this.render();
  }
  setFloor(i) { this.fi = i; this.sel = null; this.fit(); this.render(); this.onSelect?.(null); }
  fit() {
    const p = this.plan.plot, pad = 9;
    this.vb = { x: -pad, y: -pad, w: p.ex + 2 * pad, h: p.ny + 2 * pad + 4 }; this.base = { ...this.vb };
  }
  render() {
    if (!this.plan) return;
    const f = this.floor;
    let inner = PlanDraw.floorMarkup(this.plan, f, { ...this.layers, sel: this.sel, dims: true });
    inner += this.handles();
    this.host.innerHTML = PlanDraw.wrapSVG(this.plan, f, inner, { grid: this.layers.grid, vb: this.vb });
    this.svg = this.host.firstElementChild;
    $$('.room', this.svg).forEach(r => r.style.cursor = 'grab');
    $$('.op', this.svg).forEach(r => r.style.cursor = 'ew-resize');
    this.undoBtns?.();
  }
  svgToPlan(e) {
    const pt = this.svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(this.svg.getScreenCTM().inverse()); return { x: p.x, y: p.y };
  }
  handles() {
    if (!this.sel || this.sel.kind !== 'room') return '';
    const r = this.floor.rooms.find(x => x.id === this.sel.id); if (!r) return '';
    const H = (side, x, y, w, h, cur) => `<rect data-edge="${side}" x="${x}" y="${y}" width="${w}" height="${h}" fill="#b8923a" stroke="#fff" stroke-width=".08" rx=".2" style="cursor:${cur}"/>`;
    return H('N', r.x + r.w / 2 - 1, r.y - .35, 2, .7, 'ns-resize') + H('S', r.x + r.w / 2 - 1, r.y + r.h - .35, 2, .7, 'ns-resize') +
           H('W', r.x - .35, r.y + r.h / 2 - 1, .7, 2, 'ew-resize') + H('E', r.x + r.w - .35, r.y + r.h / 2 - 1, .7, 2, 'ew-resize');
  }
  select(sel) { this.sel = sel; this.render(); this.onSelect?.(sel); }
  /* ---------- history ---------- */
  push() { this.hist.push(JSON.stringify(this.plan)); if (this.hist.length > 80) this.hist.shift(); this.fut = []; }
  undo() { if (!this.hist.length) return; this.fut.push(JSON.stringify(this.plan)); this.plan = JSON.parse(this.hist.pop()); this.afterHist(); }
  redo() { if (!this.fut.length) return; this.hist.push(JSON.stringify(this.plan)); this.plan = JSON.parse(this.fut.pop()); this.afterHist(); }
  afterHist() { this.fi = Math.min(this.fi, this.plan.floors.length - 1); this.render(); this.onChange(this.plan, 'history'); this.onSelect?.(this.sel); }
  commit(kind = 'edit') { this.render(); this.onChange(this.plan, kind); }
  key(e) {
    if (!$('#v-2d').classList.contains('on') || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? this.redo() : this.undo(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); this.redo(); }
    else if ((e.key === 'Delete' || e.key === 'Backspace') && this.sel && this.sel.kind !== 'room') this.deleteSel();
    else if (e.key === 'Escape') this.select(null);
  }
  /* ---------- zoom / pan ---------- */
  zoom(k, cx, cy) {
    const v = this.vb; cx ??= v.x + v.w / 2; cy ??= v.y + v.h / 2;
    const nw = Math.min(Math.max(v.w / k, 12), this.base.w * 3), s = nw / v.w;
    this.vb = { x: cx - (cx - v.x) * s, y: cy - (cy - v.y) * s, w: nw, h: v.h * s }; this.render();
  }
  wheel(e) { e.preventDefault(); const p = this.svgToPlan(e); this.zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, p.x, p.y); }
  /* ---------- pointer interaction ---------- */
  down(e) {
    if (!this.svg || e.button === 2) return;
    const t = e.target, p = this.svgToPlan(e);
    const edge = t.closest?.('[data-edge]'), door = t.closest?.('[data-door]'), win = t.closest?.('[data-win]'), room = t.closest?.('[data-room]');
    if (edge && this.sel?.kind === 'room') { this.push(); this.drag = { type: 'edge', side: edge.dataset.edge, id: this.sel.id, snapshot: JSON.stringify(this.plan) }; }
    else if (door || win) {
      const id = (door || win).dataset.door || (door || win).dataset.win, kind = door ? 'door' : 'window';
      this.sel = { kind, id }; this.push(); this.drag = { type: 'op', kind, id, moved: false }; this.render(); this.onSelect?.(this.sel);
    } else if (room && !e.spaceKey) {
      const id = room.dataset.room; if (!(this.sel?.id === id)) { this.sel = { kind: 'room', id }; this.render(); this.onSelect?.(this.sel); }
      const r = this.floor.rooms.find(x => x.id === id);
      this.drag = { type: 'room', id, start: p, ox: r.x, oy: r.y, moved: false };
    } else { if (this.sel) { this.sel = null; this.render(); this.onSelect?.(null); } this.drag = { type: 'pan', sx: e.clientX, sy: e.clientY, vb: { ...this.vb } }; }
    if (this.drag) e.preventDefault();
  }
  move(e) {
    const d = this.drag; if (!d) return;
    if (d.type === 'pan') {
      const k = this.vb.w / this.svg.clientWidth; this.vb.x = d.vb.x - (e.clientX - d.sx) * k; this.vb.y = d.vb.y - (e.clientY - d.sy) * k;
      this.svg.setAttribute('viewBox', `${this.vb.x} ${this.vb.y} ${this.vb.w} ${this.vb.h}`); return;
    }
    const p = this.svgToPlan(e);
    if (d.type === 'room') {
      if (!d.moved && Math.hypot(p.x - d.start.x, p.y - d.start.y) < .6) return;
      if (!d.moved) { d.moved = true; this.push(); }
      const r = this.floor.rooms.find(x => x.id === d.id);
      d.nx = snap(d.ox + p.x - d.start.x); d.ny = snap(d.oy + p.y - d.start.y); d.px = p;
      this.ghost(r, d.nx, d.ny);
    } else if (d.type === 'edge') {
      this.plan = JSON.parse(d.snapshot); const f = this.floor, r = f.rooms.find(x => x.id === d.id);
      const pos = snap(d.side === 'W' || d.side === 'E' ? p.x : p.y);
      d.err = this.moveEdge(f, r, d.side, pos); d.pos = pos; this.render();
    } else if (d.type === 'op') {
      const f = this.floor, o = (d.kind === 'door' ? f.doors : f.windows).find(x => x.id === d.id), r = f.rooms.find(x => x.id === o.room);
      const t = o.wall === 'N' || o.wall === 'S' ? p.x - r.x : p.y - r.y, len = o.wall === 'N' || o.wall === 'S' ? r.w : r.h;
      o.t = r1(Math.min(Math.max(snap(t, .25), o.width / 2 + .6), len - o.width / 2 - .6)); this.refreshOpenings(f); d.moved = true; this.render();
    }
  }
  ghost(r, x, y) {
    $('#ghost', this.svg)?.remove();
    const g = document.createElementNS(NS, 'rect'); g.id = 'ghost';
    Object.entries({ x, y, width: r.w, height: r.h, fill: 'rgba(184,146,58,.25)', stroke: '#b8923a', 'stroke-width': .2, 'stroke-dasharray': '.6 .4', 'pointer-events': 'none' }).forEach(([k, v]) => g.setAttribute(k, v));
    this.svg.appendChild(g);
  }
  up(e) {
    const d = this.drag; this.drag = null; if (!d) return;
    if (d.type === 'room') {
      if (!d.moved) return;
      const f = this.floor, r = f.rooms.find(x => x.id === d.id);
      const tgt = f.rooms.find(o => o.id !== r.id && d.px.x >= o.x && d.px.x <= o.x + o.w && d.px.y >= o.y && d.px.y <= o.y + o.h);
      if (tgt) { this.swap(r, tgt); toast(`Swapped ${r.name} and ${tgt.name}`); this.sel = { kind: 'room', id: tgt.id }; this.commit('swap'); return; }
      const trial = { ...r, x: d.nx, y: d.ny }, b = this.plan.buildable, pl = this.plan.plot;
      const inside = trial.type === 'garden' || (trial.x >= b.x - .01 && trial.y >= b.y - .01 && trial.x + trial.w <= b.x + b.w + .01 && trial.y + trial.h <= b.y + b.h + .01);
      const clash = f.rooms.some(o => o.id !== r.id && ov(trial, o) > .05);
      if (inside && !clash) { r.x = d.nx; r.y = d.ny; this.refreshOpenings(f); this.floorCustom(f, false); this.commit('move'); }
      else { this.hist.pop(); this.render(); toast(clash ? 'Rooms cannot overlap - drop on another room to swap them.' : 'Room must stay inside the buildable area.'); }
    } else if (d.type === 'edge') {
      if (d.err) { this.plan = JSON.parse(d.snapshot); this.hist.pop(); this.render(); toast(d.err, 3600); }
      else if (JSON.stringify(this.plan) === d.snapshot) this.hist.pop(); else { this.floorCustom(this.floor, false); this.commit('resize'); }
    } else if (d.type === 'op') { if (d.moved) this.commit('opening'); else this.hist.pop(); }
  }
  floorCustom(f, v) { f.custom_furniture = v; }
  swap(a, b) { for (const k of ['type', 'name', 'cat', 'target_area']) { const t = a[k]; a[k] = b[k]; b[k] = t; } this.floorCustom(this.floor, false); }
  /* ---------- geometry edits ---------- */
  moveEdge(f, room, side, pos, minSize = 3) {
    const vert = side === 'W' || side === 'E', o = f.outline, EPS = .011;
    const line = side === 'W' ? room.x : side === 'E' ? room.x + room.w : side === 'N' ? room.y : room.y + room.h;
    if (Math.abs(pos - line) < .01) return null;
    const onOutline = vert ? (Math.abs(line - o.x) < EPS || Math.abs(line - o.x - o.w) < EPS) : (Math.abs(line - o.y) < EPS || Math.abs(line - o.y - o.h) < EPS);
    if (onOutline) return 'This is an exterior wall - resize the plot or buildable area instead.';
    const edges = [];
    for (const r of f.rooms) {
      if (vert) { if (Math.abs(r.x - line) < EPS) edges.push({ r, s: 'W', a: r.y, b: r.y + r.h }); if (Math.abs(r.x + r.w - line) < EPS) edges.push({ r, s: 'E', a: r.y, b: r.y + r.h }); }
      else { if (Math.abs(r.y - line) < EPS) edges.push({ r, s: 'N', a: r.x, b: r.x + r.w }); if (Math.abs(r.y + r.h - line) < EPS) edges.push({ r, s: 'S', a: r.x, b: r.x + r.w }); }
    }
    const start = edges.find(e => e.r === room && e.s === side); let A = start.a, B = start.b, set = new Set([start]), grew = true;
    while (grew) { grew = false; for (const e of edges) if (!set.has(e) && e.a < B - EPS && e.b > A + EPS) { set.add(e); A = Math.min(A, e.a); B = Math.max(B, e.b); grew = true; } }
    for (const e of set) { const r = e.r; if (vert) { if (e.s === 'W') { r.w += r.x - pos; r.x = pos; } else r.w = pos - r.x; } else { if (e.s === 'N') { r.h += r.y - pos; r.y = pos; } else r.h = pos - r.y; } }
    for (const e of set) {
      const r = e.r, min = ['toilet', 'store', 'utility', 'pooja', 'bathroom', 'balcony'].includes(r.type) ? 2.5 : minSize;
      if (Math.min(r.w, r.h) < min - .01) return `${r.name} would become too small (min ${min} ft).`;
    }
    for (const e of set) for (const o2 of f.rooms) if (!set.has([...set].find(z => z.r === o2)) && o2 !== e.r && ov(e.r, o2) > .05) return `That would overlap ${o2.name}.`;
    for (const e of set) { e.r.w = r1(e.r.w * 4) / 4; e.r.h = r1(e.r.h * 4) / 4; }
    this.refreshOpenings(f); return null;
  }
  refreshOpenings(f) {
    const rooms = Object.fromEntries(f.rooms.map(r => [r.id, r]));
    for (const arr of [f.doors || [], f.windows || []]) for (const o of arr) {
      const r = rooms[o.room]; if (!r) continue;
      const len = o.wall === 'N' || o.wall === 'S' ? r.w : r.h;
      o.t = r1(Math.min(Math.max(o.t, o.width / 2 + .3), Math.max(len - o.width / 2 - .3, o.width / 2 + .3)));
      [o.x, o.y, o.orient] = PlanDraw.openingPoint(r, o.wall, o.t);
    }
  }
  setRoomSize(id, w, h) {
    const f = this.floor, find = () => f.rooms.find(x => x.id === id); this.push(); const snap0 = JSON.stringify(this.plan);
    const isExt = e => e && e.startsWith('This is an exterior');
    let err = null, r = find();
    if (w && Math.abs(w - r.w) > .01) { err = this.moveEdge(f, r, 'E', snap(r.x + w)); if (isExt(err)) { r = find(); err = this.moveEdge(f, r, 'W', snap(r.x + r.w - w)); } }
    r = find();
    if (!err && h && Math.abs(h - r.h) > .01) { err = this.moveEdge(f, r, 'S', snap(r.y + h)); if (isExt(err)) { r = find(); err = this.moveEdge(f, r, 'N', snap(r.y + r.h - h)); } }
    if (err) { this.plan = JSON.parse(snap0); this.hist.pop(); this.render(); toast(err, 3600); return false; }
    this.floorCustom(this.floor, false); this.commit('resize'); return true;
  }
  addOpening(kind, roomId, wall) {
    const f = this.floor, r = f.rooms.find(x => x.id === roomId); this.push();
    const arr = kind === 'door' ? (f.doors ||= []) : (f.windows ||= []), len = wall === 'N' || wall === 'S' ? r.w : r.h;
    const width = kind === 'door' ? 3 : Math.min(3.5, Math.max(len - 2, 1.5)); if (len < width + 1.2) { this.hist.pop(); return toast('Wall is too short for that opening.'); }
    const id = (kind === 'door' ? 'd' : 'w') + Date.now().toString(36);
    const o = { id, room: roomId, wall, t: r1(len / 2), width, kind: 'internal' };
    if (kind === 'window') { o.sill = 3; o.head = 7; delete o.kind; }
    arr.push(o); this.refreshOpenings(f); this.sel = { kind, id }; this.commit('opening'); this.onSelect?.(this.sel);
  }
  deleteSel() {
    if (!this.sel || this.sel.kind === 'room') return; const f = this.floor; this.push();
    const key = this.sel.kind === 'door' ? 'doors' : 'windows'; f[key] = f[key].filter(x => x.id !== this.sel.id); this.sel = null; this.commit('opening'); this.onSelect?.(null);
  }
  update(kind, id, patch) {
    const f = this.floor, o = kind === 'room' ? f.rooms.find(x => x.id === id) : (kind === 'door' ? f.doors : f.windows).find(x => x.id === id); if (!o) return;
    this.push(); Object.assign(o, patch); if (kind !== 'room') this.refreshOpenings(f); if (kind === 'room' && patch.type) this.floorCustom(f, false); this.commit(kind);
  }
}
function ov(a, b) {
  const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x), oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return ox > 1e-3 && oy > 1e-3 ? ox * oy : 0;
}
