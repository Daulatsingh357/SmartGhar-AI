"""JSON API used by the studio, tools and dashboard."""
import json
from functools import wraps
from flask import Blueprint, request, jsonify, current_app, Response
from flask_login import login_required, current_user
from models import db, Project, DownloadLog, MaterialPrice
from engine.plot import compute_plot
from engine.plan import generate_plans, finalize
from engine.layout import Infeasible
from engine.estimator import estimate, prices_for_city
from engine import tools as civil_tools
from services.llm import commentary
from routes.pages import PLAN_LIMITS

bp = Blueprint("api", __name__, url_prefix="/api")


def api(fn):
    @wraps(fn)
    def w(*a, **k):
        try:
            return fn(*a, **k)
        except (ValueError, Infeasible) as e:
            return jsonify(error=str(e)), 400
        except (KeyError, TypeError) as e:
            return jsonify(error=f"Invalid data: {e}"), 400
    return w


def body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ValueError("Expected a JSON object.")
    return d


def check_plan(plan):
    """Light structural validation of a client-supplied plan before recomputation."""
    if not isinstance(plan, dict) or not isinstance(plan.get("floors"), list) or not plan["floors"]:
        raise ValueError("Plan has no floors.")
    if len(plan["floors"]) > 8:
        raise ValueError("Too many floors.")
    b = plan.get("buildable") or {}
    for k in ("x", "y", "w", "h"):
        float(b[k])
    for f in plan["floors"]:
        if len(f.get("rooms", [])) > 80:
            raise ValueError("Too many rooms on a floor.")
        for r in f.get("rooms", []):
            for k in ("x", "y", "w", "h"):
                r[k] = float(r[k])
            if r["w"] <= 0 or r["h"] <= 0 or r["w"] > 500 or r["h"] > 500:
                raise ValueError(f"Room '{r.get('name')}' has invalid size.")
    return plan


def db_prices(city):
    rows = MaterialPrice.query.filter_by(city=city).all()
    return [dict(key=r.key, label=r.label, unit=r.unit, price=r.price) for r in rows]


def owned(pid):
    p = db.session.get(Project, pid)
    if not p or (p.user_id != current_user.id and not current_user.is_admin):
        return None
    return p


@bp.route("/plot/calc", methods=["POST"])
@api
def plot_calc():
    return jsonify(compute_plot(body()))


@bp.route("/generate", methods=["POST"])
@api
def generate():
    inp = body()
    res = generate_plans(inp)
    return jsonify(res)


@bp.route("/finalize", methods=["POST"])
@api
def finalize_plan():
    """Recompute furniture, metrics, validation and Vastu after the user edits rooms/walls/openings."""
    plan = check_plan(body().get("plan"))
    keep = {f["index"]: f.get("furniture", []) for f in plan["floors"] if f.get("custom_furniture")}
    out = finalize(plan)
    for f in out["floors"]:
        if f["index"] in keep:
            f["furniture"] = keep[f["index"]]
            f["custom_furniture"] = True
    return jsonify(out)


@bp.route("/prices")
@api
def prices():
    city = request.args.get("city", "Jaipur")
    return jsonify(prices_for_city(city, db_rows=db_prices(city)))


@bp.route("/estimate", methods=["POST"])
@api
def estimate_api():
    d = body()
    plan = check_plan(d.get("plan"))
    city = d.get("city") or plan.get("plot", {}).get("city") or "Jaipur"
    prices = prices_for_city(city, overrides=d.get("overrides"), db_rows=db_prices(city))
    return jsonify(dict(estimate=estimate(plan, prices), prices=prices, city=city))


@bp.route("/tools/<name>", methods=["POST"])
@api
def tool(name):
    return jsonify(civil_tools.run(name, body()))


@bp.route("/commentary", methods=["POST"])
@login_required
@api
def commentary_api():
    d = body()
    return jsonify(commentary(current_app.config, check_plan(d.get("plan")), d.get("inputs") or {}))


# ---- projects -------------------------------------------------------------------------------
def project_json(p, full=True):
    out = dict(id=p.id, name=p.name, selected_option=p.selected_option,
               created_at=p.created_at.isoformat(), updated_at=p.updated_at.isoformat())
    if full:
        out["inputs"] = json.loads(p.inputs_json)
        out["plans"] = json.loads(p.plans_json) if p.plans_json else []
    return out


