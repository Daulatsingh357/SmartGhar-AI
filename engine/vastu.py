"""Vastu Shastra rules, preferred-zone tables and plan scoring.
Vastu guidance is traditional advice, not an engineering requirement."""
from .geom import shared_wall

ZONE_GRID = [['NW', 'N', 'NE'], ['W', 'C', 'E'], ['SW', 'S', 'SE']]
ZONE_RC = {z: (r, c) for r, row in enumerate(ZONE_GRID) for c, z in enumerate(row)}

RULES = {
    'living':   dict(ideal=['N', 'NE', 'E'], ok=['NW', 'W'], avoid=['SW', 'SE'], w=8,
                     why="North/east living areas receive morning light and positive energy flow."),
    'lounge':   dict(ideal=['N', 'NE', 'E', 'C'], ok=['NW', 'W'], avoid=['SW'], w=3,
                     why="Open family spaces suit the centre and north-east."),
    'master':   dict(ideal=['SW'], ok=['S', 'W'], avoid=['NE', 'SE'], w=12,
                     why="South-west is the zone of stability, recommended for the head of the family."),
    'guest':    dict(ideal=['NW'], ok=['N', 'W'], avoid=['SW', 'NE'], w=6,
                     why="North-west suits guests (a zone associated with movement)."),
    'kids':     dict(ideal=['W', 'NW'], ok=['N', 'S'], avoid=['SE', 'NE'], w=6,
                     why="West and north-west support study and growth."),
    'kitchen':  dict(ideal=['SE'], ok=['NW'], avoid=['NE', 'SW', 'N'], w=15,
                     why="South-east is the zone of fire (Agni); cook facing east."),
    'dining':   dict(ideal=['W', 'E'], ok=['N', 'NW', 'C'], avoid=['SW'], w=4,
                     why="Dining next to the kitchen on the west or east side is preferred."),
    'bathroom': dict(ideal=['NW', 'W'], ok=['S', 'SE'], avoid=['NE', 'SW', 'C'], w=6,
                     why="Wet areas belong in north-west/west; avoid north-east and centre."),
    'toilet':   dict(ideal=['NW', 'W'], ok=['S', 'SE'], avoid=['NE', 'SW', 'C'], w=6,
                     why="Toilets should avoid north-east and the central Brahmasthan."),
    'pooja':    dict(ideal=['NE'], ok=['N', 'E'], avoid=['S', 'SW', 'SE', 'NW'], w=12,
                     why="North-east (Ishanya) is the most auspicious zone for worship."),
    'balcony':  dict(ideal=['N', 'NE', 'E'], ok=['NW'], avoid=['SW'], w=2,
                     why="Open north/east balconies capture light and fresh air."),
    'parking':  dict(ideal=['NW', 'SE'], ok=['N', 'E'], avoid=['NE', 'SW'], w=3,
                     why="Vehicles suit the north-west or south-east."),
    'staircase': dict(ideal=['S', 'W', 'SW'], ok=['SE', 'NW'], avoid=['NE', 'C', 'N'], w=8,
                      why="Heavy stair mass is best in the south or west; avoid north-east and the centre."),
    'store':    dict(ideal=['NW', 'SW'], ok=['W', 'S'], avoid=['NE'], w=2,
                     why="Storage suits the heavier north-west/south-west."),
    'utility':  dict(ideal=['NW', 'SE'], ok=['W', 'S'], avoid=['NE'], w=2,
                     why="Washing/utility works in north-west or south-east."),
}

ENTRANCE = {  # road side -> (ideal zones, avoid zones, target fraction along wall (W->E or N->S))
    'N': (['N', 'NE'], ['NW'], 0.78),
    'E': (['E', 'NE'], ['SE'], 0.22),
    'S': (['S', 'SE'], ['SW'], 0.78),
    'W': (['W', 'NW'], ['SW'], 0.22),
}

# ---- preferred (row, col) in a 3x3 grid, row 0 = north, col 0 = west --------------------
IDEAL = {'kitchen': (2, 2), 'master': (2, 0), 'guest': (0, 0), 'kids': (1, 0), 'dining': (1, 0),
         'bathroom': (0, 0), 'toilet': (0, 0), 'pooja': (0, 2), 'balcony': (0, 1), 'lounge': (1, 1),
         'store': (0, 0), 'utility': (2, 2), 'hall': (1, 1), 'lobby': (1, 1)}
ALT = {'kitchen': (0, 0), 'master': (2, 1), 'guest': (0, 1), 'kids': (0, 0), 'dining': (1, 2),
       'bathroom': (2, 1), 'toilet': (1, 0), 'pooja': (0, 1), 'balcony': (0, 2), 'lounge': (1, 1),
       'store': (2, 0), 'utility': (0, 0)}
ROAD_ROW_COL = {'N': (0, 1), 'S': (2, 1), 'E': (1, 2), 'W': (1, 0)}


