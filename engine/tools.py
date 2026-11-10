"""Civil engineering calculators. Every tool returns {'inputs':..., 'results':{label: value}, 'notes':[...]}.
Rule-of-thumb preliminary values only - verify with a structural engineer and the relevant IS codes."""
import math

CFT_TO_M3 = 0.0283168
SQFT_TO_M2 = 0.09290304
FT = 0.3048


def _n(d, k, default=0.0):
    try:
        return float(d.get(k, default))
    except (TypeError, ValueError):
        return float(default)


def _pos(*vals):
    for v in vals:
        if v <= 0:
            raise ValueError("All dimensions must be greater than zero.")


def area(d):
    shape = d.get('shape', 'rectangle')
    a, b, c = _n(d, 'a'), _n(d, 'b'), _n(d, 'c')
    if shape == 'rectangle':
        _pos(a, b); v = a * b
    elif shape == 'triangle':
        _pos(a, b); v = 0.5 * a * b
    elif shape == 'circle':
        _pos(a); v = math.pi * a * a
    elif shape == 'trapezium':
        _pos(a, b, c); v = 0.5 * (a + b) * c
    elif shape == 'triangle_sss':
        _pos(a, b, c)
        s = (a + b + c) / 2
        if s <= max(a, b, c):
            raise ValueError("Sides do not form a triangle.")
        v = math.sqrt(s * (s - a) * (s - b) * (s - c))
    else:
        raise ValueError("Unknown shape")
    return {'inputs': d, 'results': {'Area (sq ft)': round(v, 2), 'Area (sq m)': round(v * SQFT_TO_M2, 2),
                                     'Area (sq yd)': round(v / 9, 2)},
            'notes': ["Enter dimensions in feet. Rectangle: a=length, b=width. Triangle: a=base, b=height. "
                      "Circle: a=radius. Trapezium: a,b parallel sides, c=height."]}


def volume(d):
    shape = d.get('shape', 'box')
    a, b, c = _n(d, 'a'), _n(d, 'b'), _n(d, 'c')
    if shape == 'box':
        _pos(a, b, c); v = a * b * c
    elif shape == 'cylinder':
        _pos(a, b); v = math.pi * a * a * b
    elif shape == 'cone':
        _pos(a, b); v = math.pi * a * a * b / 3
    elif shape == 'sphere':
        _pos(a); v = 4 / 3 * math.pi * a ** 3
    else:
        raise ValueError("Unknown shape")
    return {'inputs': d, 'results': {'Volume (cu ft)': round(v, 2), 'Volume (cu m)': round(v * CFT_TO_M3, 3),
                                     'Capacity (litres)': round(v * CFT_TO_M3 * 1000)},
            'notes': ["Box: a=L, b=W, c=H. Cylinder/cone: a=radius, b=height. Sphere: a=radius (feet)."]}


MIXES = {'M5': (1, 5, 10), 'M7.5': (1, 4, 8), 'M10': (1, 3, 6), 'M15': (1, 2, 4), 'M20': (1, 1.5, 3), 'M25': (1, 1, 2)}


def concrete(d):
    L, W, T = _n(d, 'length'), _n(d, 'width'), _n(d, 'thickness_in', 5)
    mix = d.get('mix', 'M20')
    _pos(L, W, T)
    if mix not in MIXES:
        raise ValueError("Unknown mix grade")
    vol = L * W * T / 12 * CFT_TO_M3
    c, s, a = MIXES[mix]
    dry = vol * 1.54
    tot = c + s + a
    cem = dry * c / tot
    return {'inputs': d, 'results': {
        'Wet volume (cu m)': round(vol, 3), 'Wet volume (cu ft)': round(vol / CFT_TO_M3, 1),
        'Cement (bags of 50 kg)': math.ceil(cem * 1440 / 50), 'Sand (cu m)': round(dry * s / tot, 2),
        'Aggregate (cu m)': round(dry * a / tot, 2), 'Mix ratio': f"{c}:{s}:{a}"},
        'notes': ["Dry volume = 1.54 x wet volume. Cement density 1440 kg/m3. Add 5% wastage on site."]}


