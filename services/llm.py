"""Optional LLM commentary. Layout geometry never depends on this; without an API key a rule-based summary is returned."""
import json
import requests


def rule_based(plan, inputs):
    m, v = plan['metrics'], plan['vastu']
    best = sorted(v['items'], key=lambda i: -i['points'])[:2]
    worst = [i for i in v['items'] if i['status'] == 'avoid'][:2]
    s = (f"{plan['title']}: {m['built_total_sqft']:.0f} sq ft built-up over {len([f for f in plan['floors'] if f['kind'] != 'terrace'])} level(s), "
         f"{m['coverage_pct']}% ground coverage and {m['open_space_sqft']:.0f} sq ft open space. "
         f"Vastu score {v['score']}/100 ({v['grade']}). ")
    if best:
        s += "Well placed: " + ", ".join(f"{i['room']} ({i['zone']})" for i in best) + ". "
    if worst:
        s += "Reconsider: " + ", ".join(f"{i['room']} ({i['zone']})" for i in worst) + ". "
    s += "Use cross-ventilation, keep door clearances, and have a structural engineer verify the frame before construction."
    return s


def commentary(cfg, plan, inputs):
    if not cfg.get('LLM_API_KEY') or not cfg.get('LLM_API_URL'):
        return {'text': rule_based(plan, inputs), 'source': 'rules'}
    summary = {'title': plan['title'], 'metrics': {k: plan['metrics'][k] for k in ('built_total_sqft', 'coverage_pct', 'far', 'open_space_sqft')},
               'vastu_score': plan['vastu']['score'],
               'rooms': [{'floor': r['floor'], 'name': r['name'], 'dims': r['dims']} for r in plan['metrics']['rooms']],
               'road': plan['plot']['road'], 'city': inputs.get('city'), 'budget': inputs.get('budget')}
    prompt = ("You are a residential architect in India. Give 5 short, practical design comments (bullet list, no preamble) "
              "on this preliminary house plan: layout strengths, circulation, light/ventilation, Vastu notes and budget. "
              "Do not invent dimensions.\n" + json.dumps(summary))
    try:
        r = requests.post(cfg['LLM_API_URL'], timeout=40, headers={
            'x-api-key': cfg['LLM_API_KEY'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
            json={'model': cfg['LLM_MODEL'], 'max_tokens': 500, 'messages': [{'role': 'user', 'content': prompt}]})
        r.raise_for_status()
        text = ''.join(b.get('text', '') for b in r.json().get('content', []))
        return {'text': text.strip() or rule_based(plan, inputs), 'source': 'llm'}
    except Exception as e:  # network / key / quota problems must never break the designer
        return {'text': rule_based(plan, inputs), 'source': 'rules', 'error': str(e)[:160]}
