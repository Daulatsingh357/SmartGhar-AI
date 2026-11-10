"""Dimension-based house layout generator.

Rooms are placed with a slicing (band) partition of the buildable rectangle, so rooms tile the
footprint exactly with no overlaps and every coordinate is a real feet value snapped to 0.5 ft.
A staircase strip is carved first so the stair sits at the same place on every floor."""
import heapq
import math
from .geom import snap, shared_wall, wall_len, opening_point, EPS
from . import vastu as V

SPEC = {
    'living':    dict(label='Living Room', area=224, short=9, prio=10, cat='living'),
    'master':    dict(label='Master Bedroom', area=196, short=9, prio=9, cat='sleeping'),
    'guest':     dict(label='Guest Bedroom', area=144, short=8, prio=6, cat='sleeping'),
    'kids':      dict(label="Children's Bedroom", area=132, short=8, prio=7, cat='sleeping'),
    'kitchen':   dict(label='Kitchen', area=110, short=6, prio=9, cat='service'),
    'dining':    dict(label='Dining Room', area=120, short=7, prio=8, cat='living'),
    'bathroom':  dict(label='Bathroom', area=40, short=4.5, prio=8, cat='wet'),
    'toilet':    dict(label='Toilet', area=24, short=3.5, prio=5, cat='wet'),
    'pooja':     dict(label='Pooja Room', area=25, short=3.5, prio=5, cat='service'),
    'balcony':   dict(label='Balcony', area=40, short=3.5, prio=2, cat='outdoor'),
    'parking':   dict(label='Parking', area=180, short=9, prio=7, cat='parking'),
    'garden':    dict(label='Garden', area=0, short=0, prio=0, cat='outdoor'),
    'staircase': dict(label='Staircase', area=80, short=7, prio=10, cat='circulation'),
    'store':     dict(label='Store Room', area=48, short=3.5, prio=3, cat='service'),
    'utility':   dict(label='Utility Room', area=35, short=3.5, prio=2, cat='service'),
    'lounge':    dict(label='Family Lounge', area=110, short=7, prio=4, cat='living'),
    'lobby':     dict(label='Stair Lobby', area=40, short=4, prio=1, cat='circulation'),
    'hall':      dict(label='Basement Hall', area=200, short=8, prio=4, cat='living'),
    'headroom':  dict(label='Staircase Headroom', area=80, short=7, prio=1, cat='circulation'),
}
SMALL = {'bathroom', 'toilet', 'pooja', 'store', 'utility', 'balcony', 'lobby'}
DROP_ORDER = ['utility', 'store', 'balcony', 'lounge', 'toilet', 'guest', 'parking', 'pooja', 'kids', 'dining']
FLOOR_NAMES = ['Ground Floor', 'First Floor', 'Second Floor', 'Third Floor']
FLOOR_H = 10.0
BASEMENT_H = 9.0
EXT_T, INT_T = 0.75, 0.375


class Infeasible(Exception):
    pass


# ----------------------------------------------------------------------------- programme
def normalise_rooms(inp):
    counts, dims = {}, {}
    for r in inp.get('rooms') or []:
        t = r.get('type')
        if t not in SPEC or t in ('lobby', 'hall', 'headroom'):
            continue
        n = int(float(r.get('count', 1) or 0))
        if n <= 0:
            continue
        counts[t] = counts.get(t, 0) + n
        w, h = float(r.get('w') or 0), float(r.get('h') or 0)
        if w > 0 and h > 0 and t not in dims:
            dims[t] = (w, h)
    return counts, dims


def mk(t, counts_dims, name=None, idx=1, total=1, road='N'):
    sp = SPEC[t]
    area, short = sp['area'], sp['short']
    dims = counts_dims.get(t)
    if dims:
        area, short = dims[0] * dims[1], min(short, min(dims) * 0.9)
    if t == 'parking' and total > 1:
        area = area * 1  # per car bay handled by caller
    nm = name or sp['label']
    if name is None and total > 1:
        nm = f"{sp['label']} {idx}"
    d = {'type': t, 'name': nm, 'area': float(area), 'short': float(short), 'prio': sp['prio'],
         'cat': sp['cat'], 'req_dims': dims}
    d['min_dx'] = d['min_dy'] = float(short)
    return d


