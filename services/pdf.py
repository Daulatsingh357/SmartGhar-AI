"""Vector PDF drawings (ReportLab) generated directly from plan geometry - never raster images."""
import io
import math
from datetime import datetime
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from engine.geom import floor_walls, fmt_ft, inward

GOLD, CHAR, GREY, LIGHT = HexColor("#b8923a"), HexColor("#25282d"), HexColor("#8a8f98"), HexColor("#eceae4")
PAGE = landscape(A3)
W, H = PAGE
M = 18 * mm


class Sheet:
    """Maps plan feet (origin NW, y down) into a PDF box, scaled to fit."""

    def __init__(self, c, bx, by, bw, bh, ex, ny, pad=26):
        self.c = c
        self.s = min((bw - 2 * pad) / ex, (bh - 2 * pad) / ny)
        self.ox = bx + (bw - ex * self.s) / 2
        self.oy = by + (bh - ny * self.s) / 2
        self.ny = ny

    def p(self, x, y):
        return self.ox + x * self.s, self.oy + (self.ny - y) * self.s

    def L(self, v):
        return v * self.s


def frame(c, title, sub, page_no, name, disclaimer):
    c.setStrokeColor(CHAR); c.setLineWidth(1.2)
    c.rect(M / 2, M / 2, W - M, H - M)
    c.setFillColor(CHAR); c.setFont("Helvetica-Bold", 20); c.drawString(M, H - M - 8, title)
    c.setFont("Helvetica", 10); c.setFillColor(GREY); c.drawString(M, H - M - 24, sub)
    c.setFillColor(GOLD); c.setFont("Helvetica-Bold", 11); c.drawRightString(W - M, H - M - 8, "SMARTGHAR AI")
    c.setFillColor(GREY); c.setFont("Helvetica", 8)
    c.drawRightString(W - M, H - M - 22, f"{name}  |  {datetime.now():%d %b %Y}")
    c.setStrokeColor(GOLD); c.setLineWidth(0.8); c.line(M, H - M - 32, W - M, H - M - 32)
    c.setFillColor(GREY); c.setFont("Helvetica-Oblique", 7)
    c.drawString(M, M / 2 + 8, disclaimer[:230])
    c.drawRightString(W - M, M / 2 + 8, f"Sheet {page_no}")


def north_arrow(c, x, y, r=22):
    c.setStrokeColor(CHAR); c.setFillColor(CHAR); c.setLineWidth(1)
    c.circle(x, y, r, stroke=1, fill=0)
    p = c.beginPath(); p.moveTo(x, y + r - 2); p.lineTo(x - 7, y - r + 6); p.lineTo(x, y - 4); p.lineTo(x + 7, y - r + 6); p.close()
    c.drawPath(p, stroke=1, fill=1)
    c.setFont("Helvetica-Bold", 11); c.drawCentredString(x, y + r + 5, "N")


def scale_bar(c, sh, x, y, feet=10):
    c.setStrokeColor(CHAR); c.setFillColor(CHAR); c.setLineWidth(0.8)
    L = sh.L(feet)
    c.rect(x, y, L / 2, 4, fill=1); c.rect(x + L / 2, y, L / 2, 4, fill=0)
    c.setFont("Helvetica", 7)
    for i, t in enumerate((0, feet / 2, feet)):
        c.drawCentredString(x + L * i / 2, y - 9, f"{t:g}'")
    c.drawString(x + L + 6, y, f"Scale bar ({feet} ft)")


def dim_line(c, sh, x1, y1, x2, y2, off, text):
    """Dimension line between plan points, offset perpendicular by `off` plan feet (+ = outside)."""
    c.setStrokeColor(GREY); c.setFillColor(CHAR); c.setLineWidth(0.5)
    horiz = abs(y1 - y2) < 1e-6
    if horiz:
        a, b = sh.p(x1, y1 - off), sh.p(x2, y2 - off)
        for (px, py), (qx, qy) in (((sh.p(x1, y1)), a), ((sh.p(x2, y2)), b)):
            c.line(px, py + (3 if off > 0 else -3), qx, qy + (3 if off > 0 else -3))
    else:
        a, b = sh.p(x1 - off, y1), sh.p(x2 - off, y2)
        for (px, py), (qx, qy) in (((sh.p(x1, y1)), a), ((sh.p(x2, y2)), b)):
            c.line(px - 3, py, qx - 3, qy)
    c.line(a[0], a[1], b[0], b[1])
    for q in (a, b):
        c.circle(q[0], q[1], 1.3, stroke=0, fill=1)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    c.setFont("Helvetica", 7.5)
    if horiz:
        c.drawCentredString(mx, my + 3, text)
    else:
        c.saveState(); c.translate(mx - 3, my); c.rotate(90); c.drawCentredString(0, 0, text); c.restoreState()


