"""Rule-based furniture placement (feet, plot coordinates). Also produces stair, electrical and plumbing data."""
from .geom import opening_point, inward, wall_len

CLEAR = 3.0  # door clearance depth (ft)


def _door_zones(room, doors):
    zs = []
    for d in doors:
        if d['room'] != room['id']:
            continue
        x, y, o = opening_point(room, d['wall'], d['t'])
        hw = d['width'] / 2 + 0.3
        if o == 'h':
            zs.append((x - hw, y if d['wall'] == 'N' else y - CLEAR, 2 * hw, CLEAR))
        else:
            zs.append((x if d['wall'] == 'W' else x - CLEAR, y - hw, CLEAR, 2 * hw))
    # doors of other rooms opening into this one
    return zs


def _hit(a, b):
    return not (a[0] + a[2] <= b[0] + 1e-6 or b[0] + b[2] <= a[0] + 1e-6 or
                a[1] + a[3] <= b[1] + 1e-6 or b[1] + b[3] <= a[1] + 1e-6)


class Placer:
    def __init__(self, room, doors, all_doors):
        self.r = room
        self.items = []
        self.zones = _door_zones(room, doors)
        for d in all_doors:
            if d.get('to') == room['id']:
                pass
        self.occ = []

    def _free(self, rect):
        r = self.r
        if rect[0] < r['x'] - 1e-6 or rect[1] < r['y'] - 1e-6 or \
                rect[0] + rect[2] > r['x'] + r['w'] + 1e-6 or rect[1] + rect[3] > r['y'] + r['h'] + 1e-6:
            return False
        return not any(_hit(rect, z) for z in self.zones + self.occ)

    def put(self, kind, rect, **kw):
        if not self._free(rect):
            return False
        self.occ.append(rect)
        self.items.append({'kind': kind, 'x': round(rect[0], 2), 'y': round(rect[1], 2),
                           'w': round(rect[2], 2), 'h': round(rect[3], 2), **kw})
        return True

    def along(self, wall, length, depth, kind, offset=0.5, **kw):
        """Place a (length x depth) item against `wall`; offset: 0..1 position along the wall (0.5 = centred)."""
        r = self.r
        L = wall_len(r, wall)
        if length > L:
            return False
        for off in ([offset] if offset is not None else []) + [0.1, 0.9, 0.3, 0.7]:
            c = r['x' if wall in 'NS' else 'y'] + length / 2 + off * (L - length)
            if wall == 'N':
                rect = (c - length / 2, r['y'], length, depth)
            elif wall == 'S':
                rect = (c - length / 2, r['y'] + r['h'] - depth, length, depth)
            elif wall == 'W':
                rect = (r['x'], c - length / 2, depth, length)
            else:
                rect = (r['x'] + r['w'] - depth, c - length / 2, depth, length)
            if self.put(kind, rect, wall=wall, **kw):
                return True
        return False


def _walls_by_length(r):
    return sorted('NSWE', key=lambda w: -wall_len(r, w))


