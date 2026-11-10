"""Smart plot area calculator: dimensions -> areas, setbacks, buildable rectangle."""
import math
import re
from .geom import polygon_area, point_in_polygon, dist_point_segment

SQFT_TO_SQM = 0.09290304
SQFT_TO_SQYD = 1.0 / 9.0

# (max plot area sqft) -> (front, rear, side) setbacks in feet. Typical municipal values; always verify local by-laws.
SETBACK_TABLE = [
    (1000, (5.0, 3.0, 2.0)),
    (1500, (6.0, 4.0, 2.5)),
    (2000, (7.0, 5.0, 3.0)),
    (3500, (10.0, 6.0, 4.0)),
    (1e12, (15.0, 8.0, 6.0)),
]
ROAD_OPP = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_polygon(text):
    pts = []
    for part in re.split(r"[;\n]+", text or ""):
        nums = re.findall(r"-?\d+(?:\.\d+)?", part)
        if len(nums) >= 2:
            pts.append((float(nums[0]), float(nums[1])))
    return pts


def _shape_polygon(shape, ex, ny, road, p):
    rect = [(0, 0), (ex, 0), (ex, ny), (0, ny)]
    if shape == 'trapezium':
        rear = min(_f(p.get('rear_width'), ex * 0.7), ex if road in 'NS' else ny)
        if road in ('N', 'S'):
            off = (ex - rear) / 2
            top_full = road == 'N'
            if top_full:
                return [(0, 0), (ex, 0), (ex - off, ny), (off, ny)]
            return [(off, 0), (ex - off, 0), (ex, ny), (0, ny)]
        off = (ny - rear) / 2
        if road == 'W':
            return [(0, 0), (ex, off), (ex, ny - off), (0, ny)]
        return [(0, off), (ex, 0), (ex, ny), (0, ny - off)]
    if shape == 'lshape':
        cw = min(_f(p.get('cut_w'), ex * 0.35), ex * 0.7)
        ch = min(_f(p.get('cut_h'), ny * 0.35), ny * 0.7)
        if road in ('N', 'W'):   # cut the far (south-east) corner
            return [(0, 0), (ex, 0), (ex, ny - ch), (ex - cw, ny - ch), (ex - cw, ny), (0, ny)]
        return [(0, 0), (cw, 0), (cw, ch), (ex, ch), (ex, ny), (0, ny)]  # cut north-west corner
    if shape == 'custom':
        pts = parse_polygon(p.get('points', ''))
        if len(pts) >= 3:
            mx = min(x for x, _ in pts)
            my = min(y for _, y in pts)
            return [(x - mx, y - my) for x, y in pts]
    return rect


def _largest_rect(mask, step):
    """Maximal axis-aligned rectangle in a boolean grid (histogram method)."""
    rows, cols = len(mask), len(mask[0])
    heights = [0] * cols
    best = (0, 0, 0, 0, 0)  # area, r0, c0, r1, c1
    for r in range(rows):
        for c in range(cols):
            heights[c] = heights[c] + 1 if mask[r][c] else 0
        stack = []
        for c in range(cols + 1):
            cur = heights[c] if c < cols else 0
            start = c
            while stack and stack[-1][1] >= cur:
                s, h = stack.pop()
                area = h * (c - s)
                if area > best[0]:
                    best = (area, r - h + 1, s, r + 1, c)
                start = s
            stack.append((start, cur))
    return best