def draw_door(c, sh, d, rooms):
    r = rooms.get(d['room'])
    if not r:
        return
    wall = d['wall']
    w = d['width']
    ax = (1, 0) if wall in ('N', 'S') else (0, 1)
    inv = inward(wall)
    cx, cy = d['x'], d['y']
    th = 0.75 if d.get('kind') != 'internal' else 0.4
    # clear the wall opening
    c.setFillColor(white); c.setStrokeColor(white)
    hw, ht = (w / 2, th / 2 + 0.05) if ax == (1, 0) else (th / 2 + 0.05, w / 2)
    x0, y0 = sh.p(cx - hw, cy + ht)
    c.rect(x0, y0, sh.L(2 * hw), sh.L(2 * ht), stroke=0, fill=1)
    # leaf + swing arc (hinge at the start of the opening)
    hx, hy = cx - ax[0] * w / 2, cy - ax[1] * w / 2
    closed = (hx + ax[0] * w, hy + ax[1] * w)
    opened = (hx + inv[0] * w, hy + inv[1] * w)
    c.setStrokeColor(CHAR); c.setLineWidth(0.7)
    H1, C1, O1 = sh.p(hx, hy), sh.p(*closed), sh.p(*opened)
    c.line(H1[0], H1[1], O1[0], O1[1])
    a0 = math.degrees(math.atan2(C1[1] - H1[1], C1[0] - H1[0]))
    a1 = math.degrees(math.atan2(O1[1] - H1[1], O1[0] - H1[0]))
    ext = (a1 - a0 + 540) % 360 - 180
    r_ = sh.L(w)
    c.setLineWidth(0.4); c.setStrokeColor(GREY)
    c.arc(H1[0] - r_, H1[1] - r_, H1[0] + r_, H1[1] + r_, a0, ext)


def draw_window(c, sh, wd):
    w = wd['width']
    horiz = wd['orient'] == 'h'
    th = 0.5
    hw, ht = (w / 2, th / 2) if horiz else (th / 2, w / 2)
    x0, y0 = sh.p(wd['x'] - hw, wd['y'] + ht)
    c.setFillColor(white); c.setStrokeColor(CHAR); c.setLineWidth(0.6)
    c.rect(x0, y0, sh.L(2 * hw), sh.L(2 * ht), stroke=1, fill=1)
    c.setLineWidth(0.4)
    if horiz:
        yy = y0 + sh.L(ht); c.line(x0, yy, x0 + sh.L(2 * hw), yy)
    else:
        xx = x0 + sh.L(hw); c.line(xx, y0, xx, y0 + sh.L(2 * ht))


def draw_furniture(c, sh, f):
    x0, y0 = sh.p(f['x'], f['y'] + f['h'])
    w, h = sh.L(f['w']), sh.L(f['h'])
    c.setStrokeColor(HexColor("#9a9fa8")); c.setFillColor(HexColor("#f7f5ef")); c.setLineWidth(0.4)
    if f['kind'] == 'stairs':
        c.rect(x0, y0, w, h, stroke=1, fill=0)
        n = max(int(f.get('risers', 12)) - 1, 3)
        for i in range(1, n):
            if f.get('axis', 'y') == 'y':
                c.line(x0, y0 + h * i / n, x0 + w, y0 + h * i / n)
            else:
                c.line(x0 + w * i / n, y0, x0 + w * i / n, y0 + h)
        return
    if f['kind'] in ('plant', 'tree', 'wc_round', 'basin_round'):
        c.circle(x0 + w / 2, y0 + h / 2, min(w, h) / 2, stroke=1, fill=0)
    else:
        c.rect(x0, y0, w, h, stroke=1, fill=1)
    if w > 30 and h > 12:
        c.setFillColor(GREY); c.setFont("Helvetica", 5.5)
        c.drawCentredString(x0 + w / 2, y0 + h / 2 - 2, f['kind'].replace('_', ' ').title())