def _opposite(w):
    return {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[w]


def furnish_room(room, doors, windows):
    t = room['type']
    p = Placer(room, doors, [])
    ws = _walls_by_length(room)
    win_walls = {w['wall'] for w in windows if w['room'] == room['id']}
    if t in ('master', 'guest', 'kids'):
        bw, bl = (6.0, 6.5) if t == 'master' else (5.0, 6.5) if t == 'guest' else (3.5, 6.5)
        placed = False
        for w in ws:
            if w in win_walls and len(win_walls) < 4 and w != ws[-1]:
                pass
            # bed with its head on wall w, bed length perpendicular
            if p.along(w, bw, bl, 'bed', 0.5):
                placed = True
                b = p.items[-1]
                if t != 'kids':
                    for side in (-1, 1):
                        if w in 'NS':
                            x = b['x'] - 1.5 if side < 0 else b['x'] + b['w']
                            p.put('sidetable', (x, b['y'] if w == 'N' else b['y'] + b['h'] - 1.5, 1.5, 1.5))
                        else:
                            y = b['y'] - 1.5 if side < 0 else b['y'] + b['h']
                            p.put('sidetable', (b['x'] if w == 'W' else b['x'] + b['w'] - 1.5, y, 1.5, 1.5))
                break
        for w in ws:
            if p.along(w, 5.0 if t != 'kids' else 4.0, 2.0, 'wardrobe', 0.5):
                break
        if t == 'kids':
            for w in ws:
                if p.along(w, 4.0, 2.0, 'desk', 0.5):
                    break
        elif room['w'] * room['h'] > 140:
            for w in ws:
                if p.along(w, 3.0, 1.5, 'dresser', 0.5):
                    break
    elif t in ('living', 'lounge'):
        sofa_w = 7.0 if room['w'] * room['h'] > 100 else 6.0
        for w in ws:
            if p.along(w, sofa_w, 3.0, 'sofa', 0.5):
                s = p.items[-1]
                opp = _opposite(w)
                p.along(opp, 4.5, 1.5, 'tv', 0.5)
                cx, cy = s['x'] + s['w'] / 2, s['y'] + s['h'] / 2
                if w in 'NS':
                    ty = s['y'] + 3.7 if w == 'N' else s['y'] - 2.7
                    p.put('coffee_table', (cx - 1.5, ty, 3.0, 2.0))
                else:
                    tx = s['x'] + 3.7 if w == 'W' else s['x'] - 2.7
                    p.put('coffee_table', (tx, cy - 1.5, 2.0, 3.0))
                break
        if room['w'] * room['h'] > 180:
            for w in ws:
                if p.along(w, 2.5, 2.5, 'armchair', 0.15):
                    break
    elif t == 'dining':
        tw, td = 6.0, 3.5
        cx, cy = room['x'] + room['w'] / 2, room['y'] + room['h'] / 2
        if room['w'] < tw + 3 and room['h'] >= tw + 3:
            tw, td = td, tw
        p.put('dining_table', (cx - tw / 2, cy - td / 2, tw, td))
        if tw >= td:
            for i in range(3):
                x = cx - tw / 2 + 0.6 + i * 1.7
                p.put('chair', (x, cy - td / 2 - 1.4, 1.3, 1.3)); p.put('chair', (x, cy + td / 2 + 0.1, 1.3, 1.3))
        else:
            for i in range(3):
                y = cy - td / 2 + 0.6 + i * 1.7
                p.put('chair', (cx - tw / 2 - 1.4, y, 1.3, 1.3)); p.put('chair', (cx + tw / 2 + 0.1, y, 1.3, 1.3))
    elif t == 'kitchen':
        done = 0
        for w in ws:
            L = wall_len(room, w)
            if done == 0 and p.along(w, min(L - 0.5, 11.0), 2.0, 'counter', 0.5):
                c = p.items[-1]
                if w in 'NS':
                    p.put('sink', (c['x'] + 1.0, c['y'] + (0.2 if w == 'N' else 0.3), 2.0, 1.5))
                    p.put('stove', (c['x'] + c['w'] - 3.0, c['y'] + (0.0 if w == 'N' else 0.0), 2.0, 2.0))
                else:
                    p.put('sink', (c['x'] + 0.2, c['y'] + 1.0, 1.5, 2.0))
                    p.put('stove', (c['x'], c['y'] + c['h'] - 3.0, 2.0, 2.0))
                done = 1
                fw = w
                continue
            if done == 1:
                for w2 in ws:
                    if w2 != fw and w2 != _opposite(fw):
                        if p.along(w2, min(wall_len(room, w2) - 2.5, 6.0), 2.0, 'counter', 0.9):
                            break
                p.along(_opposite(fw), 2.5, 2.5, 'fridge', 0.05)
                break
    elif t in ('bathroom', 'toilet'):
        for w in ws:
            if p.along(w, 1.6, 2.4, 'wc', 0.5):
                break
        for w in ws:
            if p.along(w, 1.6, 1.3, 'basin', 0.85 if wall_len(room, w) > 3.5 else 0.5):
                break
        if t == 'bathroom' and room['w'] >= 5 and room['h'] >= 5:
            r = room
            for rect in ((r['x'], r['y'], 3.0, 3.0), (r['x'] + r['w'] - 3.0, r['y'], 3.0, 3.0),
                         (r['x'], r['y'] + r['h'] - 3.0, 3.0, 3.0), (r['x'] + r['w'] - 3.0, r['y'] + r['h'] - 3.0, 3.0, 3.0)):
                if p.put('shower', rect):
                    break
    elif t == 'pooja':
        for w in ws:
            if p.along(w, min(2.5, room['w'] - 0.5), 1.5, 'mandir', 0.5):
                break
    elif t == 'parking':
        cars = room.get('cars') or max(1, int(room['w'] * room['h'] // 150))
        horiz = room['w'] >= room['h']
        n = max(1, min(cars, int((room['h'] if horiz else room['w']) // 9)))
        for i in range(n):
            if horiz:
                step = room['h'] / n
                p.put('car', (room['x'] + (room['w'] - min(15, room['w'] - 1)) / 2, room['y'] + i * step + (step - 7) / 2,
                              min(15, room['w'] - 1), 7))
            else:
                step = room['w'] / n
                p.put('car', (room['x'] + i * step + (step - 7) / 2, room['y'] + (room['h'] - min(15, room['h'] - 1)) / 2,
                              7, min(15, room['h'] - 1)))
    elif t == 'store':
        for w in ws[:2]:
            p.along(w, min(wall_len(room, w) - 0.5, 6.0), 1.5, 'shelf', 0.5)
    elif t == 'utility':
        for w in ws:
            if p.along(w, 2.0, 2.0, 'washer', 0.2):
                break
        for w in ws:
            if p.along(w, 2.0, 1.5, 'sink', 0.8):
                break
    elif t in ('staircase', 'headroom'):
        horiz = room['w'] > room['h']
        door = next((d for d in doors if d['room'] == room['id']), None)
        start_far = False
        if door:
            x, y, _ = opening_point(room, door['wall'], door['t'])
            if horiz:
                start_far = x > room['x'] + room['w'] / 2
            else:
                start_far = y > room['y'] + room['h'] / 2
        p.items.append({'kind': 'stairs', 'x': room['x'], 'y': room['y'], 'w': room['w'], 'h': room['h'],
                        'axis': 'x' if horiz else 'y', 'start_far': start_far, 'risers': 18 if t == 'staircase' else 0})
    elif t == 'balcony':
        p.along(ws[0], min(wall_len(room, ws[0]) - 1, 3.0), 1.2, 'planter', 0.5)
    return p.items


def electrical(room, doors, windows):
    """Light, fan, switchboard, socket and AC/geyser points for a room."""
    t = room['type']
    pts = []
    if t in ('garden', 'headroom'):
        return pts
    cx, cy = room['x'] + room['w'] / 2, room['y'] + room['h'] / 2
    area = room['w'] * room['h']
    nl = max(1, int(area // 90))
    for i in range(nl):
        pts.append({'kind': 'light', 'x': cx + (i - (nl - 1) / 2) * min(5, room['w'] / nl), 'y': cy})
    if t in ('master', 'guest', 'kids', 'living', 'dining', 'lounge'):
        pts.append({'kind': 'fan', 'x': cx, 'y': cy + (1.5 if area > 110 else 0)})
    if t == 'master':
        pts.append({'kind': 'ac', 'x': room['x'] + room['w'] - 1, 'y': room['y'] + 1})
    if t in ('bathroom', 'toilet', 'kitchen'):
        pts.append({'kind': 'exhaust', 'x': room['x'] + room['w'] - 1, 'y': room['y'] + 1})
    if t == 'bathroom':
        pts.append({'kind': 'geyser', 'x': room['x'] + 1, 'y': room['y'] + 1})
    for d in doors:
        if d['room'] == room['id']:
            x, y, o = opening_point(room, d['wall'], d['t'])
            dx, dy = inward(d['wall'])
            ox, oy = (1.6 if o == 'h' else 0), (1.6 if o == 'v' else 0)
            pts.append({'kind': 'switch', 'x': x + ox + dx * 0.4, 'y': y + oy + dy * 0.4})
            break
    nsock = 1 if area < 60 else 2 if area < 150 else 3
    for i in range(nsock):
        pts.append({'kind': 'socket', 'x': room['x'] + 0.4, 'y': room['y'] + room['h'] * (i + 1) / (nsock + 1)})
    return pts
