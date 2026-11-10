/* Architectural drawing set rendered as SVG from plan geometry. */
const Drawings = (() => {
  const LIST = [
    ['plan', '2D Floor Plan', true], ['dims', 'Dimension Plan', true], ['furn', 'Furniture Layout', true],
    ['elec', 'Electrical Layout', true], ['plumb', 'Plumbing Layout', true], ['front', 'Front Elevation'], ['side', 'Side Elevation'],
    ['section', 'Section Drawing'], ['roof', 'Roof Plan'], ['site', 'Site Plan']];
  const levels = p => p.floors.filter(f => f.kind !== 'terrace');
  const frame = (w, h, title, sub, inner) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" font-family="Inter,sans-serif"><rect width="${w}" height="${h}" fill="#fff"/><text x="3" y="4" font-size="2" font-weight="700" fill="#25282d">${esc(title)}</text><text x="3" y="6.4" font-size="1.2" fill="#7d838c">${esc(sub)}</text>${inner}</svg>`;

  function elevation(p, side) {
    const lv = levels(p), o = p.floors[0].outline, span = side === 'front' ? o.w : o.h, par = p.style?.parapet_ft ?? 3;
    const top = Math.max(...lv.map(f => f.elevation + f.height)), bot = Math.min(...lv.map(f => f.elevation));
    const W = span + 22, H = top - bot + par + 14, gy = e => H - 6 + bot - e + (-bot) * 0; // y for elevation e (ground=0 -> H-6+bot)
    const Y = e => 8 + (top + par - e), X = x => 6 + x;
    let s = `<rect x="${X(0)}" y="${Y(top + par)}" width="${span}" height="${top - bot + par}" fill="${p.style?.wall_color || '#f4efe6'}" stroke="#25282d" stroke-width=".18"/>`;
    for (const f of lv) {
      s += `<line x1="${X(0)}" x2="${X(span)}" y1="${Y(f.elevation)}" y2="${Y(f.elevation)}" stroke="#8a8f98" stroke-width=".08"/>`;
      for (const w of f.windows || []) {
        const ok = side === 'front' ? (w.orient === 'h' && Math.abs(w.y - o.y - o.h) < .6) : (w.orient === 'v' && Math.abs(w.x - o.x - o.w) < .6);
        if (!ok || f.kind === 'basement') continue; const pos = side === 'front' ? w.x - o.x : w.y - o.y;
        s += `<rect x="${X(pos - w.width / 2)}" y="${Y(f.elevation + w.head)}" width="${w.width}" height="${w.head - w.sill}" fill="#cfe3f1" stroke="#25282d" stroke-width=".1"/><line x1="${X(pos)}" x2="${X(pos)}" y1="${Y(f.elevation + w.head)}" y2="${Y(f.elevation + w.sill)}" stroke="#25282d" stroke-width=".06"/>`;
      }
      for (const d of f.doors || []) {
        if (d.kind !== 'main') continue;
        const ok = side === 'front' ? (d.orient === 'h' && Math.abs(d.y - o.y - o.h) < .6) : (d.orient === 'v' && Math.abs(d.x - o.x - o.w) < .6); if (!ok) continue;
        const pos = side === 'front' ? d.x - o.x : d.y - o.y;
        s += `<rect x="${X(pos - d.width / 2)}" y="${Y(f.elevation + 7)}" width="${d.width}" height="7" fill="#8a5a2b" stroke="#25282d" stroke-width=".1"/>`;
      }
      s += `<text x="${X(span) + 1.5}" y="${Y(f.elevation) - .4}" font-size=".95" fill="#25282d">${esc(f.name)} +${f.elevation.toFixed(1)}'</text>`;
    }
    s += `<rect x="${X(-.6)}" y="${Y(top + par)}" width="${span + 1.2}" height=".6" fill="#25282d"/><line x1="${X(-4)}" x2="${X(span + 4)}" y1="${Y(0)}" y2="${Y(0)}" stroke="#25282d" stroke-width=".3"/><text x="${X(span) + 1.5}" y="${Y(top + par) + .9}" font-size=".95">Parapet +${(top + par).toFixed(1)}'</text>`;
    s += `<text x="${X(span / 2)}" y="${H - 1.5}" font-size="1.3" font-weight="700" text-anchor="middle">${side === 'front' ? 'FRONT ELEVATION (south face)' : 'SIDE ELEVATION (east face)'}</text>`;
    s += `<line x1="${X(0)}" x2="${X(span)}" y1="${H - 4}" y2="${H - 4}" stroke="#8a8f98" stroke-width=".06"/><text x="${X(span / 2)}" y="${H - 4.4}" font-size=".9" text-anchor="middle">${fmtFt(span)}</text>`;
    return frame(W, H, side === 'front' ? 'Front Elevation' : 'Side Elevation', p.title, s);
  }
  function section(p) {
    const lv = levels(p), o = p.floors[0].outline, par = p.style?.parapet_ft ?? 3;
    const top = Math.max(...lv.map(f => f.elevation + f.height)), bot = Math.min(...lv.map(f => f.elevation));
    const W = o.h + 22, H = top - bot + par + 14, Y = e => 8 + (top + par - e), X = x => 6 + x; let s = '';
    for (const f of lv) {
      s += `<rect x="${X(-.75)}" y="${Y(f.elevation)}" width="${o.h + 1.5}" height=".45" fill="#25282d"/>`;
      for (const r of f.rooms) {
        if (r.outdoor || ['garden', 'headroom'].includes(r.type) || r.x > o.x + .1) continue;
        s += `<rect x="${X(r.y - o.y)}" y="${Y(f.elevation + f.height)}" width="${r.h}" height="${f.height}" fill="#fbf9f3" stroke="#8a8f98" stroke-width=".08"/>`;
        if (r.h > 5) s += `<text x="${X(r.y - o.y + r.h / 2)}" y="${Y(f.elevation + f.height / 2)}" font-size=".85" text-anchor="middle" fill="#7d838c">${esc(r.name)}</text>`;
      }
      s += `<text x="${X(o.h) + 2}" y="${Y(f.elevation)}" font-size=".95">${esc(f.name)} +${f.elevation.toFixed(1)}'</text>`;
    }
    s += `<rect x="${X(-.75)}" y="${Y(top + .45)}" width="${o.h + 1.5}" height=".45" fill="#25282d"/><rect x="${X(-.75)}" y="${Y(top + par)}" width=".75" height="${par}" fill="#25282d"/><rect x="${X(o.h)}" y="${Y(top + par)}" width=".75" height="${par}" fill="#25282d"/>`;
    s += `<line x1="${X(-4)}" x2="${X(o.h + 4)}" y1="${Y(0)}" y2="${Y(0)}" stroke="#25282d" stroke-width=".3"/><text x="${X(o.h / 2)}" y="${H - 1.5}" font-size="1.3" font-weight="700" text-anchor="middle">SECTION A-A (north-south cut)</text>`;
    return frame(W, H, 'Section Drawing', p.title, s);
  }
  function roof(p) {
    const o = p.floors[0].outline, st = p.style || {}, f = p.floors[0];
    let inner = `<rect x="${o.x}" y="${o.y}" width="${o.w}" height="${o.h}" fill="#e8e4da" stroke="#25282d" stroke-width=".4"/><rect x="${o.x + .75}" y="${o.y + .75}" width="${o.w - 1.5}" height="${o.h - 1.5}" fill="none" stroke="#25282d" stroke-width=".1"/>`;
    if ((st.roof || 'flat') === 'flat') {
      for (const k of [.25, .5, .75]) inner += `<line x1="${o.x + o.w * k}" y1="${o.y + o.h * .3}" x2="${o.x + o.w * k}" y2="${o.y + o.h * .8}" stroke="#8a8f98" stroke-width=".1" stroke-dasharray=".6 .4"/>`;
      inner += `<circle cx="${o.x + o.w - 2}" cy="${o.y + o.h - 2}" r=".7" fill="#2a6fb0"/><text x="${o.x + o.w - 3}" y="${o.y + o.h - 3}" font-size=".9" text-anchor="end" fill="#7d838c">Rainwater outlet - slope 1:100</text>`;
    } else inner += `<line x1="${o.x + o.w / 2}" y1="${o.y}" x2="${o.x + o.w / 2}" y2="${o.y + o.h}" stroke="#25282d" stroke-width=".2"/><text x="${o.x + o.w / 2 + .5}" y="${o.y + 1.5}" font-size=".9">Ridge</text>`;
    const sh = p.floors.find(x => x.rooms.some(r => r.type === 'headroom'))?.rooms.find(r => r.type === 'headroom');
    if (sh) inner += `<rect x="${sh.x}" y="${sh.y}" width="${sh.w}" height="${sh.h}" fill="#d6d1c4" stroke="#25282d" stroke-width=".25"/><text x="${sh.x + sh.w / 2}" y="${sh.y + sh.h / 2}" font-size=".9" text-anchor="middle">Stair headroom</text>`;
    inner += `<text x="${o.x + o.w / 2}" y="${o.y + o.h / 2}" font-size="1.4" font-weight="700" text-anchor="middle">ROOF PLAN</text>`;
    return PlanDraw.wrapSVG(p, f, inner, { grid: false, title: 'Roof Plan' });
  }
  function site(p) {
    const pl = p.plot, f = p.floors[0], rd = pl.road, ex = pl.ex, ny = pl.ny, rw = 8;
    const R = { N: [0, -rw - 1, ex, rw], S: [0, ny + 1, ex, rw], W: [-rw - 1, 0, rw, ny], E: [ex + 1, 0, rw, ny] }[rd];
    let inner = `<rect x="${R[0]}" y="${R[1]}" width="${R[2]}" height="${R[3]}" fill="#4b4f57"/><text x="${R[0] + R[2] / 2}" y="${R[1] + R[3] / 2 + .5}" font-size="1.4" fill="#fff" text-anchor="middle" font-weight="700">ROAD</text>`;
    for (const r of f.rooms) inner += `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" fill="${r.type === 'garden' ? '#dfe9d2' : '#d9d5ca'}" stroke="#8a8f98" stroke-width=".08"/>`;
    const s = pl.setbacks, a = pl.areas;
    inner += `<text x="${p.buildable.x + .6}" y="${p.buildable.y - .6}" font-size=".95" fill="#7a5c14">Setbacks: front ${s.front}' rear ${s.rear}' side ${s.side}'</text><text x="0" y="${ny + 3}" font-size="1.1" font-weight="700">Plot ${a.sqft} sq ft | ${a.sqm} sq m | ${a.sqyd} sq yd</text>`;
    inner += `<g font-size=".9" fill="#25282d" text-anchor="middle"><text x="${ex / 2}" y="${ny + 1.2}">${fmtFt(ex)}</text><text transform="translate(${ex + 1.2} ${ny / 2}) rotate(90)">${fmtFt(ny)}</text></g>`;
    const vb = { x: -rw - 11, y: -rw - 11, w: ex + 2 * rw + 22, h: ny + 2 * rw + 24 };
    return PlanDraw.wrapSVG(p, f, inner, { grid: false, title: 'Site Plan', vb });
  }
  function render(key, p, fi) {
    const f = p.floors[Math.min(fi, p.floors.length - 1)];
    const opt = { plan: { furniture: false, dims: true }, dims: { furniture: false, chain: true }, furn: { furniture: true }, elec: { electrical: true }, plumb: { plumbing: true, furniture: true } }[key];
    if (opt) return PlanDraw.wrapSVG(p, f, PlanDraw.floorMarkup(p, f, opt), { title: `${f.name} - ${LIST.find(x => x[0] === key)[1]}` });
    return { front: () => elevation(p, 'front'), side: () => elevation(p, 'side'), section: () => section(p), roof: () => roof(p), site: () => site(p) }[key]();
  }
  return { LIST, render };
})();
