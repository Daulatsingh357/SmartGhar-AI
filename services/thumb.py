"""Small SVG thumbnails of generated plans for the gallery (cached)."""
import json
from functools import lru_cache
from engine.plan import generate_plans


@lru_cache(maxsize=128)
def thumb_svg(inputs_json):
    try:
        res = generate_plans(json.loads(inputs_json))
        f = res['options'][0]['floors'][0]
        pl = res['plot']
    except Exception:
        return '<svg viewBox="0 0 10 10"></svg>'
    ex, ny = pl['ex'], pl['ny']
    out = [f'<svg viewBox="-3 -3 {ex + 6:.1f} {ny + 6:.1f}" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">',
           f'<rect x="0" y="0" width="{ex}" height="{ny}" fill="#faf8f4" stroke="#b8923a" stroke-width=".3" stroke-dasharray="1 .8"/>']
    for r in f['rooms']:
        col = '#dfe9d2' if r['type'] in ('garden',) else '#fff'
        out.append(f'<rect x="{r["x"]}" y="{r["y"]}" width="{r["w"]}" height="{r["h"]}" fill="{col}" stroke="#25282d" stroke-width=".55"/>')
        if r['w'] > 7 and r['h'] > 6:
            out.append(f'<text x="{r["x"] + r["w"] / 2}" y="{r["y"] + r["h"] / 2}" font-size="1.9" text-anchor="middle" fill="#7d838c" font-family="sans-serif">{r["name"][:12]}</text>')
    out.append('</svg>')
    return ''.join(out)