def cement(d):
    work = d.get('work', 'brickwork')
    vol_m3 = _n(d, 'quantity') * (CFT_TO_M3 if d.get('unit', 'cft') == 'cft' else 1.0) if work != 'plaster' else None
    if work == 'plaster':
        a, t = _n(d, 'area_sqft'), _n(d, 'thickness_mm', 12)
        _pos(a, t)
        wet = a * SQFT_TO_M2 * t / 1000
        ratio = _n(d, 'ratio', 4)
        dry = wet * 1.27
        cem, sand = dry / (1 + ratio), dry * ratio / (1 + ratio)
    else:
        _pos(vol_m3)
        ratio = _n(d, 'ratio', 6)
        dry = vol_m3 * 0.25 * 1.27
        wet = vol_m3 * 0.25
        cem, sand = dry / (1 + ratio), dry * ratio / (1 + ratio)
    return {'inputs': d, 'results': {'Mortar (wet, cu m)': round(wet, 3), 'Cement (bags)': math.ceil(cem * 1440 / 50),
                                     'Sand (cu m)': round(sand, 2), 'Mix': f"1:{ratio:g}"},
            'notes': ["Brickwork mortar is taken as 25% of masonry volume. Plaster: area x thickness."]}


def brick(d):
    L, H, T = _n(d, 'length'), _n(d, 'height'), _n(d, 'thickness_in', 9)
    opening = _n(d, 'openings_sqft', 0)
    _pos(L, H, T)
    net_area = max(L * H - opening, 0)
    vol = net_area * T / 12 * CFT_TO_M3
    nos = vol * 500
    return {'inputs': d, 'results': {'Wall volume (cu m)': round(vol, 2), 'Bricks (nos, no wastage)': round(nos),
                                     'Bricks with 5% wastage': math.ceil(nos * 1.05),
                                     'Mortar (cu m wet)': round(vol * 0.25, 2)},
            'notes': ["Standard brick 190x90x90 mm (200x100x100 with mortar) = 500 bricks per m3."]}


def steel(d):
    kind = d.get('kind', 'slab')
    if kind == 'bar':
        dia, L, n = _n(d, 'dia_mm', 12), _n(d, 'length_ft'), _n(d, 'count', 1)
        _pos(dia, L, n)
        w = dia * dia / 162.0 * L * FT * n
        return {'inputs': d, 'results': {'Weight (kg)': round(w, 1), 'Weight per metre (kg/m)': round(dia * dia / 162, 3)},
                'notes': ["Unit weight = d^2/162 kg per metre (d in mm)."]}
    L, W, T = _n(d, 'length'), _n(d, 'width'), _n(d, 'thickness_in', 5)
    dia, spacing = _n(d, 'dia_mm', 10), _n(d, 'spacing_in', 6)
    _pos(L, W, T, dia, spacing)
    per_dir_x = math.ceil(W * 12 / spacing) + 1
    per_dir_y = math.ceil(L * 12 / spacing) + 1
    total_len_m = (per_dir_x * L + per_dir_y * W) * FT
    wt = total_len_m * dia * dia / 162
    return {'inputs': d, 'results': {'Bars (main)': per_dir_x, 'Bars (distribution)': per_dir_y,
                                     'Total length (m)': round(total_len_m, 1), 'Steel weight (kg)': round(wt),
                                     'Steel weight (tonnes)': round(wt / 1000, 3)},
            'notes': ["Single-layer mesh both ways; add laps, bends, chairs and top steel as per the structural drawing."]}


def paint(d):
    wall, ceil_, openings = _n(d, 'wall_area'), _n(d, 'ceiling_area', 0), _n(d, 'openings_sqft', 0)
    coats, cover = _n(d, 'coats', 2), _n(d, 'coverage', 110)
    _pos(wall + ceil_, coats, cover)
    area_ = max(wall - openings, 0) + ceil_
    prim = area_ / cover
    fin = area_ * coats / cover
    return {'inputs': d, 'results': {'Paintable area (sq ft)': round(area_), 'Primer (litres)': round(prim, 1),
                                     'Finish paint (litres)': round(fin, 1), 'Putty (kg, 2 coats)': round(area_ / 12)},
            'notes': ["Coverage default 110 sq ft per litre per coat. Textured finishes need more."]}


def tile(d):
    L, W = _n(d, 'length'), _n(d, 'width')
    tl, tw = _n(d, 'tile_len_in', 24), _n(d, 'tile_wid_in', 24)
    wastage = _n(d, 'wastage_pct', 8)
    _pos(L, W, tl, tw)
    area_ = L * W
    tile_a = tl * tw / 144
    n = math.ceil(area_ / tile_a * (1 + wastage / 100))
    return {'inputs': d, 'results': {'Floor area (sq ft)': round(area_, 1), 'Tile size (sq ft)': round(tile_a, 2),
                                     'Tiles needed': n, 'Boxes (4 tiles/box)': math.ceil(n / 4),
                                     'Adhesive (kg, ~4 kg/m2)': round(area_ * SQFT_TO_M2 * 4)},
            'notes': ["Wastage 5-10% for straight lay, 12-15% for diagonal/patterned layouts."]}