def pref(rtype, mode, road, alt=False, idx=0):
    """Preferred grid cell for placing a room type."""
    if rtype == 'living':
        if mode == 'normal':
            return ROAD_ROW_COL[road]
        return {'N': (0, 1) if not alt else (0, 2), 'E': (1, 2), 'S': (2, 1) if mode == 'flexible' else (1, 2),
                'W': (1, 0) if mode == 'flexible' else (0, 0)}[road]
    if rtype == 'parking':
        return {'N': (0, 0), 'E': (2, 2), 'S': (2, 2), 'W': (0, 0)}[road] if not alt else \
            {'N': (0, 2), 'E': (0, 2), 'S': (2, 0), 'W': (2, 0)}[road]
    if mode == 'normal':
        func = {'master': (2, 0), 'guest': (2, 2), 'kids': (1, 2), 'kitchen': (1, 0), 'dining': (1, 1),
                'bathroom': (2, 1), 'toilet': (2, 1), 'pooja': (0, 2), 'store': (2, 2), 'utility': (1, 2),
                'lounge': (1, 1)}
        if rtype == 'balcony':
            return ROAD_ROW_COL[road]
        return func.get(rtype, (1, 1))
    if mode == 'flexible' and rtype in ('kids', 'guest', 'dining', 'bathroom', 'toilet', 'store', 'utility', 'balcony') \
            and idx % 2 == 1:
        return ALT.get(rtype, IDEAL.get(rtype, (1, 1)))
    return (ALT if alt else IDEAL).get(rtype, (1, 1)) if (alt and rtype in ALT) or rtype in IDEAL else (1, 1)


def zone_of(cx, cy, rect):
    c = min(2, max(0, int(3 * (cx - rect['x']) / rect['w'])))
    r = min(2, max(0, int(3 * (cy - rect['y']) / rect['h'])))
    return ZONE_GRID[r][c]


def _status(rule, zone):
    if zone in rule['ideal']:
        return 'ideal', 1.0
    if zone in rule['ok']:
        return 'acceptable', 0.65
    if zone in rule['avoid']:
        return 'avoid', 0.0
    return 'neutral', 0.35


def score_plan(plan, road, mode='flexible'):
    """Score every room of a plan. Returns {score, items, entrance, checks, grade}."""
    b = plan['buildable']
    items, total_w, total_p = [], 0.0, 0.0
    groups = {}
    for fl in plan['floors']:
        for r in fl['rooms']:
            rule = RULES.get(r['type'])
            if not rule or r.get('outdoor') and r['type'] == 'garden':
                continue
            zone = zone_of(r['x'] + r['w'] / 2, r['y'] + r['h'] / 2, b)
            st, pts = _status(rule, zone)
            items.append({'room': r['name'], 'type': r['type'], 'floor': fl['name'], 'zone': zone,
                          'status': st, 'points': pts, 'why': rule['why'],
                          'advice': ("Well placed." if st == 'ideal' else
                                     f"Acceptable. Ideal: {', '.join(rule['ideal'])}." if st == 'acceptable' else
                                     f"Move toward {', '.join(rule['ideal'])} if possible." if st == 'avoid' else
                                     f"Neutral placement. Preferred: {', '.join(rule['ideal'])}.")})
            g = 'bath' if r['type'] in ('bathroom', 'toilet') else r['type']
            groups.setdefault(g, []).append((rule['w'], pts))
    for g, vals in groups.items():
        w = max(v[0] for v in vals)
        total_w += w
        total_p += w * sum(v[1] for v in vals) / len(vals)

    # entrance
    ent = None
    ground = next((f for f in plan['floors'] if f['kind'] == 'ground'), None)
    ideal, avoid, _ = ENTRANCE[road]
    if ground:
        d = next((d for d in ground['doors'] if d.get('kind') == 'main'), None)
        if d:
            zone = zone_of(d['x'], d['y'], b)
            st = 'ideal' if zone in ideal else ('avoid' if zone in avoid else 'neutral')
            pts = {'ideal': 1.0, 'neutral': 0.4, 'avoid': 0.0}[st]
            ent = {'zone': zone, 'status': st, 'ideal': ideal,
                   'advice': f"Main entrance on the {road} side sits in the {zone} zone. "
                             f"Best zones for a {road}-facing plot: {', '.join(ideal)}."}
            total_w += 15
            total_p += 15 * pts

    # window direction (share of windows on N/E walls)
    nw = ne = 0
    for fl in plan['floors']:
        for w in fl['windows']:
            if w['wall'] in ('N', 'E'):
                ne += 1
            nw += 1
    win = None
    if nw:
        share = ne / nw
        pts = 1.0 if share >= 0.4 else 0.6 if share >= 0.25 else 0.3
        win = {'share_north_east': round(100 * share), 'advice':
               "Good share of north/east windows for morning light." if share >= 0.4 else
               "Add more windows on the north/east walls for morning light and ventilation."}
        total_w += 6
        total_p += 6 * pts

    # adjacency checks
    checks, penalty = [], 0.0
    for fl in plan['floors']:
        rs = fl['rooms']
        for a in rs:
            if a['type'] != 'pooja' and a['type'] != 'kitchen':
                continue
            for b2 in rs:
                if b2['type'] in ('bathroom', 'toilet') and shared_wall(a, b2, 1.0):
                    checks.append(f"{a['name']} shares a wall with {b2['name']} ({fl['name']}) - avoid wet areas next to "
                                  f"{'worship' if a['type'] == 'pooja' else 'cooking'} spaces.")
                    penalty += 3
    score = round(max(0.0, (100 * total_p / total_w if total_w else 0) - penalty))
    grade = 'Excellent' if score >= 85 else 'Good' if score >= 70 else 'Fair' if score >= 50 else 'Needs work'
    return {'score': score, 'grade': grade, 'mode': mode, 'items': items, 'entrance': ent,
            'windows': win, 'checks': checks}