def draw_floor(c, sh, plan, floor, furniture=True, electrical=False, dims=True):
    rooms = {r['id']: r for r in floor['rooms']}
    # room fills
    for r in floor['rooms']:
        x0, y0 = sh.p(r['x'], r['y'] + r['h'])
        outdoor = r.get('outdoor') or r['type'] in ('garden', 'terrace', 'parking', 'balcony')
        c.setFillColor(HexColor("#e6efdc") if r['type'] in ('garden', 'terrace') else HexColor("#f1efe9") if outdoor else white)
        c.setStrokeColor(white)
        c.rect(x0, y0, sh.L(r['w']), sh.L(r['h']), stroke=0, fill=1)
    if furniture:
        for f in floor.get('furniture', []):
            draw_furniture(c, sh, f)
    # walls
    c.setFillColor(CHAR); c.setStrokeColor(CHAR)
    for wl in floor_walls(floor['rooms'], floor['outline']):
        t = wl['t']
        if wl['orient'] == 'h':
            x0, y0 = sh.p(wl['s'] - t / 2, wl['line'] + t / 2); c.rect(x0, y0, sh.L(wl['e'] - wl['s'] + t), sh.L(t), stroke=0, fill=1)
        else:
            x0, y0 = sh.p(wl['line'] - t / 2, wl['e'] + t / 2); c.rect(x0, y0, sh.L(t), sh.L(wl['e'] - wl['s'] + t), stroke=0, fill=1)
    for d in floor.get('doors', []):
        draw_door(c, sh, d, rooms)
    for wd in floor.get('windows', []):
        draw_window(c, sh, wd)
    if electrical:
        c.setFillColor(GOLD); c.setStrokeColor(GOLD)
        for e in floor.get('electrical', []):
            px, py = sh.p(e['x'], e['y']); c.circle(px, py, 1.8, stroke=0, fill=1)
    # labels
    for r in floor['rooms']:
        cx, cy = sh.p(r['x'] + r['w'] / 2, r['y'] + r['h'] / 2)
        c.setFillColor(CHAR)
        small = sh.L(r['w']) < 48
        c.setFont("Helvetica-Bold", 6.5 if small else 8)
        nm = r['name']
        c.drawCentredString(cx, cy + 4, nm if not small else nm[:11])
        c.setFont("Helvetica", 6 if small else 7); c.setFillColor(GREY)
        c.drawCentredString(cx, cy - 5, f"{fmt_ft(r['w'])} x {fmt_ft(r['h'])}")
    if dims:
        o = floor['outline']
        dim_line(c, sh, o['x'], o['y'], o['x'] + o['w'], o['y'], 3.0, fmt_ft(o['w']))
        dim_line(c, sh, o['x'], o['y'], o['x'], o['y'] + o['h'], 3.0, fmt_ft(o['h']))


# ---- plumbing layout (derived from wet rooms) ------------------------------------------------
def draw_plumbing(c, sh, floor):
    wet = [f for f in floor.get('furniture', []) if f['kind'] in ('wc', 'basin', 'shower', 'sink', 'washer')]
    c.setStrokeColor(HexColor("#2a6fb0")); c.setFillColor(HexColor("#2a6fb0")); c.setLineWidth(1)
    pts = []
    for f in wet:
        px, py = sh.p(f['x'] + f['w'] / 2, f['y'] + f['h'] / 2)
        c.circle(px, py, 2.2, stroke=0, fill=1); pts.append((px, py, f['kind']))
    if pts:
        # simple stack on the nearest outside wall: horizontal run to the left of the cluster
        xs = min(p[0] for p in pts) - 10
        c.setDash(3, 2)
        for px, py, _ in pts:
            c.line(px, py, xs, py)
        c.setDash()
        ys = [p[1] for p in pts]
        c.line(xs, min(ys), xs, max(ys))
        c.setFont("Helvetica", 6); c.drawString(xs - 2, max(ys) + 6, "Stack")


