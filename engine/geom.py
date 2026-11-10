"""Shared geometry helpers. All plan coordinates are in FEET, origin = plot NW corner,
x grows east, y grows south (north is always "up" on the drawing)."""
import math

EPS = 1e-6
FT = 0.3048  # metres per foot


def ft_to_m(v):
    return v * FT


def fmt_ft(v):
    feet = int(math.floor(abs(v) + 1e-9))
    inches = int(round((abs(v) - feet) * 12))
    if inches == 12:
        feet, inches = feet + 1, 0
    return f"{feet}'-{inches}\""


def snap(v, step=0.5):
    return round(v / step) * step


def overlap_area(a, b):
    ox = min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])
    oy = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
    return ox * oy if ox > 1e-3 and oy > 1e-3 else 0.0


def shared_wall(a, b, min_len=0.5):
    """Return ('v'|'h', line, start, end) where rectangles a and b touch, else None."""
    t = 1e-3
    if abs(a['x'] + a['w'] - b['x']) < t or abs(b['x'] + b['w'] - a['x']) < t:
        line = a['x'] + a['w'] if abs(a['x'] + a['w'] - b['x']) < t else a['x']
        s, e = max(a['y'], b['y']), min(a['y'] + a['h'], b['y'] + b['h'])
        if e - s >= min_len:
            return ('v', line, s, e)
    if abs(a['y'] + a['h'] - b['y']) < t or abs(b['y'] + b['h'] - a['y']) < t:
        line = a['y'] + a['h'] if abs(a['y'] + a['h'] - b['y']) < t else a['y']
        s, e = max(a['x'], b['x']), min(a['x'] + a['w'], b['x'] + b['w'])
        if e - s >= min_len:
            return ('h', line, s, e)
    return None


def wall_len(r, wall):
    return r['w'] if wall in ('N', 'S') else r['h']


def opening_point(r, wall, t):
    """Centre point of an opening on `wall` of room r at offset t from the wall's west/north end."""
    if wall == 'N':
        return r['x'] + t, r['y'], 'h'
    if wall == 'S':
        return r['x'] + t, r['y'] + r['h'], 'h'
    if wall == 'W':
        return r['x'], r['y'] + t, 'v'
    return r['x'] + r['w'], r['y'] + t, 'v'


def inward(wall):
    return {'N': (0, 1), 'S': (0, -1), 'W': (1, 0), 'E': (-1, 0)}[wall]


def merge_intervals(iv, tol=1e-3):
    iv = sorted(iv)
    out = []
    for s, e in iv:
        if out and s <= out[-1][1] + tol:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def floor_walls(rooms, outline, ext_t=0.75, int_t=0.375):
    """Unique wall centre-line segments of a floor. Shared walls are returned once."""
    segs = {}
    for r in rooms:
        if r.get('outdoor') or r['type'] in ('terrace',):
            continue
        x, y, w, h = r['x'], r['y'], r['w'], r['h']
        for key, s, e in (
            (('h', round(y, 3)), x, x + w), (('h', round(y + h, 3)), x, x + w),
            (('v', round(x, 3)), y, y + h), (('v', round(x + w, 3)), y, y + h)):
            segs.setdefault(key, []).append((s, e))
    ox, oy, ow, oh = outline['x'], outline['y'], outline['w'], outline['h']
    walls = []
    for (orient, line), iv in segs.items():
        for s, e in merge_intervals(iv):
            if orient == 'h':
                ext = abs(line - oy) < 1e-3 or abs(line - (oy + oh)) < 1e-3
            else:
                ext = abs(line - ox) < 1e-3 or abs(line - (ox + ow)) < 1e-3
            walls.append({'orient': orient, 'line': line, 's': s, 'e': e, 'ext': ext,
                          't': ext_t if ext else int_t})
    return walls


def polygon_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def point_in_polygon(px, py, pts):
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def dist_point_segment(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