def build_program(inp, road):
    counts, dims = normalise_rooms(inp)
    nfl = max(1, min(4, int(float(inp.get('floors', 1) or 1))))
    basement = bool(inp.get('basement'))
    terrace = inp.get('terrace', True)
    floors = []

    def new_floor(i, kind, name):
        floors.append({'index': i, 'kind': kind, 'name': name, 'specs': []})
        return floors[-1]

    mkr = lambda t, **k: mk(t, dims, road=road, **k)
    if basement:
        b = new_floor(-1, 'basement', 'Basement')
    ground = new_floor(0, 'ground', FLOOR_NAMES[0])
    uppers = [new_floor(i, 'upper', FLOOR_NAMES[i]) for i in range(1, nfl)]

    def add(fl, t, n=1, names=None):
        for i in range(n):
            fl['specs'].append(mkr(t, idx=i + 1, total=n, name=(names[i] if names else None)))

    for t in ('living', 'dining', 'kitchen', 'pooja', 'store', 'utility'):
        add(ground, t, counts.get(t, 0))
    # parking
    pk = counts.get('parking', 0)
    if pk:
        spk = mkr('parking')
        spk['area'] = spk['area'] * pk
        if road in 'NS':
            spk['min_dx'], spk['min_dy'] = 9.0 * pk, 15.0
        else:
            spk['min_dx'], spk['min_dy'] = 15.0, 9.0 * pk
        spk['cars'] = pk
        (floors[0] if basement else ground)['specs'].append(spk)
    # bedrooms
    beds = []
    for t in ('master', 'guest', 'kids'):
        beds += [(t, i + 1, counts.get(t, 0)) for i in range(counts.get(t, 0))]
    if nfl == 1:
        ground_beds, up_beds = beds, [[] for _ in uppers]
    else:
        ground_beds = [x for x in beds if x[0] == 'guest']
        rest = [x for x in beds if x[0] != 'guest']
        up_beds = [[] for _ in uppers]
        masters = [x for x in rest if x[0] == 'master']
        kids = [x for x in rest if x[0] == 'kids']
        for x in masters:
            up_beds[0].append(x)
        for j, x in enumerate(kids):
            up_beds[j % len(uppers)].append(x)
    for (t, i, tot) in ground_beds:
        ground['specs'].append(mkr(t, idx=i, total=tot))
    for fl, bl in zip(uppers, up_beds):
        for (t, i, tot) in bl:
            fl['specs'].append(mkr(t, idx=i, total=tot))
    # wet rooms
    B, T = counts.get('bathroom', 0), counts.get('toilet', 0)
    if nfl == 1:
        add(ground, 'bathroom', B)
        add(ground, 'toilet', T)
    else:
        gb = min(B, len(ground_beds))
        pool = B - gb
        add(ground, 'bathroom', gb)
        for fl, bl in zip(uppers, up_beds):
            n = min(pool, len(bl))
            add(fl, 'bathroom', n)
            pool -= n
        if pool > 0:
            add(uppers[0], 'bathroom', pool)
        if T:
            add(ground, 'toilet', 1)
            for j in range(T - 1):
                add(uppers[j % len(uppers)], 'toilet', 1)
    # balconies
    bal = counts.get('balcony', 0)
    for j in range(bal):
        add(uppers[j % len(uppers)] if uppers else ground, 'balcony', 1, names=[f"Balcony {j + 1}" if bal > 1 else 'Balcony'])
    # lounge on upper floors
    for fl in uppers:
        fl['specs'].append(mkr('lounge'))
    if basement:
        bs = floors[0]
        if not any(s['type'] == 'parking' for s in bs['specs']):
            pass
        bs['specs'] += [mkr('hall'), mkr('store'), mkr('utility')]
    # stairs and terrace
    need_stair = counts.get('staircase', 0) > 0 or nfl > 1 or basement
    garden = counts.get('garden', 0) > 0
    if terrace:
        floors.append({'index': nfl, 'kind': 'terrace', 'name': 'Terrace', 'specs': []})
    return floors, need_stair, garden, counts