# ---- elevations / section / roof / site -----------------------------------------------------
def _levels(plan):
    return [f for f in plan['floors'] if f['kind'] != 'terrace']


def draw_elevation(c, bx, by, bw, bh, plan, side="front"):
    """side 'front' = looking at the south face, 'side' = east face (flat drawing from geometry)."""
    lv = _levels(plan)
    o = plan['floors'][0]['outline']
    span = o['w'] if side == 'front' else o['h']
    top = max(f['elevation'] + f['height'] for f in lv)
    bot = min(f['elevation'] for f in lv)
    par = plan.get('style', {}).get('parapet_ft', 3.0)
    s = min((bw - 80) / span, (bh - 70) / (top - bot + par + 4))
    x0 = bx + (bw - span * s) / 2
    y0 = by + 30 - bot * s + 20
    c.setStrokeColor(CHAR); c.setLineWidth(1.2); c.setFillColor(HexColor("#f4efe6"))
    c.rect(x0, y0 + bot * s, span * s, (top - bot + par) * s, stroke=1, fill=1)
    below = [f for f in lv if f['elevation'] < 0]
    for f in lv:
        e0 = f['elevation']
        c.setLineWidth(0.5); c.setStrokeColor(GREY)
        c.line(x0, y0 + e0 * s, x0 + span * s, y0 + e0 * s)
        for wd in f.get('windows', []):
            if side == 'front':
                ok = wd['orient'] == 'h' and abs(wd['y'] - (o['y'] + o['h'])) < 0.6
                pos = wd['x'] - o['x']
            else:
                ok = wd['orient'] == 'v' and abs(wd['x'] - (o['x'] + o['w'])) < 0.6
                pos = wd['y'] - o['y']
            if ok and f['kind'] != 'basement':
                c.setFillColor(HexColor("#cfe3f1")); c.setStrokeColor(CHAR); c.setLineWidth(0.6)
                c.rect(x0 + (pos - wd['width'] / 2) * s, y0 + (e0 + wd['sill']) * s, wd['width'] * s, (wd['head'] - wd['sill']) * s, stroke=1, fill=1)
        for d in f.get('doors', []):
            if d.get('kind') != 'main' and not (f['index'] == 0 and d.get('kind') == 'main'):
                continue
            if side == 'front':
                ok = d['orient'] == 'h' and abs(d['y'] - (o['y'] + o['h'])) < 0.6
                pos = d['x'] - o['x']
            else:
                ok = d['orient'] == 'v' and abs(d['x'] - (o['x'] + o['w'])) < 0.6
                pos = d['y'] - o['y']
            if ok:
                c.setFillColor(HexColor("#8a5a2b")); c.setStrokeColor(CHAR)
                c.rect(x0 + (pos - d['width'] / 2) * s, y0 + e0 * s, d['width'] * s, 7 * s, stroke=1, fill=1)
    # parapet + ground line + level marks
    c.setStrokeColor(CHAR); c.setLineWidth(1.6)
    c.line(x0 - 30, y0, x0 + span * s + 30, y0)
    c.setFont("Helvetica", 7); c.setFillColor(CHAR)
    for f in lv:
        c.drawString(x0 + span * s + 8, y0 + f['elevation'] * s + 2, f"{f['name']}  +{f['elevation']:.1f}'")
    c.drawString(x0 + span * s + 8, y0 + (top + par) * s - 6, f"Parapet +{top + par:.1f}'")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(bx + bw / 2, by + 6, "FRONT ELEVATION (south face)" if side == 'front' else "SIDE ELEVATION (east face)")


