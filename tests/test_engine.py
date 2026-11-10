import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.plan import generate_plans
from engine.geom import overlap_area
from tests.sample_inputs import SAMPLES

def check(name, inp):
    res = generate_plans(inp)
    assert res['options'], name
    for p in res['options']:
        errs = [i for i in p['validation'] if i['level']=='error']
        assert not errs, (name, p['key'], errs)
        for f in p['floors']:
            tot = sum(r['w']*r['h'] for r in f['rooms'] if not r.get('outdoor'))
            if f['kind']!='terrace':
                b = p['buildable']
                assert abs(tot - b['w']*b['h']) < 0.5, (name, f['name'], tot, b['w']*b['h'])
            ids = {r['id'] for r in f['rooms']}
            for d in f['doors']: assert d['room'] in ids
        print(f"  {name} {p['key']}: floors={len(p['floors'])} built={p['metrics']['built_total_sqft']} vastu={p['vastu']['score']} warns={len(p['validation'])} {p['warnings']}")
    return res

if __name__ == '__main__':
    for n, i in SAMPLES.items():
        print(n); check(n, i)
    print("ALL OK")
