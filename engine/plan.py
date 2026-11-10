"""Plan assembly, recomputation after edits, validation, space-utilisation metrics."""
import copy
from .geom import overlap_area, wall_len, opening_point, fmt_ft
from . import layout as L
from . import vastu as V
from .furniture import furnish_room, electrical
from .plot import compute_plot

VARIANTS = [
    dict(key='A', title='Option A - Compact Hub', transposed=False, strip_side='W', stair_end='S', alt=False),
    dict(key='B', title='Option B - Wing Layout', transposed=True, strip_side='W', stair_end='N', alt=False),
    dict(key='C', title='Option C - Garden Facing', transposed=False, strip_side='E', stair_end='N', alt=True),
]
MIN_SHORT = {'living': 9, 'master': 9, 'guest': 8, 'kids': 8, 'kitchen': 6, 'dining': 7, 'bathroom': 4, 'toilet': 3,
             'pooja': 3, 'balcony': 3, 'parking': 8, 'store': 3, 'utility': 3, 'lounge': 7, 'staircase': 6}
CAT_MAP = {'living': 'Living & dining', 'sleeping': 'Sleeping', 'service': 'Kitchen & services', 'wet': 'Bath & toilets',
           'circulation': 'Stairs & circulation', 'parking': 'Parking', 'outdoor': 'Balcony & outdoor'}
STYLE_DEFAULT = {'roof': 'flat', 'wall_color': '#f4efe6', 'floor_material': 'vitrified', 'parapet_ft': 3.0,
                 'floor_height_ft': L.FLOOR_H}


def _plan_floors_from_layout(floors, plot, mode):
    out = []
    b = plot['buildable']
    el = 0.0
    for f in sorted(floors, key=lambda f: f['index']):
        h = L.BASEMENT_H if f['kind'] == 'basement' else L.FLOOR_H
        f['height'] = h
        f['outline'] = dict(b)
        doors, windows = L.generate_openings(f, b, plot['road'], mode)
        f['doors'], f['windows'] = doors, windows
        out.append(f)
    return out


def finalize(plan, with_openings=False):
    """Recompute furniture, electrical, metrics, validation, Vastu score for a plan dict (mutates & returns it)."""
    b = plan['buildable']
    el = 0.0
    floors = sorted(plan['floors'], key=lambda f: f['index'])
    plan['floors'] = floors
    base = -L.BASEMENT_H if floors and floors[0]['kind'] == 'basement' else 0.0
    el = base
    for f in floors:
        f['height'] = L.BASEMENT_H if f['kind'] == 'basement' else float(f.get('height') or L.FLOOR_H)
        f['elevation'] = round(el, 2)
        el += f['height']
        f.setdefault('outline', dict(b))
        rooms = {r['id']: r for r in f['rooms']}
        f['doors'] = [d for d in f.get('doors', []) if d['room'] in rooms]
        f['windows'] = [w for w in f.get('windows', []) if w['room'] in rooms]
        for d in f['doors'] + f['windows']:
            r = rooms[d['room']]
            ln = wall_len(r, d['wall'])
            hw = d['width'] / 2
            d['t'] = round(min(max(d['t'], hw + 0.25), max(ln - hw - 0.25, hw + 0.25)), 2)
            x, y, o = opening_point(r, d['wall'], d['t'])
            d['x'], d['y'], d['orient'] = round(x, 2), round(y, 2), o
        furn, elec = [], []
        for r in f['rooms']:
            if r.get('outdoor'):
                continue
            rd = [d for d in f['doors'] if d['room'] == r['id']]
            rw = [w for w in f['windows'] if w['room'] == r['id']]
            for it in furnish_room(r, rd, rw):
                it['room'] = r['id']
                furn.append(it)
            for pt in electrical(r, rd, rw):
                pt['room'] = r['id']
                elec.append(pt)
        f['furniture'], f['electrical'] = furn, elec
    plan['validation'] = validate(plan)
    plan['metrics'] = metrics(plan)
    plan['vastu'] = V.score_plan(plan, plan['plot']['road'], plan.get('vastu_mode', 'flexible'))
    return plan


def validate(plan):
    issues = []
    b = plan['buildable']
    pb = plan['plot']
    for f in plan['floors']:
        rs = [r for r in f['rooms']]
        for i, r in enumerate(rs):
            if r['w'] <= 0 or r['h'] <= 0:
                issues.append({'level': 'error', 'floor': f['name'], 'msg': f"{r['name']} has zero size."})
                continue
            if r.get('outdoor'):
                if r['x'] < -1e-6 or r['y'] < -1e-6 or r['x'] + r['w'] > pb['ex'] + 1e-6 or r['y'] + r['h'] > pb['ny'] + 1e-6:
                    issues.append({'level': 'error', 'floor': f['name'], 'msg': f"{r['name']} is outside the plot."})
            elif (r['x'] < b['x'] - 1e-3 or r['y'] < b['y'] - 1e-3 or r['x'] + r['w'] > b['x'] + b['w'] + 1e-3
                  or r['y'] + r['h'] > b['y'] + b['h'] + 1e-3):
                issues.append({'level': 'error', 'floor': f['name'],
                               'msg': f"{r['name']} crosses the setback line / plot boundary."})
            ms = MIN_SHORT.get(r['type'])
            if ms and min(r['w'], r['h']) < ms - 1e-6:
                issues.append({'level': 'warn', 'floor': f['name'],
                               'msg': f"{r['name']} is {fmt_ft(min(r['w'], r['h']))} on its short side (recommended {ms} ft minimum)."})
            if min(r['w'], r['h']) > 0 and max(r['w'], r['h']) / min(r['w'], r['h']) > 2.6 and r['type'] not in ('balcony', 'parking', 'lobby', 'garden'):
                issues.append({'level': 'warn', 'floor': f['name'], 'msg': f"{r['name']} is long and narrow (aspect > 2.6)."})
            for r2 in rs[i + 1:]:
                if overlap_area(r, r2) > 0.05:
                    issues.append({'level': 'error', 'floor': f['name'],
                                   'msg': f"{r['name']} overlaps {r2['name']}."})
        if f['kind'] in ('ground', 'upper', 'basement'):
            ind = [r for r in rs if not r.get('outdoor')]
            if ind:
                no_air = [r['name'] for r in ind if r['type'] not in ('lobby', 'hall', 'pooja', 'parking', 'balcony', 'headroom')
                          and not any(w['room'] == r['id'] for w in f['windows'])]
                for n in no_air:
                    issues.append({'level': 'warn', 'floor': f['name'],
                                   'msg': f"{n} has no exterior window - plan a ventilation shaft / exhaust."})
    return issues