# ----------------------------------------------------------------------------- band layout
def solve_sizes(items, total):
    """items: list of (target, minimum). Returns sizes summing to total, honouring minimums where possible."""
    n = len(items)
    fixed = [False] * n
    out = [0.0] * n
    while True:
        free = [i for i in range(n) if not fixed[i]]
        if not free:
            break
        rem = total - sum(out[i] for i in range(n) if fixed[i])
        tsum = sum(items[i][0] for i in free) or 1.0
        changed = False
        for i in free:
            v = rem * items[i][0] / tsum
            if v < items[i][1] - 1e-9:
                out[i] = items[i][1]
                fixed[i] = True
                changed = True
        if not changed:
            for i in free:
                out[i] = rem * items[i][0] / tsum
            break
    s = sum(out)
    if s > total + 1e-6:
        out = [v * total / s for v in out]
    return out


def make_cells(band):
    band = sorted(band, key=lambda s: (s['pref'][1], -s['prio']))
    cells, i = [], 0
    while i < len(band):
        a = band[i]
        if (a['type'] in SMALL and i + 1 < len(band) and band[i + 1]['type'] in SMALL
                and a['area'] + band[i + 1]['area'] <= 130):
            cells.append([a, band[i + 1]])
            i += 2
        else:
            cells.append([a])
            i += 1
    return cells


def _cell_min_w(c):
    return max(s['min_dx'] for s in c)


def _cell_min_h(c):
    return sum(s['min_dy'] for s in c)


def _partition_cost(bands, W, H):
    """Feasibility + proportion cost of a band partition (None if rooms cannot fit)."""
    cells_per = [make_cells(b) for b in bands]
    for cells in cells_per:
        if sum(_cell_min_w(c) for c in cells) > W + 1e-6:
            return None
    minh = [max(_cell_min_h(c) for c in cells) for cells in cells_per]
    if sum(minh) > H + 1e-6:
        return None
    heights = solve_sizes([(sum(s['area'] for s in b), mh) for b, mh in zip(bands, minh)], H)
    cost = 0.0
    for cells, bh in zip(cells_per, heights):
        widths = solve_sizes([(sum(s['area'] for s in c), _cell_min_w(c)) for c in cells], W)
        for c, cw in zip(cells, widths):
            ca = sum(s['area'] for s in c) or 1.0
            for s in c:
                rh = max(bh * s['area'] / ca, 0.1)
                asp = max(cw / rh, rh / max(cw, 0.1))
                cost += s['area'] * (math.log(asp) ** 2)
    return cost


def _best_bands(order, W, H):
    n = len(order)
    best, best_c = None, None
    if n <= 14:
        for mask in range(1 << (n - 1)):
            bands, cur = [], [order[0]]
            for i in range(1, n):
                if mask >> (i - 1) & 1:
                    bands.append(cur)
                    cur = []
                cur.append(order[i])
            bands.append(cur)
            c = _partition_cost(bands, W, H)
            if c is not None and (best_c is None or c < best_c):
                best, best_c = bands, c
    else:  # greedy fallback for very large programmes
        total = sum(s['area'] for s in order)
        mean = total / n
        per = max(1, int(round(W / math.sqrt(max(mean, 30.0) * 1.25))))
        for k in range(max(1, int(math.ceil(n / per))), 0, -1):
            bands, cur, cum = [], [], 0.0
            for s in order:
                if cur and cum + s['area'] / 2 > total / k * (len(bands) + 1) and len(bands) < k - 1:
                    bands.append(cur)
                    cur = []
                cur.append(s)
                cum += s['area']
            bands.append(cur)
            c = _partition_cost(bands, W, H)
            if c is not None:
                return bands
    return best


