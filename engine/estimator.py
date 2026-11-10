"""Construction quantity & cost estimator driven by the real plan geometry.

All rates are approximate planning figures (INR) and are meant to be edited per city.
Quantities use standard thumb rules; they are NOT a substitute for a Bill of Quantities by a quantity surveyor."""
import math
from .geom import floor_walls, FT

M2_PER_SQFT = 0.09290304
M3_PER_CFT = 0.0283168

DEFAULT_PRICES = {  # key: (label, unit, price INR)
    'cement': ('Cement (50 kg bag)', 'bag', 390.0),
    'sand': ('River / M-sand', 'm3', 1700.0),
    'aggregate': ('Aggregate 20 mm', 'm3', 1500.0),
    'bricks': ('Bricks (first class)', 'piece', 8.5),
    'steel': ('TMT steel Fe500', 'kg', 68.0),
    'tiles': ('Vitrified floor tiles', 'sqft', 58.0),
    'paint': ('Primer + emulsion paint', 'litre', 330.0),
    'labour': ('Skilled + unskilled labour', 'sqft built-up', 480.0),
    'plumbing': ('Plumbing & sanitary (rough + fixtures)', 'sqft built-up', 150.0),
    'electrical': ('Electrical wiring & fittings', 'sqft built-up', 140.0),
    'door': ('Door (frame + shutter + hardware)', 'each', 12500.0),
    'window': ('Window (aluminium/UPVC with glass)', 'each', 9000.0),
    'excavation': ('Earthwork, PCC & waterproofing', 'sqft footprint', 220.0),
}
CITY_FACTORS = {  # multiplier on the default price set for quick presets
    'Jaipur': 1.00, 'Delhi': 1.12, 'Mumbai': 1.30, 'Bengaluru': 1.15, 'Hyderabad': 1.08, 'Pune': 1.10,
    'Lucknow': 0.96, 'Ahmedabad': 1.02, 'Chennai': 1.10, 'Kolkata': 1.04, 'Indore': 0.97, 'Patna': 0.94,
}


def prices_for_city(city, overrides=None, db_rows=None):
    base = {}
    f = CITY_FACTORS.get(city, 1.0)
    for k, (label, unit, price) in DEFAULT_PRICES.items():
        base[k] = {'label': label, 'unit': unit, 'price': round(price * f, 2)}
    for r in db_rows or []:
        base[r['key']] = {'label': r['label'], 'unit': r['unit'], 'price': float(r['price'])}
    for k, v in (overrides or {}).items():
        try:
            if k in base and float(v) >= 0:
                base[k]['price'] = float(v)
        except (TypeError, ValueError):
            pass
    return base