def metrics(plan):
    b = plan['buildable']
    plot_area = plan['plot']['areas']['sqft']
    floors_out, built_total = [], 0.0
    util = {}
    room_rows = []
    for f in plan['floors']:
        if f['kind'] == 'terrace':
            continue
        area = sum(r['w'] * r['h'] for r in f['rooms'] if not r.get('outdoor'))
        built_total += area
        for r in f['rooms']:
            if r.get('outdoor') and r['type'] == 'garden':
                continue
            a = r['w'] * r['h']
            cat = L.SPEC.get(r['type'], {}).get('cat', 'service')
            util[cat] = util.get(cat, 0) + a
            room_rows.append({'floor': f['name'], 'name': r['name'], 'type': r['type'], 'w': round(r['w'], 2),
                              'h': round(r['h'], 2), 'area_sqft': round(a, 1),
                              'dims': f"{fmt_ft(r['w'])} x {fmt_ft(r['h'])}"})
        floors_out.append({'floor': f['name'], 'built_sqft': round(area, 1)})
    tot = sum(util.values()) or 1
    ground = next((f for f in plan['floors'] if f['kind'] == 'ground'), None)
    footprint = sum(r['w'] * r['h'] for r in ground['rooms'] if not r.get('outdoor')) if ground else 0
    return {
        'built_total_sqft': round(built_total, 1), 'built_total_sqm': round(built_total * 0.0929, 1),
        'footprint_sqft': round(footprint, 1), 'plot_sqft': plot_area,
        'coverage_pct': round(100 * footprint / plot_area, 1), 'far': round(built_total / plot_area, 2),
        'open_space_sqft': round(plot_area - footprint, 1), 'floors': floors_out,
        'utilisation': [{'category': CAT_MAP.get(k, k), 'sqft': round(v, 1), 'pct': round(100 * v / tot, 1)}
                        for k, v in sorted(util.items(), key=lambda kv: -kv[1])],
        'rooms': room_rows,
    }


def recommendations(plan, inp):
    tips = []
    m = plan['metrics']
    v = plan['vastu']
    tips.append(f"Ground coverage is {m['coverage_pct']}% of the plot with {m['open_space_sqft']:.0f} sq ft of open space "
                f"(FAR {m['far']}). Verify FAR and coverage against your local authority.")
    bad = [i for i in v['items'] if i['status'] == 'avoid']
    for i in bad[:4]:
        tips.append(f"Vastu: {i['room']} ({i['floor']}) falls in {i['zone']}. {i['advice']}")
    if v['windows']:
        tips.append(v['windows']['advice'])
    for c in v['checks'][:3]:
        tips.append(c)
    for iss in plan['validation']:
        if iss['level'] == 'warn':
            tips.append(f"{iss['floor']}: {iss['msg']}")
    budget = float(inp.get('budget') or 0)
    if budget:
        tips.append("Budget is compared to the estimate on the Estimator tab; consider phasing upper floors if it is exceeded.")
    tips.append("Provide cross ventilation by placing windows on opposite walls of principal rooms; keep a 3 ft clearance in front of doors.")
    tips.append("Have a licensed structural engineer verify column grid, footing sizes and load paths before construction.")
    return tips[:12]


def generate_plans(inp):
    """Main entry: validated inputs -> 3 layout options (geometry, doors, windows, furniture, Vastu, metrics)."""
    plot = compute_plot(inp)
    mode = {'strict': 'strict', 'flexible': 'flexible', 'normal': 'normal'}.get(inp.get('vastu_mode'), 'flexible')
    options, warnings = [], []
    for v in VARIANTS:
        try:
            floors, warns = L.generate_option(inp, plot, v, mode)
        except ValueError as e:
            if v is VARIANTS[0]:
                raise
            warnings.append(f"{v['title']}: {e}")
            continue
        plan = {'key': v['key'], 'title': v['title'], 'plot': plot, 'buildable': dict(plot['buildable']),
                'floors': _plan_floors_from_layout(floors, plot, mode), 'warnings': warns,
                'vastu_mode': mode, 'style': dict(STYLE_DEFAULT)}
        finalize(plan)
        plan['recommendations'] = recommendations(plan, inp)
        options.append(plan)
    # drop duplicate geometries (can happen on very small plots)
    uniq, seen = [], set()
    for p in options:
        sig = tuple((r['type'], r['x'], r['y'], r['w'], r['h']) for f in p['floors'][:2] for r in f['rooms'])
        if sig not in seen:
            seen.add(sig)
            uniq.append(p)
    return {'plot': plot, 'options': uniq, 'warnings': warnings}