def layout_rect(rect, specs):
    """rect=(x,y,w,h) canonical. Each spec has pref=(row,col). Returns list of room dicts."""
    X, Y, W, H = rect
    if not specs:
        return []
    specs = [dict(s) for s in specs]
    for s in specs:   # cars can be parked in either orientation: rotate if the long side does not fit
        if s.get('cars'):
            if s['min_dx'] > W * 0.95 and s['min_dy'] <= W:
                s['min_dx'], s['min_dy'] = s['min_dy'], s['min_dx']
            elif s['min_dy'] > H * 0.95 and s['min_dx'] <= H:
                s['min_dx'], s['min_dy'] = s['min_dy'], s['min_dx']
    order = sorted(specs, key=lambda s: (s['pref'][0], s['pref'][1], -s['prio']))
    bands = _best_bands(order, W, H)
    if not bands:
        raise Infeasible(min(specs, key=lambda s: s['prio'])['name'])
    band_cells = [make_cells(b) for b in bands]
    heights = solve_sizes([(sum(s['area'] for s in b), max(_cell_min_h(c) for c in cells))
                           for b, cells in zip(bands, band_cells)], H)
    rooms = []
    y_cum = 0.0
    for bi, (cells, bh) in enumerate(zip(band_cells, heights)):
        y_top = Y + snap(y_cum) if bi else Y
        y_cum += bh
        y_bot = Y + snap(y_cum) if bi < len(bands) - 1 else Y + H
        widths = solve_sizes([(sum(s['area'] for s in c), _cell_min_w(c)) for c in cells], W)
        x_cum = 0.0
        for ci, (cell, cw) in enumerate(zip(cells, widths)):
            x_l = X + snap(x_cum) if ci else X
            x_cum += cw
            x_r = X + snap(x_cum) if ci < len(cells) - 1 else X + W
            ch = y_bot - y_top
            hs = solve_sizes([(s['area'], s['min_dy']) for s in cell], ch)
            yy, acc = y_top, 0.0
            for si, (s, hh) in enumerate(zip(cell, hs)):
                acc += hh
                y2 = y_top + snap(acc) if si < len(cell) - 1 else y_bot
                rooms.append({**s, 'x': x_l, 'y': yy, 'w': x_r - x_l, 'h': y2 - yy})
                yy = y2
    return rooms


def _T(r):
    return {**r, 'x': r['y'], 'y': r['x'], 'w': r['h'], 'h': r['w']}


def _swap_dims(s):
    s = dict(s)
    s['min_dx'], s['min_dy'] = s['min_dy'], s['min_dx']
    return s


def distribute(specs, regions):
    if len(regions) == 1:
        return [specs]
    sp = sorted(specs, key=lambda s: (s['pref'][0], s['pref'][1], -s['prio']))
    tot = sum(x['area'] for x in sp) or 1.0
    areas = [r[2] * r[3] for r in regions]
    A = sum(areas)
    out = [[] for _ in regions]
    cum, idx = 0.0, 0
    for sp_ in sp:
        share = sum(areas[:idx + 1]) / A * tot
        if idx < len(regions) - 1 and out[idx] and cum + sp_['area'] / 2 > share:
            idx += 1
        out[idx].append(sp_)
        cum += sp_['area']
    for i in range(len(out)):
        if not out[i]:
            j = max(range(len(out)), key=lambda j: len(out[j]))
            if len(out[j]) > 1:
                out[i].append(out[j].pop(0 if i < j else -1))
    return out


