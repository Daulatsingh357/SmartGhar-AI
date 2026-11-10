/* Three.js viewer: builds real 3D geometry from the 2D plan (feet; plan x -> X, plan y -> Z, elevation -> Y). */
class Viewer3D {
  constructor(host, cb = {}) {
    this.host = host; this.cb = cb; this.texCache = {}; this.night = false; this.showRoof = true; this.isolate = null; this.plan = null;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.shadowMap.enabled = true; this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); host.appendChild(this.renderer.domElement);
    this.scene = new THREE.Scene(); this.camera = new THREE.PerspectiveCamera(42, 1, 0.5, 4000);
    this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.dampingFactor = .08; this.controls.maxPolarAngle = Math.PI / 2 - .01;
    this.hemi = new THREE.HemisphereLight(0xffffff, 0x8a8f7a, .75); this.scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight(0xfff3dc, .95); this.sun.castShadow = true; this.sun.shadow.mapSize.set(2048, 2048); this.scene.add(this.sun, this.sun.target);
    this.root = new THREE.Group(); this.scene.add(this.root);
    this.ray = new THREE.Raycaster(); this.mouse = new THREE.Vector2();
    const el = this.renderer.domElement;
    el.addEventListener('pointerdown', e => this.pdown(e)); window.addEventListener('pointermove', e => this.pmove(e)); window.addEventListener('pointerup', () => this.pup());
    new ResizeObserver(() => this.resize()).observe(host); this.resize(); this.setDay();
    const loop = () => { requestAnimationFrame(loop); if (!host.offsetParent) return; this.controls.update(); this.renderer.render(this.scene, this.camera); }; loop();
  }
  resize() { const w = this.host.clientWidth, h = this.host.clientHeight; if (!w || !h) return; this.renderer.setSize(w, h); this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); }
  /* ---------- procedural textures ---------- */
  tex(kind, color = '#ffffff', rep = [1, 1]) {
    const key = kind + color + rep; if (this.texCache[key]) return this.texCache[key];
    const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d'); g.fillStyle = color; g.fillRect(0, 0, 256, 256);
    const noise = (n, a) => { for (let i = 0; i < n; i++) { g.fillStyle = `rgba(${Math.random() < .5 ? '0,0,0' : '255,255,255'},${Math.random() * a})`; g.fillRect(Math.random() * 256, Math.random() * 256, 2, 2); } };
    if (kind === 'plaster') noise(3500, .07);
    else if (kind === 'brick') { g.strokeStyle = 'rgba(0,0,0,.25)'; g.lineWidth = 2; for (let y = 0; y < 256; y += 32) { g.beginPath(); g.moveTo(0, y); g.lineTo(256, y); g.stroke(); for (let x = (y / 32) % 2 ? 0 : 32; x < 256; x += 64) { g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + 32); g.stroke(); } } noise(1500, .12); }
    else if (kind === 'tile') { g.strokeStyle = 'rgba(0,0,0,.28)'; g.lineWidth = 3; g.strokeRect(0, 0, 256, 256); g.beginPath(); g.moveTo(128, 0); g.lineTo(128, 256); g.moveTo(0, 128); g.lineTo(256, 128); g.stroke(); noise(1200, .05); }
    else if (kind === 'wood') { for (let y = 0; y < 256; y += 32) { g.fillStyle = `rgba(0,0,0,${Math.random() * .12})`; g.fillRect(0, y, 256, 32); g.strokeStyle = 'rgba(0,0,0,.3)'; g.strokeRect(0, y, 256, 32); } for (let i = 0; i < 90; i++) { g.strokeStyle = 'rgba(60,30,10,.12)'; g.beginPath(); const y = Math.random() * 256; g.moveTo(0, y); g.lineTo(256, y + Math.random() * 4); g.stroke(); } }
    else if (kind === 'marble') { for (let i = 0; i < 14; i++) { g.strokeStyle = `rgba(90,90,90,${.08 + Math.random() * .12})`; g.lineWidth = 1 + Math.random() * 2; g.beginPath(); let x = Math.random() * 256, y = 0; g.moveTo(x, y); while (y < 256) { x += Math.random() * 40 - 20; y += 24; g.lineTo(x, y); } g.stroke(); } g.strokeStyle = 'rgba(0,0,0,.15)'; g.strokeRect(0, 0, 256, 256); }
    else if (kind === 'grass') noise(6000, .22);
    else if (kind === 'concrete') noise(5000, .12);
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...rep); t.anisotropy = 4; return this.texCache[key] = t;
  }
  mat(color, kind, rep, extra = {}) { return new THREE.MeshStandardMaterial({ color: kind ? 0xffffff : color, map: kind ? this.tex(kind, color, rep) : null, roughness: .85, metalness: 0, ...extra }); }
  box(w, h, d, m, x, y, z, parent, shadow = true) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); b.position.set(x, y, z); b.castShadow = shadow; b.receiveShadow = true; parent.add(b); return b;
  }
  /* ---------- build ---------- */
  clear() { while (this.root.children.length) { const c = this.root.children.pop(); c.traverse(o => { o.geometry?.dispose?.(); }); } }
  setPlan(plan, keepCam = false) {
    this.plan = plan; this.clear(); this.groups = []; this.pickables = []; this.nightLights = []; this.glass = [];
    const st = plan.style || {}, wallCol = st.wall_color || '#f4efe6', pl = plan.plot;
    this.wallMat = this.mat(wallCol, 'plaster', [2, 2]); this.glassMat = new THREE.MeshStandardMaterial({ color: 0x9fc6e0, transparent: true, opacity: .45, roughness: .05, metalness: .2, emissive: 0x000000 });
    this.glass.push(this.glassMat);
    this.frameMat = this.mat('#4a3a2a'); this.doorMat = this.mat('#8a5a2b', 'wood', [1, 1]);
    // ground, plot pad, road
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(1200, 1200), this.mat('#8fae73', 'grass', [200, 200])); ground.rotation.x = -Math.PI / 2; ground.position.y = -.02; ground.receiveShadow = true; this.root.add(ground); this.ground = ground;
    const shp = new THREE.Shape(pl.polygon.map(([x, y]) => new THREE.Vector2(x, y))); const pad = new THREE.Mesh(new THREE.ShapeGeometry(shp), this.mat('#b9c79f', 'grass', [.15, .15])); pad.rotation.x = Math.PI / 2; pad.position.y = .01; pad.receiveShadow = true; this.root.add(pad);
    const rw = 24, R = { N: [pl.ex / 2, -rw / 2 - 1, pl.ex + 40, rw], S: [pl.ex / 2, pl.ny + rw / 2 + 1, pl.ex + 40, rw], W: [-rw / 2 - 1, pl.ny / 2, rw, pl.ny + 40], E: [pl.ex + rw / 2 + 1, pl.ny / 2, rw, pl.ny + 40] }[pl.road];
    const road = new THREE.Mesh(new THREE.PlaneGeometry(R[2], R[3]), this.mat('#4b4f57', 'concrete', [6, 6])); road.rotation.x = -Math.PI / 2; road.position.set(R[0], .03, R[1]); road.receiveShadow = true; this.root.add(road);
    // compound wall
    const cm = this.mat('#d8d1c2', 'plaster', [4, 1]);
    const poly = pl.polygon; for (let i = 0; i < poly.length; i++) {
      const [x1, y1] = poly[i], [x2, y2] = poly[(i + 1) % poly.length], len = Math.hypot(x2 - x1, y2 - y1);
      const m = new THREE.Mesh(new THREE.BoxGeometry(len, 3.5, .6), cm); m.position.set((x1 + x2) / 2, 1.75, (y1 + y2) / 2); m.rotation.y = -Math.atan2(y2 - y1, x2 - x1); m.castShadow = m.receiveShadow = true; this.root.add(m);
    }
    plan.floors.forEach((f, i) => { const g = this.buildFloor(plan, f, i); this.groups.push(g); this.root.add(g); });
    this.buildRoof(plan); this.applyVisibility(); this.applyMode();
    const cx = plan.buildable.x + plan.buildable.w / 2, cz = plan.buildable.y + plan.buildable.h / 2; this.center = new THREE.Vector3(cx, 8, cz); this.sun.target.position.copy(this.center);
    const span = Math.max(pl.ex, pl.ny); const sc = this.sun.shadow.camera; sc.left = sc.bottom = -span * .9; sc.right = sc.top = span * .9; sc.far = span * 6; sc.updateProjectionMatrix();
    this.sun.position.set(cx + span * .8, span * 1.6, cz + span * .9);
    if (!keepCam) this.setView('persp');
  }
  floorMatFor(r, st) {
    const base = st.floor_material || 'vitrified';
    if (r.type === 'garden') return this.mat('#8fae73', 'grass', [r.w / 6, r.h / 6]);
    if (r.type === 'parking') return this.mat('#8d9096', 'concrete', [r.w / 6, r.h / 6]);
    const kind = r.floor_mat || (r.cat === 'wet' ? 'tile' : r.cat === 'outdoor' ? 'tile' : ({ vitrified: 'tile', wood: 'wood', marble: 'marble', granite: 'marble', kota: 'concrete' }[base] || 'tile'));
    const col = r.floor_color || (kind === 'tile' ? (r.cat === 'wet' ? '#cfd8dc' : '#ece7dc') : kind === 'wood' ? '#b98a56' : kind === 'marble' ? '#f1efe9' : '#9a9d95');
    return this.mat(col, kind, [r.w / 4, r.h / 4], { roughness: kind === 'marble' ? .25 : .7 });
  }
  buildFloor(plan, f, fi) {
    const g = new THREE.Group(); g.userData.fi = fi; const st = plan.style || {}, E = f.elevation, H = f.height, ol = f.outline;
    if (f.kind === 'terrace') { g.userData.terrace = true; }
    for (const r of f.rooms) {
      if (f.kind === 'terrace' && r.type !== 'headroom') continue;
      const m = this.box(r.w, .4, r.h, this.floorMatFor(r, st), r.x + r.w / 2, E - .2, r.y + r.h / 2, g, false); m.userData = { pick: 'room', fi, id: r.id };
      if (r.type === 'garden') m.position.y = E + .02, m.scale.y = .1; this.pickables.push(m);
      if (!r.outdoor && r.type !== 'garden' && f.kind !== 'terrace' && r.type !== 'parking') {
        const pt = new THREE.PointLight(0xffd9a0, 0, 28, 1.6); pt.position.set(r.x + r.w / 2, E + H - 1.2, r.y + r.h / 2); g.add(pt); this.nightLights.push(pt);
      }
    }
    if (f.kind === 'terrace') { // terrace walking surface: parapet only, headroom block built from room
      const t = this.box(ol.w, .4, ol.h, this.mat('#bdb8ad', 'concrete', [ol.w / 6, ol.h / 6]), ol.x + ol.w / 2, E - .2, ol.y + ol.h / 2, g, false);
      const par = st.parapet_ft ?? 3, pm = this.mat('#e9e3d6', 'plaster', [3, 1]);
      this.box(ol.w + .75, par, .75, pm, ol.x + ol.w / 2, E + par / 2, ol.y, g); this.box(ol.w + .75, par, .75, pm, ol.x + ol.w / 2, E + par / 2, ol.y + ol.h, g);
      this.box(.75, par, ol.h, pm, ol.x, E + par / 2, ol.y + ol.h / 2, g); this.box(.75, par, ol.h, pm, ol.x + ol.w, E + par / 2, ol.y + ol.h / 2, g);
      this.terraceG = g;
    }
    const wallH = f.kind === 'terrace' ? 8.5 : H - .1;
    const doors = f.doors || [], wins = f.windows || [];
    for (const w of PlanDraw.floorWalls(f.rooms.filter(r => f.kind !== 'terrace' || r.type === 'headroom'), ol, st.wall_ext ?? .75, st.wall_int ?? .375)) this.buildWall(g, w, E, wallH, doors, wins, f.kind === 'basement', st);
    for (const fu of f.furniture || []) { const o = this.furn(fu, f); if (o) { o.position.y = E; o.userData = { pick: 'furn', fi, id: fu }; g.add(o); this.pickables.push(o); } }
    return g;
  }
  buildWall(g, w, E, H, doors, wins, basement, st) {
    const horiz = w.o === 'h', t = w.t, ops = [];
    for (const d of doors) if (d.orient === (horiz ? 'h' : 'v') && Math.abs((horiz ? d.y : d.x) - w.line) < .02) { const c = horiz ? d.x : d.y; if (c >= w.s && c <= w.e) ops.push({ c, w: d.width, y0: 0, y1: 7, door: d }); }
    if (!basement) for (const x of wins) if (x.orient === (horiz ? 'h' : 'v') && Math.abs((horiz ? x.y : x.x) - w.line) < .02) { const c = horiz ? x.x : x.y; if (c >= w.s && c <= w.e) ops.push({ c, w: x.width, y0: x.sill, y1: x.head, win: x }); }
    ops.sort((a, b) => a.c - b.c);
    const seg = (a, b, y0, y1) => { if (b - a < .01 || y1 - y0 < .01) return; const len = b - a, m = (a + b) / 2, yc = E + (y0 + y1) / 2; const mat = this.wallMat; if (horiz) this.box(len, y1 - y0, t, mat, m, yc, w.line, g); else this.box(t, y1 - y0, len, mat, w.line, yc, m, g); };
    let cur = w.s - t / 2;
    for (const o of ops) {
      const a = o.c - o.w / 2, b = o.c + o.w / 2; seg(cur, a, 0, H); if (o.y0 > 0) seg(a, b, 0, o.y0); seg(a, b, o.y1, H); cur = b;
      const yc = E + (o.y0 + o.y1) / 2, hh = o.y1 - o.y0;
      if (o.win) { const gl = horiz ? this.box(o.w - .2, hh - .2, .08, this.glassMat, o.c, yc, w.line, g, false) : this.box(.08, hh - .2, o.w - .2, this.glassMat, w.line, yc, o.c, g, false); [[-1, 0], [1, 0]].forEach(() => 0);
        const f = this.frameMat, fw = .12; if (horiz) { this.box(o.w, fw, t + .1, f, o.c, E + o.y0, w.line, g, false); this.box(o.w, fw, t + .1, f, o.c, E + o.y1, w.line, g, false); this.box(fw, hh, t + .1, f, o.c, yc, w.line, g, false); } else { this.box(t + .1, fw, o.w, f, w.line, E + o.y0, o.c, g, false); this.box(t + .1, fw, o.w, f, w.line, E + o.y1, o.c, g, false); this.box(t + .1, hh, fw, f, w.line, yc, o.c, g, false); } }
      if (o.door && o.door.kind === 'main') { if (horiz) this.box(o.w - .2, hh - .1, .18, this.doorMat, o.c, yc, w.line, g); else this.box(.18, hh - .1, o.w - .2, this.doorMat, w.line, yc, o.c, g); }
      else if (o.door) { const f = this.frameMat; if (horiz) this.box(o.w, .15, t + .06, f, o.c, E + 7, w.line, g, false); else this.box(t + .06, .15, o.w, f, w.line, E + 7, o.c, g, false); }
    }
    seg(cur, w.e + t / 2, 0, H);
    if (H < 20 && w.ext && !basement) { const sk = this.mat('#cfc6b4'); if (horiz) this.box(w.e - w.s + t + .3, .35, t + .3, sk, (w.s + w.e) / 2, E + .17, w.line, g, false); else this.box(t + .3, .35, w.e - w.s + t + .3, sk, w.line, E + .17, (w.s + w.e) / 2, g, false); }
  }
  buildRoof(plan) {
    this.roofG = new THREE.Group(); const st = plan.style || {}, lv = plan.floors.filter(f => f.kind !== 'terrace'), top = lv[lv.length - 1], ol = top.outline, y = top.elevation + top.height, kind = st.roof || 'flat';
    const hasTerrace = plan.floors.some(f => f.kind === 'terrace');
    if (hasTerrace || kind === 'flat') { this.box(ol.w + 1.2, .5, ol.h + 1.2, this.mat('#b9b4a8', 'concrete', [4, 4]), ol.x + ol.w / 2, y - .25 + .25, ol.y + ol.h / 2, this.roofG); this.roofIsFlat = true;
      if (!hasTerrace) { const par = st.parapet_ft ?? 3, pm = this.mat('#e9e3d6', 'plaster', [3, 1]); this.box(ol.w + 1, par, .7, pm, ol.x + ol.w / 2, y + par / 2, ol.y, this.roofG); this.box(ol.w + 1, par, .7, pm, ol.x + ol.w / 2, y + par / 2, ol.y + ol.h, this.roofG); this.box(.7, par, ol.h, pm, ol.x, y + par / 2, ol.y + ol.h / 2, this.roofG); this.box(.7, par, ol.h, pm, ol.x + ol.w, y + par / 2, ol.y + ol.h / 2, this.roofG); }
    } else {
      this.box(ol.w + 1, .5, ol.h + 1, this.mat('#b9b4a8', 'concrete', [4, 4]), ol.x + ol.w / 2, y, ol.y + ol.h / 2, this.roofG);
      const rise = Math.min(ol.w, ol.h) * .32, rm = this.mat('#a8503a', 'brick', [6, 6]); let m;
      if (kind === 'hip') { const r = 1; m = new THREE.Mesh(new THREE.ConeGeometry(r * Math.SQRT2 / 1, 1, 4), rm); m.rotation.y = Math.PI / 4; m.scale.set((ol.w + 2) / 2, rise, (ol.h + 2) / 2); m.position.set(ol.x + ol.w / 2, y + .25 + rise / 2, ol.y + ol.h / 2); }
      else { const sh = new THREE.Shape([new THREE.Vector2(-(ol.w + 2) / 2, 0), new THREE.Vector2((ol.w + 2) / 2, 0), new THREE.Vector2(0, rise)]); m = new THREE.Mesh(new THREE.ExtrudeGeometry(sh, { depth: ol.h + 2, bevelEnabled: false }), rm); m.position.set(ol.x + ol.w / 2, y + .25, ol.y - 1); }
      m.castShadow = m.receiveShadow = true; this.roofG.add(m);
    }
    this.root.add(this.roofG);
  }
  /* ---------- furniture (simple but recognisable primitives) ---------- */
  furn(f, floor) {
    const g = new THREE.Group(), cx = f.x + f.w / 2, cz = f.y + f.h / 2, M = (c, k) => this.mat(c, k);
    const B = (w, h, d, m, x, y, z) => this.box(w, h, d, m, x, y, z, g);
    const long = f.w >= f.h; g.position.set(0, 0, 0); g.userData.cx = cx; g.userData.cz = cz;
    switch (f.kind) {
      case 'stairs': {
        const n = f.risers || 0; if (!n) return null; const H = floor.height, rh = H / n, ax = f.axis, len = ax === 'y' ? f.h : f.w, sw = ax === 'y' ? f.w : f.h, td = len / n, m = this.mat('#c9c2b2', 'concrete', [1, 1]);
        for (let i = 0; i < n; i++) { const k = f.start_far ? n - 1 - i : i; const p = f.x * (ax === 'x') + f.y * (ax === 'y') + td * (k + .5); const hh = rh * (i + 1);
          if (ax === 'y') B(sw, hh, td, m, cx, hh / 2, p); else B(td, hh, sw, m, p, hh / 2, cz); }
        return g; }
      case 'bed': { B(f.w, .9, f.h, M('#6b4a2f', 'wood'), cx, .45, cz); B(f.w - .3, .45, f.h - .3, M('#e9e4f0', 'plaster'), cx, 1.1, cz);
        const pw = Math.max(f.w / 2 - .5, .6); for (const s of [-1, 1]) long ? B(1, .3, pw, M('#fff'), f.x + .8, 1.45, cz + s * f.h / 4) : B(pw, .3, 1, M('#fff'), cx + s * f.w / 4, 1.45, f.y + .8); return g; }
      case 'sofa': { B(f.w, 1.2, f.h, M('#7d6a5a'), cx, .6, cz); long ? B(f.w, 1.2, .7, M('#6a5849'), cx, 1.8, f.y + .35) : B(.7, 1.2, f.h, M('#6a5849'), f.x + .35, 1.8, cz); return g; }
      case 'armchair': case 'chair': { const s = f.kind === 'chair' ? 1.4 : 1.1; B(f.w, s * .35, f.h, M('#7d6a5a'), cx, s * .5, cz); B(f.w, .8, .25, M('#6a5849'), cx, s * .9 + .2, f.y + .15); return g; }
      case 'coffee_table': case 'sidetable': case 'dining_table': case 'desk': { const h = f.kind === 'sidetable' ? 1.6 : f.kind === 'coffee_table' ? 1.3 : 2.5; B(f.w, .18, f.h, M('#8a6b48', 'wood'), cx, h, cz); for (const [a, b] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) B(.15, h, .15, M('#5a432b'), cx + a * (f.w / 2 - .15), h / 2, cz + b * (f.h / 2 - .15)); return g; }
      case 'tv': B(f.w, 1.8, f.h, M('#4a3a2a', 'wood'), cx, .9, cz); long ? B(Math.min(f.w - .5, 4), 2.2, .12, M('#111'), cx, 3.2, cz) : B(.12, 2.2, Math.min(f.h - .5, 4), M('#111'), cx, 3.2, cz); return g;
      case 'wardrobe': B(f.w, 7, f.h, M('#8a6b48', 'wood'), cx, 3.5, cz); return g;
      case 'dresser': case 'shelf': B(f.w, f.kind === 'shelf' ? 6 : 3, f.h, M('#8a6b48', 'wood'), cx, f.kind === 'shelf' ? 3 : 1.5, cz); return g;
      case 'counter': B(f.w, 2.8, f.h, M('#d8d3c8'), cx, 1.4, cz); B(f.w, .15, f.h, M('#2d3036'), cx, 2.88, cz); if (f.h > 1.8 && f.w > 1.8) B(f.w, 2, .9, M('#e9e3d6'), long ? cx : f.x + .45, 6, long ? f.y + .45 : cz); return g;
      case 'sink': B(f.w, 2.8, f.h, M('#d8d3c8'), cx, 1.4, cz); B(Math.min(f.w, f.h) * .7, .1, Math.min(f.w, f.h) * .7, M('#b8bec4'), cx, 2.85, cz); return g;
      case 'fridge': B(f.w, 5.8, f.h, M('#e6e8ea'), cx, 2.9, cz); return g;
      case 'wc': B(f.w * .8, 1.3, f.h * .65, M('#f5f5f5'), cx, .65, cz + (long ? 0 : f.h * .15)); B(f.w * .8, 1.8, f.h * .25, M('#f5f5f5'), cx, 1.6, f.y + f.h * .15); return g;
      case 'basin': B(f.w, .15, f.h, M('#f5f5f5'), cx, 2.7, cz); B(f.w * .3, 2.6, f.h * .3, M('#f5f5f5'), cx, 1.3, cz); return g;
      case 'shower': B(f.w, .15, f.h, M('#cfd8dc'), cx, .08, cz); B(.08, 6.5, f.h, this.glassMat, f.x + f.w, 3.25, cz); return g;
      case 'washer': B(f.w, 3, f.h, M('#eceff1'), cx, 1.5, cz); return g;
      case 'mandir': B(f.w, 3, f.h, M('#c77d2b'), cx, 1.5, cz); B(f.w * .7, 1.4, f.h * .7, M('#f3b24a'), cx, 3.7, cz); return g;
      case 'planter': { const m = new THREE.Mesh(new THREE.CylinderGeometry(Math.min(f.w, f.h) / 2, Math.min(f.w, f.h) / 2.4, 1.2, 16), M('#8a5a3a')); m.position.set(cx, .6, cz); g.add(m); const s = new THREE.Mesh(new THREE.SphereGeometry(Math.min(f.w, f.h) * .55, 12, 10), M('#3f7d3a')); s.position.set(cx, 2.1, cz); s.castShadow = true; g.add(s); return g; }
      case 'car': { B(f.w, 1.6, f.h, M('#8a1f1f'), cx, 1.2, cz); B(f.w * (long ? .5 : .85), 1.3, f.h * (long ? .85 : .5), M('#a63030'), cx, 2.5, cz); for (const [a, b] of [[.35, .5], [-.35, .5], [.35, -.5], [-.35, -.5]]) { const w = new THREE.Mesh(new THREE.CylinderGeometry(.6, .6, .5, 12), M('#111')); w.rotation.z = long ? 0 : Math.PI / 2; w.rotation.x = long ? Math.PI / 2 : 0; w.position.set(cx + a * f.w * (long ? 1 : 1.15), .6, cz + b * f.h * (long ? 1.15 : 1)); g.add(w); } return g; }
      default: B(f.w, 1.5, f.h, M('#b9b4a8'), cx, .75, cz); return g;
    }
  }
  /* ---------- modes, visibility, views ---------- */
  setDay() { this.night = false; this.applyMode(); }
  setNight() { this.night = true; this.applyMode(); }
  applyMode() {
    const n = this.night; this.scene.background = new THREE.Color(n ? 0x0b1022 : 0xcfe5f5); this.scene.fog = new THREE.Fog(n ? 0x0b1022 : 0xcfe5f5, 250, 900);
    this.hemi.intensity = n ? .22 : .75; this.sun.intensity = n ? .08 : .95; this.sun.color.set(n ? 0x8899ff : 0xfff3dc);
    this.renderer.toneMappingExposure = n ? 1 : 1.05; (this.nightLights || []).forEach(l => l.intensity = n ? .7 : 0);
    (this.glass || []).forEach(m => { m.emissive.set(n ? 0xffc766 : 0x000000); m.emissiveIntensity = n ? .8 : 0; m.opacity = n ? .75 : .45; });
  }
  applyVisibility() {
    if (!this.groups) return; const lv = this.groups.length;
    this.groups.forEach((g, i) => { g.visible = this.isolate === null ? true : (this.isolate === 'upto' ? i <= this.upto : i === this.isolate); });
    const topVisible = this.isolate === null || this.isolate === 'upto' && this.upto >= lv - 1;
    const terr = this.groups.findIndex(g => g.userData.terrace); if (terr >= 0 && this.plan.style?.roof && this.plan.style.roof !== 'flat') this.groups[terr].visible = false;
    if (this.roofG) this.roofG.visible = this.showRoof && topVisible;
  }
  showAll() { this.isolate = null; this.applyVisibility(); }
  showFloor(i) { this.isolate = i; this.applyVisibility(); }
  showUpTo(i) { this.isolate = 'upto'; this.upto = i; this.applyVisibility(); }
  setRoofVisible(v) { this.showRoof = v; this.applyVisibility(); }
  setView(v) {
    const c = this.center || new THREE.Vector3(), pl = this.plan.plot, span = Math.max(pl.ex, pl.ny), top = Math.max(...this.plan.floors.map(f => f.elevation + f.height));
    const road = { N: [0, -1], S: [0, 1], W: [-1, 0], E: [1, 0] }[pl.road], T = this.controls.target; this.controls.autoRotate = false; this.camera.up.set(0, 1, 0); this.camera.fov = v === 'interior' ? 70 : 42; this.camera.updateProjectionMatrix();
    let p;
    if (v === 'top') { p = [c.x, span * 1.7 + top, c.z + .01]; T.set(c.x, 0, c.z); }
    else if (v === 'front') { p = [c.x + road[0] * span * 1.8, top * .5 + 6, c.z + road[1] * span * 1.8]; T.set(c.x, top * .45, c.z); }
    else if (v === 'side') { p = [c.x + road[1] * span * 1.8, top * .5 + 6, c.z - road[0] * span * 1.8]; T.set(c.x, top * .45, c.z); }
    else if (v === 'interior') {
      const fi = this.isolate === null || this.isolate === 'upto' ? 0 : this.isolate, f = this.plan.floors[fi];
      const rooms = f.rooms.filter(r => !r.outdoor && !['garden', 'parking', 'headroom', 'terrace', 'balcony'].includes(r.type)).sort((a, b) => b.w * b.h - a.w * a.h);
      const r = rooms.find(x => x.type === 'living') || rooms[0] || f.outline, k = Math.min(r.w, r.h) * .3;
      p = [r.x + r.w - k, f.elevation + 5.4, r.y + r.h - k]; T.set(r.x + k, f.elevation + 3.8, r.y + k);
      this.setRoofVisible(true); this.isolate = fi; this.applyVisibility(); this.camera.position.set(...p); this.controls.update(); return; }
    else { p = [c.x + span * 1.1 + road[0] * span * .9, top + span * .55, c.z + span * 1.1 + road[1] * span * .9]; T.set(c.x, top * .4, c.z); }
    this.camera.position.set(...p); this.controls.update();
  }
  setAutoRotate(v) { this.controls.autoRotate = v; this.controls.autoRotateSpeed = 2.2; }
  zoom(k) { const d = this.camera.position.clone().sub(this.controls.target).multiplyScalar(1 / k); this.camera.position.copy(this.controls.target.clone().add(d)); }
  screenshot() { this.renderer.render(this.scene, this.camera); return new Promise(r => this.renderer.domElement.toBlob(r, 'image/png')); }
  /* ---------- picking & editing ---------- */
  pick(e) {
    const r = this.renderer.domElement.getBoundingClientRect(); this.mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(this.mouse, this.camera);
    const cand = this.pickables.filter(o => { let v = true; o.traverseAncestors(a => { if (a.visible === false) v = false; }); return v; });
    const hits = this.ray.intersectObjects(cand, true); if (!hits.length) return null;
    let o = hits[0].object; while (o && !o.userData.pick) o = o.parent; return o ? { obj: o, point: hits[0].point } : null;
  }
  pdown(e) {
    const h = this.pick(e); this.dragState = null; this.downAt = [e.clientX, e.clientY];
    if (!h) { this.markSel(null); this.cb.onSelect?.(null); return; }
    const u = h.obj.userData;
    if (u.pick === 'furn') { this.markSel(h.obj); this.cb.onSelect?.({ kind: 'furn', fi: u.fi, item: u.id });
      const f = this.plan.floors[u.fi], plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -f.elevation); const pt = new THREE.Vector3(); this.ray.ray.intersectPlane(plane, pt);
      this.dragState = { obj: h.obj, plane, off: pt.clone(), start: { x: u.id.x, y: u.id.y }, moved: false }; this.controls.enabled = false; }
    else if (u.pick === 'room') { this.markSel(null); this.cb.onSelect?.({ kind: 'room', fi: u.fi, id: u.id }); }
  }
  pmove(e) {
    const d = this.dragState; if (!d) return;
    const r = this.renderer.domElement.getBoundingClientRect(); this.mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); this.ray.setFromCamera(this.mouse, this.camera);
    const pt = new THREE.Vector3(); if (!this.ray.ray.intersectPlane(d.plane, pt)) return;
    const it = d.obj.userData.id, room = this.roomAt(d.obj.userData.fi, it);
    let nx = snap(d.start.x + pt.x - d.off.x, .25), ny = snap(d.start.y + pt.z - d.off.z, .25);
    if (room) { nx = Math.min(Math.max(nx, room.x + .2), room.x + room.w - it.w - .2); ny = Math.min(Math.max(ny, room.y + .2), room.y + room.h - it.h - .2); }
    d.obj.position.x = nx - d.start.x; d.obj.position.z = ny - d.start.y; d.nx = nx; d.ny = ny; d.moved = true;
  }
  pup() {
    const d = this.dragState; this.dragState = null; this.controls.enabled = true; if (!d || !d.moved) return;
    const it = d.obj.userData.id; it.x = d.nx; it.y = d.ny; this.cb.onFurnitureMoved?.(d.obj.userData.fi, it);
  }
  roomAt(fi, it) { return this.plan.floors[fi].rooms.find(r => it.room === r.id) || this.plan.floors[fi].rooms.find(r => it.x >= r.x - .01 && it.y >= r.y - .01 && it.x < r.x + r.w && it.y < r.y + r.h); }
  markSel(obj) {
    if (this.selBox) { this.selBox.parent?.remove(this.selBox); this.selBox = null; }
    if (!obj) return; this.selBox = new THREE.BoxHelper(obj, 0xb8923a); this.root.add(this.selBox);
    const upd = () => { if (this.selBox) { this.selBox.update(); requestAnimationFrame(upd); } }; upd();
  }
}