def compute_plot(inp):
    L = _f(inp.get('length'))
    W = _f(inp.get('width'))
    A = _f(inp.get('area'))
    if L > 0 and W > 0:
        pass
    elif A > 0 and L > 0:
        W = A / L
    elif A > 0 and W > 0:
        L = A / W
    elif A > 0:
        L = math.sqrt(A * 1.25)
        W = A / L
    else:
        raise ValueError("Enter plot length and width, or the total area.")
    if min(L, W) < 12 or max(L, W) > 400:
        raise ValueError("Plot dimensions look unrealistic (each side must be between 12 and 400 ft).")

    north = inp.get('north_pos', 'up')
    ex, ny = (L, W) if north in ('up', 'down') else (W, L)   # E-W extent, N-S extent (north always up)
    road = (inp.get('road') or 'N').upper()[:1]
    if road not in 'NESW':
        road = 'N'
    shape = inp.get('shape', 'rectangle')
    poly = _shape_polygon(shape, ex, ny, road, inp.get('shape_params') or {})
    if shape == 'custom' and len(poly) >= 3:
        ex = max(x for x, _ in poly)
        ny = max(y for _, y in poly)
    plot_area = polygon_area(poly)

    usage = inp.get('usage', 'residential')
    for lim, (fr, re_, sd) in SETBACK_TABLE:
        if plot_area <= lim:
            break
    sb = inp.get('setbacks') or {}
    front = _f(sb.get('front'), fr) if sb.get('front') not in (None, '') else fr
    rear = _f(sb.get('rear'), re_) if sb.get('rear') not in (None, '') else re_
    side = _f(sb.get('side'), sd) if sb.get('side') not in (None, '') else sd
    if usage == 'commercial':
        front, rear, side = front + 3, rear + 2, side + 1
    max_cov = _f(inp.get('max_coverage'), 70 if usage == 'residential' else 65) / 100.0

    def side_val(compass, f, r, s):
        if compass == road:
            return f
        if compass == ROAD_OPP[road]:
            return r
        return s

    x0, x1 = side_val('W', front, rear, side), ex - side_val('E', front, rear, side)
    y0, y1 = side_val('N', front, rear, side), ny - side_val('S', front, rear, side)
    note = []
    if shape != 'rectangle':
        step = 1.0
        nx, nyc = int((x1 - x0) / step), int((y1 - y0) / step)
        if nx < 4 or nyc < 4:
            raise ValueError("Plot is too small after setbacks.")
        edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
        margin = min(side, front, rear) * 0.6
        mask = []
        for r in range(nyc):
            row = []
            for c in range(nx):
                px, py = x0 + (c + 0.5) * step, y0 + (r + 0.5) * step
                ok = point_in_polygon(px, py, poly) and all(dist_point_segment(px, py, a, b) >= margin for a, b in edges)
                row.append(ok)
            mask.append(row)
        area, r0, c0, r1, c1 = _largest_rect(mask, step)
        if area < 100:
            raise ValueError("No usable rectangular building area fits inside this plot shape after setbacks.")
        x0, x1, y0, y1 = x0 + c0 * step, x0 + c1 * step, y0 + r0 * step, y0 + r1 * step
        note.append("Building footprint is the largest rectangle that fits inside the custom plot shape.")

    # snap inward to 0.5 ft grid
    x0, y0 = math.ceil(x0 * 2) / 2, math.ceil(y0 * 2) / 2
    x1, y1 = math.floor(x1 * 2) / 2, math.floor(y1 * 2) / 2
    bw, bh = x1 - x0, y1 - y0
    if bw < 12 or bh < 12:
        raise ValueError("Buildable area after setbacks is too small (need at least 12 x 12 ft). "
                         "Reduce setbacks or use a larger plot.")
    if bw * bh > max_cov * plot_area:
        scale = (max_cov * plot_area) / (bw * bh)
        if road in ('N', 'S'):
            nh = math.floor(bh * scale * 2) / 2
            y0, y1 = (y0, y0 + nh) if road == 'N' else (y1 - nh, y1)
            bh = nh
        else:
            nw = math.floor(bw * scale * 2) / 2
            x0, x1 = (x0, x0 + nw) if road == 'W' else (x1 - nw, x1)
            bw = nw
        note.append(f"Rear setback increased to respect the {max_cov*100:.0f}% ground-coverage limit.")
        if bw < 12 or bh < 12:
            raise ValueError("Coverage limit leaves too little buildable area.")

    floors = int(_f(inp.get('floors'), 1)) or 1
    footprint = bw * bh
    total_built = footprint * (floors + (1 if inp.get('basement') else 0))
    return {
        'ex': ex, 'ny': ny, 'road': road, 'shape': shape, 'polygon': [list(p) for p in poly],
        'usage': usage, 'city': inp.get('city', ''),
        'areas': {'sqft': round(plot_area, 2), 'sqm': round(plot_area * SQFT_TO_SQM, 2),
                  'sqyd': round(plot_area * SQFT_TO_SQYD, 2), 'sqm_note': '1 sq ft = 0.0929 sq m'},
        'setbacks': {'front': front, 'rear': rear, 'side': side},
        'buildable': {'x': x0, 'y': y0, 'w': bw, 'h': bh},
        'buildable_area': round(footprint, 2),
        'construction_area_available': round(total_built, 2),
        'open_space': round(plot_area - footprint, 2),
        'coverage_pct': round(100 * footprint / plot_area, 1),
        'far': round(total_built / plot_area, 2),
        'max_coverage_pct': round(max_cov * 100),
        'notes': note,
    }