def place_floor(canon, strip, specs, floor_kind, transposed):
    """Lay out one floor in canonical frame; returns rooms in canonical coordinates.
    The stair block (stair + one service room) sits in a corner; the rest of the footprint is split into
    at most two rectangles that are laid out independently, so everything tiles exactly."""
    X, Y, W, H = canon
    rooms = []
    specs = [dict(s) for s in specs]
    regions = [(X, Y, W, H)]
    if strip:
        sw, sl = strip['sw'], strip['sl']
        side, end = strip['side'], strip['end']
        stair_t = 'headroom' if floor_kind == 'terrace' else 'staircase'
        sx = X if side == 'W' else X + W - sw
        svc_h = min(H - sl, 8.0) if H - sl >= 5 else 0.0
        Hs = sl + svc_h if svc_h else H
        if svc_h and H - Hs < 6:
            svc_h, Hs = H - sl, H
        y_zone = Y if end == 'N' else Y + H - Hs
        sy = y_zone if end == 'N' else y_zone + Hs - sl
        stair_h = sl if svc_h else H
        if not svc_h:
            sy = Y
        spec = mk(stair_t, {})
        rooms.append({**spec, 'x': sx, 'y': sy, 'w': sw, 'h': stair_h})
        if floor_kind == 'terrace':
            return rooms
        if svc_h:
            svc = None
            for t in ('toilet', 'bathroom', 'store', 'utility'):
                svc = next((s for s in specs if s['type'] == t), None)
                if svc:
                    break
            if svc is None:
                svc = {**mk('lobby', {}), 'name': 'Stair Lobby'}
            else:
                specs.remove(svc)
            svc_y = y_zone + sl if end == 'N' else y_zone
            rooms.append({**svc, 'x': sx, 'y': svc_y, 'w': sw, 'h': svc_h})
        zone_main = (X + sw if side == 'W' else X, y_zone, W - sw, Hs)
        other = (X, Y + Hs if end == 'N' else Y, W, H - Hs) if H - Hs >= 6 else None
        regions = [zone_main] + ([other] if other else []) if end == 'N' else ([other] if other else []) + [zone_main]
    if floor_kind == 'terrace':
        return rooms
    subs = distribute(specs, regions)
    for attempt in range(10):
        laid, failed = [], None
        for i, (reg, sub) in enumerate(zip(regions, subs)):
            if not sub:
                laid.append([{**mk('lobby', {}), 'name': 'Passage', 'x': reg[0], 'y': reg[1], 'w': reg[2], 'h': reg[3]}])
                continue
            try:
                laid.append(layout_rect(tuple(reg), sub))
            except Infeasible:
                failed = i
                break
        if failed is None:
            for part in laid:
                rooms += part
            return rooms
        if len(regions) == 1:
            raise Infeasible('region')
        # move the biggest-minimum room of the failing region into the roomier region
        other = max((j for j in range(len(regions)) if j != failed),
                    key=lambda j: regions[j][2] * regions[j][3] - sum(x['area'] for x in subs[j]))
        if len(subs[failed]) <= 1:
            raise Infeasible('region')
        mv = max(subs[failed], key=lambda x: x['min_dx'] * x['min_dy'])
        subs[failed].remove(mv)
        subs[other].append(mv)
    raise Infeasible('region')