def estimate(plan, prices, include_boundary=True):
    built_sqft = 0.0
    wall_ext_m3 = wall_int_m3 = 0.0
    ext_len = int_len = 0.0
    n_doors = n_windows = 0
    open_area_sqft = 0.0
    wet_dado_sqft = 0.0
    plaster_sqft = 0.0
    n_floors = 0
    top_h = 0
    for f in plan['floors']:
        if f['kind'] == 'terrace':
            continue
        rooms = [r for r in f['rooms'] if not r.get('outdoor')]
        if not rooms:
            continue
        n_floors += 1
        built_sqft += sum(r['w'] * r['h'] for r in rooms)
        H = f['height']
        for w in floor_walls(rooms, f['outline']):
            L = w['e'] - w['s']
            t = w['t']
            vol = L * H * t * FT ** 3  # m3 (gross)
            if w['ext']:
                wall_ext_m3 += vol
                ext_len += L
                plaster_sqft += 2 * L * H                          # exterior + interior face
            else:
                wall_int_m3 += vol
                int_len += L
                plaster_sqft += 2 * L * H
        for r in rooms:
            if r['type'] in ('bathroom', 'toilet'):
                wet_dado_sqft += 2 * (r['w'] + r['h']) * 7.0
        for d in f['doors']:
            n_doors += 1
            open_area_sqft += d['width'] * 7.0
        for w in f['windows']:
            n_windows += 1
            open_area_sqft += w['width'] * (w.get('head', 7.0) - w.get('sill', 3.0))
        top_h = H
    footprint = sum(r['w'] * r['h'] for r in next(f for f in plan['floors'] if f['kind'] == 'ground')['rooms']
                    if not r.get('outdoor'))
    ext_len_ground = plan['buildable']['w'] * 2 + plan['buildable']['h'] * 2
    parapet_m3 = ext_len_ground * 3.0 * 0.375 * FT ** 3      # 3 ft parapet, 4.5 in thick
    boundary_m3 = 0.0
    if include_boundary:
        per = 2 * (plan['plot']['ex'] + plan['plot']['ny'])
        boundary_m3 = max(per - 12, 0) * 5.0 * 0.75 * FT ** 3

    opening_deduct = open_area_sqft * 0.375 * FT ** 3 * 1.6  # avg wall thickness blend
    masonry_m3 = max(wall_ext_m3 + wall_int_m3 + parapet_m3 + boundary_m3 - opening_deduct, 0.0)
    bricks = masonry_m3 * 500 * 1.05           # 500 bricks / m3 of masonry (incl. mortar joints) + 5% wastage
    mortar_dry = masonry_m3 * 0.25 * 1.27      # wet mortar ~25% of masonry volume, x1.27 dry
    mort_cement_m3 = mortar_dry / 7.0          # 1:6 mix
    mort_sand_m3 = mortar_dry * 6.0 / 7.0

    plaster_m2 = plaster_sqft * M2_PER_SQFT
    plaster_wet = plaster_m2 * 0.015           # 15 mm thick
    plaster_dry = plaster_wet * 1.27
    pl_cement_m3 = plaster_dry / 5.0           # 1:4
    pl_sand_m3 = plaster_dry * 4.0 / 5.0

    built_m2 = built_sqft * M2_PER_SQFT
    foot_m2 = footprint * M2_PER_SQFT
    slab_m3 = built_m2 * 0.125                 # 125 mm slabs (incl. terrace slab via top floor)
    beam_m3 = built_m2 * 0.045
    col_m3 = built_m2 * 0.02
    found_m3 = foot_m2 * 0.075 * (1 + 0.15 * max(n_floors - 1, 0))
    stair_m3 = n_floors * 1.2
    concrete_m3 = slab_m3 + beam_m3 + col_m3 + found_m3 + stair_m3
    # M20 (1:1.5:3): dry factor 1.54
    c_cement_m3 = concrete_m3 * 1.54 / 5.5
    c_sand_m3 = concrete_m3 * 1.54 * 1.5 / 5.5
    c_agg_m3 = concrete_m3 * 1.54 * 3.0 / 5.5
    steel_kg = concrete_m3 * 105.0             # typical 90-120 kg/m3 for residential frames

    cement_m3 = c_cement_m3 + mort_cement_m3 + pl_cement_m3
    cement_bags = cement_m3 * 1440 / 50.0
    sand_m3 = c_sand_m3 + mort_sand_m3 + pl_sand_m3
    agg_m3 = c_agg_m3

    floor_sqft = built_sqft - sum(r['w'] * r['h'] for f in plan['floors'] if f['kind'] != 'terrace'
                                  for r in f['rooms'] if r['type'] in ('staircase', 'parking'))
    tiles_sqft = (floor_sqft + wet_dado_sqft) * 1.08
    paint_area = plaster_sqft * 0.92 + built_sqft  # walls (less openings) + ceilings
    paint_l = paint_area * 3.0 / 110.0          # 1 primer + 2 finish coats, ~110 sqft/L/coat

    P = {k: v['price'] for k, v in prices.items()}
    lines = [
        ('Cement', cement_bags, 'bags', P['cement'], 'cement'),
        ('Sand', sand_m3, 'm3', P['sand'], 'sand'),
        ('Aggregate', agg_m3, 'm3', P['aggregate'], 'aggregate'),
        ('Bricks', bricks, 'nos', P['bricks'], 'bricks'),
        ('Steel (TMT)', steel_kg, 'kg', P['steel'], 'steel'),
        ('Floor & wall tiles', tiles_sqft, 'sq ft', P['tiles'], 'tiles'),
        ('Paint (primer + emulsion)', paint_l, 'litres', P['paint'], 'paint'),
        ('Doors', n_doors, 'nos', P['door'], 'door'),
        ('Windows', n_windows, 'nos', P['window'], 'window'),
        ('Earthwork, PCC & waterproofing', footprint, 'sq ft', P['excavation'], 'excavation'),
        ('Labour', built_sqft, 'sq ft', P['labour'], 'labour'),
        ('Plumbing & sanitary', built_sqft, 'sq ft', P['plumbing'], 'plumbing'),
        ('Electrical', built_sqft, 'sq ft', P['electrical'], 'electrical'),
    ]
    rows = [{'item': n, 'qty': round(q, 2), 'unit': u, 'rate': r, 'amount': round(q * r), 'key': k}
            for n, q, u, r, k in lines]
    subtotal = sum(x['amount'] for x in rows)
    contingency = round(subtotal * 0.05)
    total = subtotal + contingency
    return {
        'built_sqft': round(built_sqft, 1), 'footprint_sqft': round(footprint, 1),
        'quantities': {
            'cement_bags': round(cement_bags), 'sand_m3': round(sand_m3, 1), 'sand_cft': round(sand_m3 / M3_PER_CFT),
            'aggregate_m3': round(agg_m3, 1), 'bricks': round(bricks), 'steel_kg': round(steel_kg),
            'steel_tonnes': round(steel_kg / 1000, 2), 'concrete_m3': round(concrete_m3, 1),
            'concrete_cft': round(concrete_m3 / M3_PER_CFT), 'tiles_sqft': round(tiles_sqft),
            'paint_litres': round(paint_l), 'masonry_m3': round(masonry_m3, 1),
            'doors': n_doors, 'windows': n_windows,
        },
        'rows': rows, 'subtotal': subtotal, 'contingency': contingency, 'contingency_pct': 5, 'total': total,
        'per_sqft': round(total / built_sqft) if built_sqft else 0,
        'cost_groups': {
            'Materials': sum(x['amount'] for x in rows if x['key'] in ('cement', 'sand', 'aggregate', 'bricks', 'steel', 'tiles', 'paint', 'door', 'window', 'excavation')),
            'Labour': next(x['amount'] for x in rows if x['key'] == 'labour'),
            'Plumbing': next(x['amount'] for x in rows if x['key'] == 'plumbing'),
            'Electrical': next(x['amount'] for x in rows if x['key'] == 'electrical'),
            'Contingency': contingency,
        },
        'assumptions': [
            "Masonry: 9 in external and 4.5 in internal brick walls; 500 bricks per m3 incl. joints + 5% wastage.",
            "Concrete: M20 (1:1.5:3) for slabs (125 mm), beams, columns and footings; steel at ~105 kg per m3.",
            "Mortar 1:6 for brickwork, 1:4 plaster (15 mm). Paint: 1 primer + 2 finish coats at ~110 sq ft per litre.",
            "Boundary wall (5 ft, 9 in) is included around the plot except a 12 ft gate. Prices are editable per city.",
            "Not included: furniture, modular kitchen, lifts, solar, landscaping, approvals/fees, interior design.",
        ],
    }