def draw_section(c, bx, by, bw, bh, plan):
    lv = _levels(plan)
    o = plan['floors'][0]['outline']
    top = max(f['elevation'] + f['height'] for f in lv)
    bot = min(f['elevation'] for f in lv)
    s = min((bw - 80) / o['h'], (bh - 70) / (top - bot + 5))
    x0 = bx + (bw - o['h'] * s) / 2
    y0 = by + 30 - bot * s + 20
    c.setStrokeColor(CHAR); c.setFillColor(CHAR)
    for f in lv:
        c.setLineWidth(0.6)
        # cut slab
        c.rect(x0 - 0.75 * s, y0 + (f['elevation'] - 0.4) * s, (o['h'] + 1.5) * s, 0.4 * s, stroke=0, fill=1)
        for r in f['rooms']:
            if r.get('outdoor') or r['type'] in ('garden', 'headroom'):
                continue
            ry = r['y'] - o['y']
            c.setStrokeColor(GREY)
            c.rect(x0 + ry * s, y0 + f['elevation'] * s, r['h'] * s, f['height'] * s, stroke=1, fill=0)
            c.setFont("Helvetica", 5.5); c.setFillColor(GREY)
            if r['h'] * s > 26 and r['x'] <= o['x'] + 0.1:
                c.drawCentredString(x0 + (ry + r['h'] / 2) * s, y0 + (f['elevation'] + f['height'] / 2) * s, r['name'][:14])
            c.setFillColor(CHAR)
    c.setLineWidth(1.6); c.setStrokeColor(CHAR)
    c.rect(x0 - 0.75 * s, y0 + (top - 0.4) * s, (o['h'] + 1.5) * s, 0.4 * s, stroke=0, fill=1)
    c.line(x0 - 30, y0, x0 + o['h'] * s + 30, y0)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(bx + bw / 2, by + 6, "SECTION A-A (north-south cut)")


def draw_roof(c, sh, plan):
    o = plan['floors'][0]['outline']
    st = plan.get('style', {})
    roof_kind = st.get('roof', 'flat')
    x0, y0 = sh.p(o['x'], o['y'] + o['h'])
    c.setFillColor(HexColor("#e8e4da")); c.setStrokeColor(CHAR); c.setLineWidth(1.6)
    c.rect(x0, y0, sh.L(o['w']), sh.L(o['h']), stroke=1, fill=1)
    par = 0.75
    c.setLineWidth(0.6)
    ix, iy = sh.p(o['x'] + par, o['y'] + o['h'] - par)
    c.rect(ix, iy, sh.L(o['w'] - 2 * par), sh.L(o['h'] - 2 * par), stroke=1, fill=0)
    if roof_kind == 'flat':
        # slope arrows towards a drain at the SE corner
        c.setStrokeColor(GREY); c.setDash(2, 2)
        for fx in (0.25, 0.5, 0.75):
            a = sh.p(o['x'] + o['w'] * fx, o['y'] + o['h'] * 0.3); b = sh.p(o['x'] + o['w'] * fx, o['y'] + o['h'] * 0.8)
            c.line(a[0], a[1], b[0], b[1])
        c.setDash()
        dx, dy = sh.p(o['x'] + o['w'] - 2, o['y'] + o['h'] - 2)
        c.setFillColor(HexColor("#2a6fb0")); c.circle(dx, dy, 3, stroke=0, fill=1)
        c.setFillColor(GREY); c.setFont("Helvetica", 7); c.drawString(dx - 60, dy - 12, "Rainwater outlet; 1:100 slope")
    else:
        mx, _ = sh.p(o['x'] + o['w'] / 2, 0)
        c.setStrokeColor(CHAR); c.line(mx, y0, mx, y0 + sh.L(o['h']))
        c.setFont("Helvetica", 7); c.setFillColor(GREY); c.drawCentredString(mx, y0 + sh.L(o['h']) + 6, "Ridge")
    c.setFillColor(CHAR); c.setFont("Helvetica-Bold", 9)
    cx, cy = sh.p(o['x'] + o['w'] / 2, o['y'] + o['h'] / 2)
    c.drawCentredString(cx, cy, "ROOF PLAN")
    dim_line(c, sh, o['x'], o['y'], o['x'] + o['w'], o['y'], 3.0, fmt_ft(o['w']))
    dim_line(c, sh, o['x'], o['y'], o['x'], o['y'] + o['h'], 3.0, fmt_ft(o['h']))