def generate_option(inp, plot, variant, mode):
    road = plot['road']
    b = plot['buildable']
    floors_prog, need_stair, garden, counts = build_program(inp, road)
    transposed = variant['transposed']
    canon = (b['y'], b['x'], b['h'], b['w']) if transposed else (b['x'], b['y'], b['w'], b['h'])
    croad = {'N': 'W', 'S': 'E', 'E': 'S', 'W': 'N'}[road] if transposed else road
    warnings = []

    strip = None
    if need_stair:
        W, H = (canon[2], canon[3])
        sw = 8.0 if W >= 22 else 7.0
        if W < 14 or H < 12:
            raise ValueError("Plot is too narrow for a staircase. Remove the stairs or enlarge the plot.")
        strip = {'sw': sw, 'sl': 10.0 if H >= 16 else H, 'side': variant['strip_side'], 'end': variant['stair_end']}

    # capacity check: push movable rooms to the next floor up when a floor is over-full
    Wm = (canon[2] - (strip['sw'] if strip else 0))
    avail = Wm * canon[3]
    MOVABLE = ['store', 'utility', 'guest', 'toilet', 'balcony', 'kids']
    living_floors = [f for f in floors_prog if f['kind'] in ('ground', 'upper')]
    for fi, fl in enumerate(living_floors[:-1]):
        nxt = living_floors[fi + 1]
        while sum(s['area'] for s in fl['specs']) > avail * 1.3:
            cand = next((s for t in MOVABLE for s in fl['specs'] if s['type'] == t), None)
            if cand is None:
                break
            fl['specs'].remove(cand)
            nxt['specs'].append(cand)

    out_floors = []
    for fl in floors_prog:
        specs = fl['specs']
        for s in specs:
            s['pref'] = V.pref(s['type'], mode, road, variant.get('alt', False), 0)
            if transposed:
                s['pref'] = (s['pref'][1], s['pref'][0])
                s.update(_swap_dims(s))
        dropped = []
        placed = None
        for _ in range(12):
            try:
                placed = place_floor(canon, strip if need_stair else None, specs, fl['kind'], transposed)
                break
            except Infeasible as e:
                cand = None
                for t in DROP_ORDER:
                    cand = next((s for s in specs if s['type'] == t), None)
                    if cand:
                        break
                if cand is None:
                    cand = min(specs, key=lambda s: s['prio'])
                specs.remove(cand)
                dropped.append(cand['name'])
        if placed is None:
            raise ValueError("Could not fit the requested rooms in this plot. Reduce rooms or increase the plot size.")
        if dropped:
            warnings.append(f"{fl['name']}: not enough space, left out {', '.join(dropped)}.")
        rooms = []
        for i, r in enumerate(placed):
            rr = _T(r) if transposed else dict(r)
            rr['id'] = f"f{fl['index']}r{i}"
            rr['target_area'] = round(rr.get('area', 0), 1)
            for k in ('pref', 'min_dx', 'min_dy', 'area', 'short', 'prio', 'req_dims'):
                rr.pop(k, None)
            rooms.append(rr)
        out_floors.append({'index': fl['index'], 'kind': fl['kind'], 'name': fl['name'], 'rooms': rooms})

    # garden in the front setback
    sbk = plot['setbacks']['front']
    if garden:
        ex, ny = plot['ex'], plot['ny']
        if sbk >= 3.5:
            g = {'N': (0, 0, ex, b['y']), 'S': (0, b['y'] + b['h'], ex, ny - b['y'] - b['h']),
                 'E': (b['x'] + b['w'], 0, ex - b['x'] - b['w'], ny), 'W': (0, 0, b['x'], ny)}[road]
            ground = next(f for f in out_floors if f['kind'] == 'ground')
            ground['rooms'].append({'id': 'garden0', 'type': 'garden', 'name': 'Garden', 'x': g[0], 'y': g[1],
                                    'w': g[2], 'h': g[3], 'outdoor': True, 'cat': 'outdoor', 'target_area': g[2] * g[3]})
        else:
            warnings.append("Front setback is too small for a garden; a garden was not added.")
    return out_floors, warnings


# ----------------------------------------------------------------------------- doors / windows
HUB_ORDER = ['living', 'lounge', 'hall', 'dining', 'lobby', 'staircase']
PASS_COST = {'living': 1, 'lounge': 1, 'hall': 1, 'lobby': 1, 'dining': 2, 'staircase': 2, 'parking': 3,
             'guest': 15, 'kids': 15, 'master': 15, 'kitchen': 12, 'bathroom': 30, 'toilet': 30, 'pooja': 25,
             'store': 20, 'utility': 12, 'balcony': 25, 'headroom': 5}


