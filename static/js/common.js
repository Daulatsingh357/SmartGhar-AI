const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const NS = 'http://www.w3.org/2000/svg';
const clone = o => JSON.parse(JSON.stringify(o));
const snap = (v, s = 0.5) => Math.round(v / s) * s;
const r1 = v => Math.round(v * 10) / 10;
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function fmtFt(v) {
  let f = Math.floor(Math.abs(v) + 1e-9), i = Math.round((Math.abs(v) - f) * 12);
  if (i === 12) { f++; i = 0; }
  return `${f}'-${i}"`;
}
const inr = v => '₹' + Math.round(v).toLocaleString('en-IN');
async function api(path, body, method) {
  const opt = { method: method || (body ? 'POST' : 'GET'), headers: { 'Content-Type': 'application/json' } };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch(path, opt);
  if (r.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); throw new Error('login'); }
  const ct = r.headers.get('content-type') || '';
  if (!r.ok) {
    let m = 'Request failed';
    try { m = (await r.json()).error || m; } catch (e) {}
    throw new Error(m);
  }
  return ct.includes('json') ? r.json() : r.blob();
}
let _tt;
function toast(msg, ms = 2600) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(_tt); _tt = setTimeout(() => t.classList.remove('show'), ms);
}
function saveBlob(blob, name) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
function svgToPng(svgEl, scale = 2) {
  return new Promise((res, rej) => {
    const xml = new XMLSerializer().serializeToString(svgEl);
    const vb = svgEl.viewBox.baseVal;
    const w = Math.round((vb.width || svgEl.clientWidth) * scale), h = Math.round((vb.height || svgEl.clientHeight) * scale);
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.drawImage(img, 0, 0, w, h);
      c.toBlob(b => res(b), 'image/png');
    };
    img.onerror = rej;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
  });
}
const CAT_FILL = { living: '#fbf7ec', sleeping: '#f3f0f8', service: '#f6f1e6', wet: '#e9f1f6', outdoor: '#eef1e6', parking: '#efefef', circulation: '#f4f4f1' };