def draw_site(c, sh, plan):
    pl = plan['plot']
    poly = pl['polygon']
    path = c.beginPath()
    for i, (x, y) in enumerate(poly):
        px, py = sh.p(x, y)
        path.moveTo(px, py) if i == 0 else path.lineTo(px, py)
    path.close()
    c.setFillColor(HexColor("#f3f6ec")); c.setStrokeColor(CHAR); c.setLineWidth(1.6); c.drawPath(path, stroke=1, fill=1)
    b = plan['buildable']
    bx, by = sh.p(b['x'], b['y'] + b['h'])
    c.setStrokeColor(GOLD); c.setLineWidth(0.8); c.setDash(4, 3)
    c.rect(bx, by, sh.L(b['w']), sh.L(b['h']), stroke=1, fill=0); c.setDash()
    g = plan['floors'][0]
    for r in g['rooms']:
        x0, y0 = sh.p(r['x'], r['y'] + r['h'])
        c.setFillColor(HexColor("#d9d5ca") if not r.get('outdoor') else HexColor("#e6efdc")); c.setStrokeColor(GREY); c.setLineWidth(0.4)
        c.rect(x0, y0, sh.L(r['w']), sh.L(r['h']), stroke=1, fill=1)
    # road strip
    road = pl['road']; ex, ny = pl['ex'], pl['ny']
    rw = 14
    c.setFillColor(HexColor("#4b4f57"))
    c.rect(*_road_rect(sh, road, ex, ny, rw), stroke=0, fill=1)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 8)
    rr = _road_rect(sh, road, ex, ny, rw)
    c.drawCentredString(rr[0] + rr[2] / 2, rr[1] + rr[3] / 2 - 3, "ROAD")
    c.setFillColor(CHAR); c.setFont("Helvetica", 7)
    s = pl['setbacks']
    c.drawString(bx + 4, by + sh.L(b['h']) - 10, f"Setbacks: front {s['front']}' rear {s['rear']}' side {s['side']}'")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(sh.p(0, ny)[0], sh.p(0, ny)[1] + 28, f"PLOT {pl['areas']['sqft']:.0f} sq ft  |  {pl['areas']['sqm']:.1f} sq m  |  {pl['areas']['sqyd']:.1f} sq yd")


def _road_rect(sh, road, ex, ny, rw):
    if road == 'N':
        x, y = sh.p(0, 0); return (x, y + 2, sh.L(ex), sh.L(rw))
    if road == 'S':
        x, y = sh.p(0, ny); return (x, y - 2 - sh.L(rw), sh.L(ex), sh.L(rw))
    if road == 'W':
        x, y = sh.p(0, ny); return (x - 2 - sh.L(rw), y, sh.L(rw), sh.L(ny))
    x, y = sh.p(ex, ny); return (x + 2, y, sh.L(rw), sh.L(ny))