def _door_on(child, parent, did, kind='internal', width=3.0):
    sw = shared_wall(child, parent, 2.0)
    if not sw:
        return None
    orient, line, s, e = sw
    width = min(width, e - s - 0.5)
    mid = snap((s + e) / 2.0)
    mid = min(max(mid, s + width / 2 + 0.25), e - width / 2 - 0.25)
    if orient == 'v':
        wall = 'E' if abs(line - (child['x'] + child['w'])) < 1e-3 else 'W'
        t = mid - child['y']
    else:
        wall = 'S' if abs(line - (child['y'] + child['h'])) < 1e-3 else 'N'
        t = mid - child['x']
    return {'id': did, 'room': child['id'], 'wall': wall, 't': round(t, 2), 'width': width,
            'kind': kind, 'to': parent['id']}


def generate_openings(floor, outline, road, mode):
    rooms = [r for r in floor['rooms'] if not r.get('outdoor')]
    doors, windows = [], []
    if not rooms:
        return doors, windows
    by_id = {r['id']: r for r in rooms}
    ground = floor['kind'] == 'ground'
    # hub
    hub = None
    for t in HUB_ORDER:
        hub = next((r for r in rooms if r['type'] == t), None)
        if hub:
            break
    hub = hub or rooms[0]
    # adjacency
    def adj(minlen):
        g = {r['id']: [] for r in rooms}
        for i, a in enumerate(rooms):
            for b in rooms[i + 1:]:
                sw = shared_wall(a, b, minlen)
                if sw:
                    g[a['id']].append((b['id'], sw[3] - sw[2]))
                    g[b['id']].append((a['id'], sw[3] - sw[2]))
        return g
    g = adj(3.5)
    # dijkstra from hub with privacy costs
    def dijkstra(g):
        dist = {hub['id']: 0}
        parent = {}
        pq = [(0, hub['id'])]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e9):
                continue
            for v, _ in g[u]:
                nd = d + PASS_COST.get(by_id[u]['type'], 10)
                if nd < dist.get(v, 1e9):
                    dist[v] = nd
                    parent[v] = u
                    heapq.heappush(pq, (nd, v))
        return parent, dist
    parent, dist = dijkstra(g)
    if len(dist) < len(rooms):
        g = adj(2.5)
        parent, dist = dijkstra(g)
    # overrides
    adj_map = {k: [v for v, _ in vs] for k, vs in g.items()}
    def descendants(rid):
        return {c for c, p in parent.items() if p == rid}
    attached = set()
    for r in rooms:
        if r['type'] in ('bathroom', 'toilet') and not descendants(r['id']):
            cands = [by_id[n] for n in adj_map[r['id']] if by_id[n]['type'] in ('master', 'guest', 'kids')
                     and by_id[n]['id'] not in attached]
            cands.sort(key=lambda c: (c['type'] != 'master', -shared_wall(r, c, 0.1)[3] + shared_wall(r, c, 0.1)[2]))
            if cands and r['type'] == 'bathroom':
                parent[r['id']] = cands[0]['id']
                attached.add(cands[0]['id'])
        elif r['type'] == 'kitchen':
            d = next((by_id[n] for n in adj_map[r['id']] if by_id[n]['type'] == 'dining'), None)
            if d and parent.get(d['id']) != r['id']:
                parent[r['id']] = d['id']
        elif r['type'] == 'pooja':
            d = next((by_id[n] for n in adj_map[r['id']] if by_id[n]['type'] in ('living', 'lounge')), None)
            if d:
                parent[r['id']] = d['id']
        elif r['type'] == 'balcony':
            d = next((by_id[n] for n in adj_map[r['id']] if by_id[n]['type'] in ('master', 'living', 'lounge', 'kids', 'guest')), None)
            if d:
                parent[r['id']] = d['id']
    n = 0
    for rid, pid in parent.items():
        r, p = by_id[rid], by_id[pid]
        wd = 2.5 if r['type'] in ('bathroom', 'toilet', 'store', 'utility') else 3.0
        if r['type'] == 'balcony':
            wd = 3.5
        d = _door_on(r, p, f"d{len(doors)}", 'internal', wd)
        if d:
            doors.append(d)
    # main entrance and parking gate (ground only)
    if ground:
        frac = V.ENTRANCE[road][2]
        wall = road
        def road_edge(r):
            if wall == 'N' and abs(r['y'] - outline['y']) < 1e-3:
                return r['x'], r['x'] + r['w']
            if wall == 'S' and abs(r['y'] + r['h'] - (outline['y'] + outline['h'])) < 1e-3:
                return r['x'], r['x'] + r['w']
            if wall == 'W' and abs(r['x'] - outline['x']) < 1e-3:
                return r['y'], r['y'] + r['h']
            if wall == 'E' and abs(r['x'] + r['w'] - (outline['x'] + outline['w'])) < 1e-3:
                return r['y'], r['y'] + r['h']
            return None
        target = None
        for pref_t in ('living', 'dining', 'guest', 'lounge', 'staircase', 'master', 'kids'):
            for r in rooms:
                if r['type'] != pref_t:
                    continue
                e = road_edge(r)
                if e and e[1] - e[0] >= 4:
                    target = (r, e)
                    break
            if target:
                break
        if target:
            r, (s, e) = target
            if wall in 'NS':
                full0, full1 = outline['x'], outline['x'] + outline['w']
            else:
                full0, full1 = outline['y'], outline['y'] + outline['h']
            pos = full0 + frac * (full1 - full0)
            wd = 3.5
            c = min(max(snap(pos), s + wd / 2 + 0.5), e - wd / 2 - 0.5)
            base = r['x'] if wall in 'NS' else r['y']
            doors.append({'id': 'main', 'room': r['id'], 'wall': wall, 't': round(c - base, 2), 'width': wd,
                          'kind': 'main', 'to': 'outside'})
        for r in rooms:
            if r['type'] == 'parking':
                e = road_edge(r)
                if e:
                    wd = min(e[1] - e[0] - 1.0, 9.0 * r.get('cars', 1) if 'cars' in r else 9.0, 16.0)
                    c = (e[0] + e[1]) / 2
                    base = r['x'] if wall in 'NS' else r['y']
                    doors.append({'id': f"gate{r['id']}", 'room': r['id'], 'wall': wall, 't': round(c - base, 2),
                                  'width': max(wd, 6.0), 'kind': 'gate', 'to': 'outside'})
    # windows on exterior walls
    ox, oy, ow, oh = outline['x'], outline['y'], outline['w'], outline['h']
    def blocked(r, wall, c, wd):
        for d in doors:
            if d['room'] == r['id'] and d['wall'] == wall and abs(d['t'] - c) < (d['width'] + wd) / 2 + 0.5:
                return True
        return False
    no_win = {'pooja', 'balcony', 'parking', 'lobby', 'hall', 'headroom'}
    for r in rooms:
        if r['type'] in no_win:
            continue
        walls = []
        if abs(r['y'] - oy) < 1e-3: walls.append('N')
        if abs(r['y'] + r['h'] - (oy + oh)) < 1e-3: walls.append('S')
        if abs(r['x'] - ox) < 1e-3: walls.append('W')
        if abs(r['x'] + r['w'] - (ox + ow)) < 1e-3: walls.append('E')
        small = r['type'] in ('bathroom', 'toilet', 'store', 'utility')
        wd = 2.0 if small else 3.0 if r['type'] in ('kitchen', 'staircase') else 4.0
        sill = 5.0 if small else 3.0
        for w in walls:
            L = wall_len(r, w)
            if L < wd + 1.5:
                continue
            spots = [L / 2] if L < 13 else [L * 0.28, L * 0.72]
            for c in spots:
                c = snap(c)
                if blocked(r, w, c, wd):
                    alt = c + (wd + 1.0) * (1 if c < L / 2 else -1)
                    if wd / 2 + 0.5 <= alt <= L - wd / 2 - 0.5 and not blocked(r, w, alt, wd):
                        c = alt
                    else:
                        continue
                windows.append({'id': f"w{len(windows)}", 'room': r['id'], 'wall': w, 't': round(c, 2),
                                'width': wd, 'sill': sill, 'head': 7.0})
    return doors, windows