@bp.route("/projects", methods=["GET", "POST"])
@login_required
@api
def projects():
    if request.method == "GET":
        ps = Project.query.filter_by(user_id=current_user.id).order_by(Project.updated_at.desc()).all()
        return jsonify([project_json(p, False) for p in ps])
    d = body()
    count = Project.query.filter_by(user_id=current_user.id).count()
    if count >= PLAN_LIMITS.get(current_user.plan, 3):
        return jsonify(error="Project limit reached for your plan. Upgrade to save more."), 402
    p = Project(user_id=current_user.id, name=(d.get("name") or "Untitled project")[:150],
                inputs_json=json.dumps(d.get("inputs") or {}), plans_json=json.dumps(d.get("plans") or []),
                selected_option=int(d.get("selected_option") or 0))
    db.session.add(p)
    db.session.commit()
    return jsonify(project_json(p)), 201


@bp.route("/projects/<int:pid>", methods=["GET", "PUT", "DELETE"])
@login_required
@api
def project(pid):
    p = owned(pid)
    if not p:
        return jsonify(error="Project not found"), 404
    if request.method == "GET":
        return jsonify(project_json(p))
    if request.method == "DELETE":
        db.session.delete(p)
        db.session.commit()
        return jsonify(ok=True)
    d = body()
    if "name" in d:
        p.name = str(d["name"])[:150] or p.name
    if "inputs" in d:
        p.inputs_json = json.dumps(d["inputs"])
    if "plans" in d:
        for pl in d["plans"]:
            check_plan(pl)
        p.plans_json = json.dumps(d["plans"])
    if "selected_option" in d:
        p.selected_option = int(d["selected_option"])
    db.session.commit()
    return jsonify(project_json(p))


@bp.route("/projects/<int:pid>/duplicate", methods=["POST"])
@login_required
@api
def duplicate(pid):
    p = owned(pid)
    if not p:
        return jsonify(error="Project not found"), 404
    if Project.query.filter_by(user_id=current_user.id).count() >= PLAN_LIMITS.get(current_user.plan, 3):
        return jsonify(error="Project limit reached for your plan."), 402
    n = Project(user_id=current_user.id, name=(p.name + " (copy)")[:150], inputs_json=p.inputs_json,
                plans_json=p.plans_json, selected_option=p.selected_option)
    db.session.add(n)
    db.session.commit()
    return jsonify(project_json(n, False)), 201


# ---- exports --------------------------------------------------------------------------------
@bp.route("/log-download", methods=["POST"])
@login_required
@api
def log_download():
    d = body()
    kind = str(d.get("kind", ""))[:30]
    if kind not in ("png", "svg", "pdf_plan", "pdf_estimate", "screenshot_3d", "print"):
        raise ValueError("Unknown export kind.")
    p = owned(int(d.get("project_id") or 0))
    if p:
        db.session.add(DownloadLog(user_id=current_user.id, project_id=p.id, kind=kind))
        db.session.commit()
    return jsonify(ok=True)


@bp.route("/export/<kind>", methods=["POST"])
@login_required
@api
def export_pdf(kind):
    from services import pdf
    d = body()
    plan = check_plan(d.get("plan"))
    inputs = d.get("inputs") or {}
    name = str(d.get("name") or "SMARTGHAR Plan")[:100]
    if kind == "plan":
        data = pdf.plan_pdf(plan, name, current_app.config["DISCLAIMER"], current_user.name)
        fname, log = "naksha", "pdf_plan"
    elif kind == "estimate":
        city = d.get("city") or plan.get("plot", {}).get("city") or "Jaipur"
        prices = prices_for_city(city, overrides=d.get("overrides"), db_rows=db_prices(city))
        data = pdf.estimate_pdf(plan, estimate(plan, prices), city, name, current_app.config["DISCLAIMER"])
        fname, log = "estimate", "pdf_estimate"
    else:
        return jsonify(error="Unknown export"), 404
    p = owned(int(d.get("project_id") or 0))
    if p:
        db.session.add(DownloadLog(user_id=current_user.id, project_id=p.id, kind=log))
        db.session.commit()
    safe = "".join(c if c.isalnum() else "_" for c in name)[:40] or "smartghar"
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}_{fname}.pdf"'})