# ---- public builders --------------------------------------------------------------------------
def _summary_page(c, plan, name, disclaimer, user):
    pl, m, v = plan['plot'], plan['metrics'], plan['vastu']
    frame(c, "Design Summary", f"{plan['title']}  -  prepared for {user}", 1, name, disclaimer)
    y = H - M - 70
    c.setFillColor(CHAR); c.setFont("Helvetica-Bold", 12); c.drawString(M, y, "Plot"); y -= 16
    c.setFont("Helvetica", 10)
    rows = [f"Size: {pl['ex']:g} ft x {pl['ny']:g} ft ({pl['shape']}), road on the {pl['road']} side, {pl['usage']}",
            f"Area: {pl['areas']['sqft']:.0f} sq ft = {pl['areas']['sqm']:.1f} sq m = {pl['areas']['sqyd']:.1f} sq yd",
            f"Setbacks: front {pl['setbacks']['front']} ft, rear {pl['setbacks']['rear']} ft, sides {pl['setbacks']['side']} ft",
            f"Buildable footprint: {plan['buildable']['w']:g} x {plan['buildable']['h']:g} ft ({pl['buildable_area']:.0f} sq ft)",
            f"Built-up total: {m['built_total_sqft']:.0f} sq ft | coverage {m['coverage_pct']}% | FAR {m['far']} | open space {m['open_space_sqft']:.0f} sq ft",
            f"Vastu score: {v['score']}/100 ({v['grade']}, {plan['vastu_mode']} mode)"]
    for t in rows:
        c.drawString(M + 8, y, t); y -= 14
    y -= 8
    c.setFont("Helvetica-Bold", 12); c.drawString(M, y, "Room schedule"); y -= 16
    c.setFont("Helvetica-Bold", 8)
    cols = [M + 8, M + 150, M + 330, M + 420]
    for x, t in zip(cols, ("Floor", "Room", "Size", "Area (sq ft)")):
        c.drawString(x, y, t)
    y -= 4; c.setStrokeColor(GOLD); c.line(M, y, M + 520, y); y -= 11
    c.setFont("Helvetica", 8)
    for r in m['rooms']:
        if y < M + 40:
            c.showPage(); frame(c, "Design Summary (cont.)", plan['title'], 1, name, disclaimer); y = H - M - 60; c.setFont("Helvetica", 8)
        c.drawString(cols[0], y, r['floor']); c.drawString(cols[1], y, r['name']); c.drawString(cols[2], y, r['dims']); c.drawString(cols[3], y, f"{r['area_sqft']:.0f}")
        y -= 11
    # right column: utilisation + recommendations
    x = W / 2 + 40; y = H - M - 70
    c.setFont("Helvetica-Bold", 12); c.setFillColor(CHAR); c.drawString(x, y, "Space utilisation"); y -= 16
    c.setFont("Helvetica", 9)
    for u in m['utilisation']:
        c.drawString(x + 8, y, f"{u['category']}: {u['sqft']:.0f} sq ft ({u['pct']}%)")
        c.setFillColor(GOLD); c.rect(x + 200, y - 1, u['pct'] * 3, 7, stroke=0, fill=1); c.setFillColor(CHAR); y -= 13
    y -= 10; c.setFont("Helvetica-Bold", 12); c.drawString(x, y, "Recommendations"); y -= 16; c.setFont("Helvetica", 9)
    for t in plan.get('recommendations', [])[:8]:
        words, line = t.split(), ""
        for w_ in words:
            if c.stringWidth(line + " " + w_, "Helvetica", 9) > 520:
                c.drawString(x + 8, y, "- " + line if not line.startswith("-") else line); y -= 12; line = w_
            else:
                line = (line + " " + w_).strip()
        c.drawString(x + 8, y, "- " + line); y -= 15
    c.showPage()


def plan_pdf(plan, name, disclaimer, user="Client"):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=PAGE)
    c.setTitle(f"{name} - SMARTGHAR AI"); c.setAuthor("SMARTGHAR AI")
    _summary_page(c, plan, name, disclaimer, user)
    pl = plan['plot']
    n = 2
    area = (M, M + 20, W - 2 * M, H - 2 * M - 70)
    for f in plan['floors']:
        if f['kind'] == 'terrace':
            continue
        frame(c, f"{f['name']} Plan", f"{plan['title']}  |  dimension plan with furniture", n, name, disclaimer)
        o = f['outline']
        sh = Sheet(c, *area, o['x'] + o['w'], o['y'] + o['h'], pad=50)
        draw_floor(c, sh, plan, f, furniture=True)
        north_arrow(c, W - M - 40, H - M - 90); scale_bar(c, sh, M + 10, M + 24)
        c.showPage(); n += 1
        frame(c, f"{f['name']} - Electrical & Plumbing", "Lights, fans, sockets, switches (gold) and wet points (blue)", n, name, disclaimer)
        sh = Sheet(c, *area, o['x'] + o['w'], o['y'] + o['h'], pad=50)
        draw_floor(c, sh, plan, f, furniture=False, electrical=True)
        draw_plumbing(c, sh, f)
        north_arrow(c, W - M - 40, H - M - 90)
        c.showPage(); n += 1
    frame(c, "Site Plan", "Plot boundary, setbacks, footprint and road", n, name, disclaimer)
    sh = Sheet(c, *area, pl['ex'], pl['ny'], pad=70)
    draw_site(c, sh, plan); north_arrow(c, W - M - 40, H - M - 90); scale_bar(c, sh, M + 10, M + 24)
    c.showPage(); n += 1
    frame(c, "Roof Plan", "Parapet, slope and drainage", n, name, disclaimer)
    o = plan['floors'][0]['outline']
    sh = Sheet(c, *area, o['x'] + o['w'], o['y'] + o['h'], pad=50)
    draw_roof(c, sh, plan); north_arrow(c, W - M - 40, H - M - 90)
    c.showPage(); n += 1
    frame(c, "Elevations", "Front (south) and side (east) faces", n, name, disclaimer)
    half = (W - 2 * M) / 2
    draw_elevation(c, M, M + 30, half, H - 2 * M - 80, plan, 'front')
    draw_elevation(c, M + half, M + 30, half, H - 2 * M - 80, plan, 'side')
    c.showPage(); n += 1
    frame(c, "Section", "Typical cross-section through the building", n, name, disclaimer)
    draw_section(c, M, M + 30, W - 2 * M, H - 2 * M - 80, plan)
    c.showPage()
    c.save()
    return buf.getvalue()