def staircase(d):
    H = _n(d, 'floor_height_ft', 10)
    riser = _n(d, 'riser_in', 6.5)
    tread = _n(d, 'tread_in', 10)
    width = _n(d, 'width_ft', 3.5)
    _pos(H, riser, tread, width)
    risers = max(1, round(H * 12 / riser))
    actual_riser = H * 12 / risers
    treads = risers - 1
    going = treads * tread / 12
    notes = ["Rule of thumb: 2 x riser + tread = 23-25 in. Riser 6-7.5 in, tread 10-12 in for residences."]
    check = 2 * actual_riser + tread
    if not 22 <= check <= 26:
        notes.append(f"2R+T = {check:.1f} in is outside the comfortable 23-25 in range.")
    waist = 5.0  # waist slab thickness in inches
    conc = (going * width * waist / 12 + 0.5 * risers * (actual_riser / 12) * (tread / 12) * width) * CFT_TO_M3
    return {'inputs': d, 'results': {'Number of risers': risers, 'Actual riser (in)': round(actual_riser, 2),
                                     'Number of treads': treads, 'Going / horizontal run (ft)': round(going, 2),
                                     'Slope (deg)': round(math.degrees(math.atan(actual_riser / tread)), 1),
                                     '2R + T (in)': round(check, 1), 'Concrete (cu m, 125 mm waist)': round(conc, 2)},
            'notes': notes}


def foundation(d):
    P = _n(d, 'column_load_kn')
    sbc = _n(d, 'sbc_kn_m2', 150)
    col = _n(d, 'column_size_mm', 230)
    _pos(P, sbc)
    Pw = P * 1.1  # self weight
    A = Pw / sbc
    side = math.ceil(math.sqrt(A) * 10) / 10
    proj = (side * 1000 - col) / 2
    depth_mm = max(300, math.ceil(proj * 0.6 / 25) * 25)
    vol = side * side * depth_mm / 1000
    return {'inputs': d, 'results': {'Required footing area (m2)': round(A, 2), 'Square footing side (m)': side,
                                     'Side (ft)': round(side / FT, 2), 'Trial depth (mm)': depth_mm,
                                     'Concrete (m3)': round(vol, 2), 'Steel (kg, ~80 kg/m3)': round(vol * 80)},
            'notes': ["Isolated square footing sized on safe bearing capacity with 10% self-weight allowance.",
                      "Depth is a trial value only; check shear, bending and settlement per IS 456 / soil report."]}


def beam_column(d):
    span = _n(d, 'span_ft')
    load = _n(d, 'column_load_kn')
    fck, fy = _n(d, 'fck', 20), _n(d, 'fy', 415)
    _pos(span)
    span_mm = span * 304.8
    depth = max(300, math.ceil(span_mm / 12 / 25) * 25)
    width = max(230, math.ceil(depth / 2 / 25) * 25)
    res = {'Beam span (mm)': round(span_mm), 'Trial beam depth D (mm)': depth, 'Trial beam width b (mm)': width,
           'Beam size (in)': f"{width / 25.4:.1f} x {depth / 25.4:.1f}",
           'Main steel (approx. 0.8% of bD, mm2)': round(0.008 * width * (depth - 40))}
    notes = ["Beam depth = span/12 (continuous) to span/10; width = D/2, minimum 230 mm (IS 456 thumb rules)."]
    if load > 0:
        Pu = 1.5 * load * 1000
        Ac_Asc = 0.4 * fck + (0.67 * fy - 0.4 * fck) * 0.01
        Ag = Pu / Ac_Asc
        side = max(230, math.ceil(math.sqrt(Ag) / 25) * 25)
        res.update({'Factored load Pu (kN)': round(1.5 * load), 'Gross column area (mm2)': round(Ag),
                    'Square column size (mm)': side, 'Column size (in)': round(side / 25.4, 1),
                    'Main steel 1% (mm2)': round(0.01 * side * side), 'Bars (16 mm)': max(4, math.ceil(0.01 * side * side / 201))})
        notes.append("Short axially-loaded column: Pu = 0.4 fck Ac + 0.67 fy Asc with 1% steel (IS 456 cl. 39.3).")
    return {'inputs': d, 'results': res, 'notes': notes}


TOOLS = {'area': area, 'volume': volume, 'concrete': concrete, 'cement': cement, 'brick': brick, 'steel': steel,
         'paint': paint, 'tile': tile, 'staircase': staircase, 'foundation': foundation, 'beam_column': beam_column}


def run(name, data):
    if name not in TOOLS:
        raise ValueError("Unknown tool")
    return TOOLS[name](data or {})
