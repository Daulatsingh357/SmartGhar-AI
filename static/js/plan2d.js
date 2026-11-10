/* 2D plan markup (shared by editor, drawings, exports). Units: feet, origin = plot NW corner, y grows south. */
const PlanDraw = (() => {
  const EXT = 0.75, INT = 0.375;
  const inward = w => ({ N: [0, 1], S: [0, -1], W: [1, 0], E: [-1, 0] }[w]);

  function floorWalls(rooms, outline, ext = EXT, int = INT) {
    const segs = {};
    for (const r of rooms) {
      if (r.outdoor || r.type === 'terrace') continue;
      const L = [[['h', r.y], r.x, r.x + r.w], [['h', r.y + r.h], r.x, r.x + r.w], [['v', r.x], r.y, r.y + r.h], [['v', r.x + r.w], r.y, r.y + r.h]];
      for (const [[o, line], s, e] of L) (segs[o + ':' + line.toFixed(3)] ||= { o, line, iv: [] }).iv.push([s, e]);
    }
    const out = [];
    for (const k in segs) {
      const { o, line } = segs[k];
      const iv = segs[k].iv.sort((a, b) => a[0] - b[0]); const m = [];
      for (const [s, e] of iv) { if (m.length && s <= m[m.length - 1][1] + 1e-3) m[m.length - 1][1] = Math.max(m[m.length - 1][1], e); else m.push([s, e]); }
      for (const [s, e] of m) {
        const isExt = o === 'h' ? (Math.abs(line - outline.y) < 1e-3 || Math.abs(line - outline.y - outline.h) < 1e-3)
                                : (Math.abs(line - outline.x) < 1e-3 || Math.abs(line - outline.x - outline.w) < 1e-3);
        out.push({ o, line, s, e, ext: isExt, t: isExt ? ext : int });
      }
    }
    return out;
  }

  function openingPoint(r, wall, t) {
    if (wall === 'N') return [r.x + t, r.y, 'h'];
    if (wall === 'S') return [r.x + t, r.y + r.h, 'h'];
    if (wall === 'W') return [r.x, r.y + t, 'v'];
    return [r.x + r.w, r.y + t, 'v'];
  }

  function doorSVG(d, style) {
    const w = d.width, horiz = d.orient === 'h', th = (d.kind === 'main' ? style.ext : style.int) + 0.12;
    const inv = inward(d.wall), ax = horiz ? [1, 0] : [0, 1];
    const hx = d.x - ax[0] * w / 2, hy = d.y - ax[1] * w / 2;
    const C = [hx + ax[0] * w, hy + ax[1] * w], O = [hx + inv[0] * w, hy + inv[1] * w];
    const cross = (C[0] - hx) * (O[1] - hy) - (C[1] - hy) * (O[0] - hx);
    const gap = horiz ? `<rect x="${d.x - w / 2}" y="${d.y - th / 2}" width="${w}" height="${th}" fill="#fff"/>` : `<rect x="${d.x - th / 2}" y="${d.y - w / 2}" width="${th}" height="${w}" fill="#fff"/>`;
    return gap + `<line x1="${hx}" y1="${hy}" x2="${O[0]}" y2="${O[1]}" stroke="#25282d" stroke-width=".14"/>` +
      `<path d="M${C[0]} ${C[1]} A${w} ${w} 0 0 ${cross > 0 ? 1 : 0} ${O[0]} ${O[1]}" fill="none" stroke="#8a8f98" stroke-width=".07"/>`;
  }
  function windowSVG(w, style) {
    const h = w.orient === 'h', th = style.int + 0.1;
    const x = h ? w.x - w.width / 2 : w.x - th / 2, y = h ? w.y - th / 2 : w.y - w.width / 2, ww = h ? w.width : th, hh = h ? th : w.width;
    const mid = h ? `<line x1="${x}" y1="${w.y}" x2="${x + ww}" y2="${w.y}" stroke="#25282d" stroke-width=".05"/>` : `<line x1="${w.x}" y1="${y}" x2="${w.x}" y2="${y + hh}" stroke="#25282d" stroke-width=".05"/>`;
    return `<rect x="${x}" y="${y}" width="${ww}" height="${hh}" fill="#fff" stroke="#25282d" stroke-width=".08"/>` + mid;
  }
  function furnSVG(f) {
    const s = 'fill="#f8f6f0" stroke="#9a9fa8" stroke-width=".06"';
    if (f.kind === 'stairs') {
      const n = Math.max((f.risers || 12) - 1, 3); let t = `<rect x="${f.x}" y="${f.y}" width="${f.w}" height="${f.h}" fill="none" stroke="#9a9fa8" stroke-width=".08"/>`;
      for (let i = 1; i < n; i++) t += f.axis === 'x' ? `<line x1="${f.x + f.w * i / n}" y1="${f.y}" x2="${f.x + f.w * i / n}" y2="${f.y + f.h}" stroke="#9a9fa8" stroke-width=".05"/>` : `<line x1="${f.x}" y1="${f.y + f.h * i / n}" x2="${f.x + f.w}" y2="${f.y + f.h * i / n}" stroke="#9a9fa8" stroke-width=".05"/>`;
      const cx = f.x + f.w / 2;
      return t + `<line x1="${cx}" y1="${f.y + f.h - .5}" x2="${cx}" y2="${f.y + .6}" stroke="#b8923a" stroke-width=".1"/><text x="${cx}" y="${f.y + .4}" font-size=".6" text-anchor="middle" fill="#b8923a">UP</text>`;
    }
    if (['wc', 'basin', 'planter'].includes(f.kind)) return `<rect x="${f.x}" y="${f.y}" width="${f.w}" height="${f.h}" rx="${Math.min(f.w, f.h) / 2.2}" ${s}/>`;
    if (f.kind === 'bed') return `<rect x="${f.x}" y="${f.y}" width="${f.w}" height="${f.h}" ${s}/><rect x="${f.x + .2}" y="${f.y + .2}" width="${Math.max(f.w / 2 - .3, .5)}" height="${Math.min(1.2, f.h / 4)}" fill="#fff" stroke="#9a9fa8" stroke-width=".04"/><rect x="${f.x + f.w / 2 + .1}" y="${f.y + .2}" width="${Math.max(f.w / 2 - .3, .5)}" height="${Math.min(1.2, f.h / 4)}" fill="#fff" stroke="#9a9fa8" stroke-width=".04"/>`;
    return `<rect x="${f.x}" y="${f.y}" width="${f.w}" height="${f.h}" ${s}/>`;
  }
  function chain(vals, o, horiz, off) {
    const pts = [...new Set(vals.map(v => +v.toFixed(2)))].sort((a, b) => a - b);
    let t = '';
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1]; if (b - a < 1) continue; const m = (a + b) / 2;
      if (horiz) t += `<line x1="${a}" y1="${o.y - off}" x2="${b}" y2="${o.y - off}" stroke="#8a8f98" stroke-width=".06"/><line x1="${a}" y1="${o.y - off - .5}" x2="${a}" y2="${o.y - off + .5}" stroke="#8a8f98" stroke-width=".06"/><text x="${m}" y="${o.y - off - .3}" font-size=".85" text-anchor="middle" fill="#25282d">${fmtFt(b - a)}</text>`;
      else t += `<line x1="${o.x - off}" y1="${a}" x2="${o.x - off}" y2="${b}" stroke="#8a8f98" stroke-width=".06"/><line x1="${o.x - off - .5}" y1="${a}" x2="${o.x - off + .5}" y2="${a}" stroke="#8a8f98" stroke-width=".06"/><text transform="translate(${o.x - off - .3} ${m}) rotate(-90)" font-size=".85" text-anchor="middle" fill="#25282d">${fmtFt(b - a)}</text>`;
    }
    return t;
  }

  /* opts: furniture, electrical, plumbing, dims (overall), chain, labels, sel {kind,id} */
  function floorMarkup(plan, f, o = {}) {
    const st = { ext: plan.style?.wall_ext ?? EXT, int: plan.style?.wall_int ?? INT };
    const ol = f.outline; let s = '';
    const rooms = f.rooms;
    for (const r of rooms) {
      const outdoor = r.outdoor || ['garden', 'terrace', 'parking', 'balcony'].includes(r.type);
      const fill = r.type === 'garden' || r.type === 'terrace' ? '#e4eed8' : (CAT_FILL[r.cat] || '#fff');
      const sel = o.sel && o.sel.kind === 'room' && o.sel.id === r.id;
      s += `<rect data-room="${r.id}" x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" fill="${fill}" ${outdoor ? 'stroke="#9aa08a" stroke-dasharray=".5 .3" stroke-width=".1"' : ''} class="room"/>`;
      if (sel) s += `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" fill="rgba(184,146,58,.14)" stroke="#b8923a" stroke-width=".18" pointer-events="none"/>`;
    }
    if (o.furniture) for (const fu of f.furniture || []) s += `<g pointer-events="none">${furnSVG(fu)}</g>`;
    for (const w of floorWalls(rooms, ol, st.ext, st.int)) {
      const t = w.t;
      s += w.o === 'h' ? `<rect class="wall" x="${w.s - t / 2}" y="${w.line - t / 2}" width="${w.e - w.s + t}" height="${t}" fill="#25282d"/>`
                       : `<rect class="wall" x="${w.line - t / 2}" y="${w.s - t / 2}" width="${t}" height="${w.e - w.s + t}" fill="#25282d"/>`;
    }
    for (const d of f.doors || []) { const sel = o.sel && o.sel.kind === 'door' && o.sel.id === d.id; s += `<g data-door="${d.id}" class="op" ${sel ? 'filter="url(#glow)"' : ''}>${doorSVG(d, st)}<rect x="${d.x - d.width / 2}" y="${d.y - d.width / 2}" width="${d.width}" height="${d.width}" fill="transparent"/></g>`; }
    for (const w of f.windows || []) { const sel = o.sel && o.sel.kind === 'window' && o.sel.id === w.id; s += `<g data-win="${w.id}" class="op" ${sel ? 'filter="url(#glow)"' : ''}>${windowSVG(w, st)}</g>`; }
    if (o.electrical) {
      const sym = { light: '#d9a400', fan: '#3b7', switch: '#b33', socket: '#36a', exhaust: '#777', geyser: '#c60', ac: '#08a' };
      for (const e of f.electrical || []) s += `<circle cx="${e.x}" cy="${e.y}" r="${e.kind === 'fan' ? .55 : .3}" fill="${e.kind === 'fan' ? 'none' : sym[e.kind] || '#d9a400'}" stroke="${sym[e.kind] || '#d9a400'}" stroke-width=".1" pointer-events="none"/>`;
    }
    if (o.plumbing) {
      const wet = (f.furniture || []).filter(x => ['wc', 'basin', 'shower', 'sink', 'washer'].includes(x.kind));
      if (wet.length) {
        const xs = Math.min(...wet.map(w => w.x + w.w / 2)) - 1.5; const ys = wet.map(w => w.y + w.h / 2);
        s += `<line x1="${xs}" y1="${Math.min(...ys)}" x2="${xs}" y2="${Math.max(...ys)}" stroke="#2a6fb0" stroke-width=".18"/>`;
        for (const w of wet) s += `<line x1="${w.x + w.w / 2}" y1="${w.y + w.h / 2}" x2="${xs}" y2="${w.y + w.h / 2}" stroke="#2a6fb0" stroke-width=".1" stroke-dasharray=".5 .3"/><circle cx="${w.x + w.w / 2}" cy="${w.y + w.h / 2}" r=".35" fill="#2a6fb0"/>`;
        s += `<text x="${xs}" y="${Math.min(...ys) - .5}" font-size=".8" fill="#2a6fb0" text-anchor="middle">Stack</text>`;
      }
    }
    if (o.labels !== false) for (const r of rooms) {
      const small = r.w < 8, fs = small ? .85 : 1.15;
      s += `<g pointer-events="none"><text x="${r.x + r.w / 2}" y="${r.y + r.h / 2 - .1}" font-size="${fs}" font-weight="700" text-anchor="middle" fill="#25282d" font-family="Inter,sans-serif">${esc(small && r.name.length > 12 ? r.name.slice(0, 11) + '.' : r.name)}</text><text x="${r.x + r.w / 2}" y="${r.y + r.h / 2 + fs}" font-size="${fs * .8}" text-anchor="middle" fill="#7d838c" font-family="Inter,sans-serif">${fmtFt(r.w)} x ${fmtFt(r.h)}</text></g>`;
    }
    if (o.dims !== false) {
      s += `<g pointer-events="none" font-family="Inter,sans-serif">`;
      if (o.chain) {
        const top = rooms.filter(r => !r.outdoor && Math.abs(r.y - ol.y) < .01), left = rooms.filter(r => !r.outdoor && Math.abs(r.x - ol.x) < .01);
        s += chain(top.flatMap(r => [r.x, r.x + r.w]), ol, true, 2.4) + chain(left.flatMap(r => [r.y, r.y + r.h]), ol, false, 2.4);
      }
      s += chain([ol.x, ol.x + ol.w], ol, true, 4.6) + chain([ol.y, ol.y + ol.h], ol, false, 4.6) + '</g>';
    }
    return s;
  }

  function wrapSVG(plan, f, inner, o = {}) {
    const pl = plan.plot, pad = 9, ex = pl.ex, ny = pl.ny;
    const vb = o.vb || { x: -pad, y: -pad, w: ex + 2 * pad, h: ny + 2 * pad + 4 };
    const poly = pl.polygon.map(p => p.join(',')).join(' ');
    const b = plan.buildable;
    let g = `<defs><pattern id="g1" width="1" height="1" patternUnits="userSpaceOnUse"><path d="M1 0H0V1" fill="none" stroke="#ece8de" stroke-width=".03"/></pattern><pattern id="g5" width="5" height="5" patternUnits="userSpaceOnUse"><rect width="5" height="5" fill="url(#g1)"/><path d="M5 0H0V5" fill="none" stroke="#ddd7c8" stroke-width=".06"/></pattern><filter id="glow"><feDropShadow dx="0" dy="0" stdDeviation=".25" flood-color="#b8923a"/></filter></defs>`;
    if (o.grid) g += `<rect x="${vb.x}" y="${vb.y}" width="${vb.w}" height="${vb.h}" fill="url(#g5)"/>`;
    else g += `<rect x="${vb.x}" y="${vb.y}" width="${vb.w}" height="${vb.h}" fill="#fff"/>`;
    g += `<polygon points="${poly}" fill="rgba(243,246,236,.55)" stroke="#25282d" stroke-width=".18"/><rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" fill="none" stroke="#b8923a" stroke-width=".1" stroke-dasharray=".8 .5"/>`;
    g += inner;
    // north arrow + scale bar
    const nx = vb.x + vb.w - 5, nyy = vb.y + 5;
    g += `<g font-family="Inter,sans-serif" pointer-events="none"><circle cx="${nx}" cy="${nyy}" r="2.2" fill="#fff" stroke="#25282d" stroke-width=".12"/><path d="M${nx} ${nyy - 2} L${nx - .8} ${nyy + 1.5} L${nx} ${nyy + .8} L${nx + .8} ${nyy + 1.5}Z" fill="#25282d"/><text x="${nx}" y="${nyy - 2.9}" font-size="1.4" font-weight="700" text-anchor="middle">N</text>`;
    const sx = vb.x + 2, sy = vb.y + vb.h - 2.2;
    g += `<rect x="${sx}" y="${sy}" width="5" height=".5" fill="#25282d"/><rect x="${sx + 5}" y="${sy}" width="5" height=".5" fill="#fff" stroke="#25282d" stroke-width=".06"/><text x="${sx}" y="${sy + 1.6}" font-size=".9">0</text><text x="${sx + 10}" y="${sy + 1.6}" font-size=".9" text-anchor="middle">10 ft</text>`;
    g += `<text x="${vb.x + 2}" y="${vb.y + 2.4}" font-size="1.3" font-weight="700" fill="#25282d">${esc(o.title || f?.name || '')}</text><text x="${vb.x + 2}" y="${vb.y + 4}" font-size=".9" fill="#7d838c">${esc(o.subtitle || plan.title)}</text></g>`;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb.x} ${vb.y} ${vb.w} ${vb.h}" preserveAspectRatio="xMidYMid meet">${g}</svg>`;
  }
  return { floorWalls, openingPoint, floorMarkup, wrapSVG, inward, EXT, INT };
})();