def estimate_pdf(plan, est, city, name, disclaimer):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    aw, ah = A4
    c.setTitle(f"{name} - Construction Estimate")
    def head():
        c.setFillColor(CHAR); c.setFont("Helvetica-Bold", 18); c.drawString(40, ah - 50, "Construction Cost Estimate")
        c.setFillColor(GOLD); c.setFont("Helvetica-Bold", 10); c.drawRightString(aw - 40, ah - 48, "SMARTGHAR AI")
        c.setFillColor(GREY); c.setFont("Helvetica", 9)
        c.drawString(40, ah - 66, f"{name}  |  {plan['title']}  |  Rates: {city}  |  {datetime.now():%d %b %Y}")
        c.setStrokeColor(GOLD); c.line(40, ah - 74, aw - 40, ah - 74)
    head()
    y = ah - 100
    c.setFont("Helvetica-Bold", 9); c.setFillColor(CHAR)
    xs = [40, 230, 300, 370, 450]
    for x, t in zip(xs, ("Item", "Quantity", "Unit", "Rate (INR)", "Amount (INR)")):
        c.drawString(x, y, t)
    y -= 5; c.line(40, y, aw - 40, y); y -= 13
    c.setFont("Helvetica", 9)
    for r in est['rows']:
        c.drawString(xs[0], y, str(r['item'])[:34]); c.drawString(xs[1], y, f"{r['qty']:,.1f}")
        c.drawString(xs[2], y, str(r['unit'])); c.drawString(xs[3], y, f"{r['rate']:,.2f}"); c.drawRightString(aw - 40, y, f"{r['amount']:,.0f}")
        y -= 14
    y -= 4; c.line(40, y, aw - 40, y); y -= 15
    c.setFont("Helvetica", 10)
    for k, v in est['cost_groups'].items():
        c.drawString(xs[0], y, k); c.drawRightString(aw - 40, y, f"{v:,.0f}"); y -= 14
    c.setFont("Helvetica-Bold", 12); c.setFillColor(GOLD)
    c.drawString(xs[0], y - 4, "TOTAL (approx.)"); c.drawRightString(aw - 40, y - 4, f"INR {est['total']:,.0f}")
    c.setFillColor(GREY); c.setFont("Helvetica", 9); c.drawString(xs[0], y - 20, f"About INR {est['per_sqft']:,.0f} per sq ft built-up ({est['built_sqft']:.0f} sq ft)")
    y -= 48; c.setFillColor(CHAR); c.setFont("Helvetica-Bold", 10); c.drawString(40, y, "Key quantities"); y -= 14; c.setFont("Helvetica", 9)
    q = est['quantities']
    for t in (f"Cement {q['cement_bags']} bags | Sand {q['sand_m3']} m3 | Aggregate {q['aggregate_m3']} m3",
              f"Bricks {q['bricks']:,} | Steel {q['steel_tonnes']} t | Concrete {q['concrete_m3']} m3 | Tiles {q['tiles_sqft']:,} sq ft | Paint {q['paint_litres']} L"):
        c.drawString(48, y, t); y -= 13
    y -= 8; c.setFont("Helvetica-Bold", 10); c.drawString(40, y, "Assumptions"); y -= 13; c.setFont("Helvetica", 8)
    for t in est['assumptions']:
        c.drawString(48, y, "- " + t[:120]); y -= 11
    c.setFillColor(GREY); c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(40, 36, disclaimer[:130]); c.drawString(40, 26, disclaimer[130:260])
    c.showPage(); c.save()
    return buf.getvalue()
