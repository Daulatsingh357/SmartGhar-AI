import json
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, User, Project, Template, MaterialPrice, SiteContent, Subscription, DownloadLog
from engine.estimator import DEFAULT_PRICES, CITY_FACTORS

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(fn):
    @wraps(fn)
    @login_required
    def w(*a, **k):
        if not current_user.is_admin:
            abort(403)
        return fn(*a, **k)
    return w


@bp.route("/")
@admin_required
def index():
    now = datetime.utcnow()
    days = [(now - timedelta(days=i)).date() for i in range(13, -1, -1)]
    def series(model, col):
        rows = db.session.query(func.date(col), func.count()).filter(col >= now - timedelta(days=14)).group_by(func.date(col)).all()
        m = {str(d): n for d, n in rows}
        return [m.get(str(d), 0) for d in days]
    stats = dict(users=User.query.count(), projects=Project.query.count(), downloads=DownloadLog.query.count(),
                 templates=Template.query.count(), paid=User.query.filter(User.plan != "free").count())
    plans = dict(db.session.query(User.plan, func.count()).group_by(User.plan).all())
    kinds = dict(db.session.query(DownloadLog.kind, func.count()).group_by(DownloadLog.kind).all())
    return render_template("admin/index.html", stats=stats, plans=plans, kinds=kinds,
                           labels=[d.strftime("%d %b") for d in days],
                           s_users=series(User, User.created_at), s_projects=series(Project, Project.created_at))


@bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "POST":
        u = db.session.get(User, request.form.get("id", type=int))
        act = request.form.get("action")
        if u and u.id != current_user.id:
            if act == "toggle":
                u.is_active_user = not u.is_active_user
            elif act == "admin":
                u.is_admin = not u.is_admin
            elif act == "plan" and request.form.get("plan") in ("free", "pro", "studio"):
                u.plan = request.form["plan"]
                db.session.add(Subscription(user_id=u.id, plan=u.plan, status="active", ends_at=now30() if u.plan != "free" else None))
            elif act == "delete":
                db.session.delete(u)
            db.session.commit()
        else:
            flash("You cannot modify your own account here.", "error")
        return redirect(url_for("admin.users"))
    return render_template("admin/users.html", users=User.query.order_by(User.id).all())


def now30():
    return datetime.utcnow() + timedelta(days=30)


@bp.route("/projects", methods=["GET", "POST"])
@admin_required
def projects():
    if request.method == "POST":
        p = db.session.get(Project, request.form.get("id", type=int))
        if p:
            db.session.delete(p)
            db.session.commit()
        return redirect(url_for("admin.projects"))
    rows = db.session.query(Project, User).join(User, User.id == Project.user_id).order_by(Project.updated_at.desc()).all()
    return render_template("admin/projects.html", rows=rows)


@bp.route("/templates", methods=["GET", "POST"])
@admin_required
def templates():
    if request.method == "POST":
        act = request.form.get("action")
        if act == "delete":
            t = db.session.get(Template, request.form.get("id", type=int))
            if t:
                db.session.delete(t)
        else:
            try:
                inputs = json.loads(request.form.get("inputs_json", ""))
                assert isinstance(inputs, dict)
            except Exception:
                flash("Inputs must be a valid JSON object.", "error")
                return redirect(url_for("admin.templates"))
            tid = request.form.get("id", type=int)
            t = db.session.get(Template, tid) if tid else Template()
            t.title = request.form.get("title", "Untitled")[:150]
            t.description = request.form.get("description", "")
            t.inputs_json = json.dumps(inputs)
            t.featured = bool(request.form.get("featured"))
            db.session.add(t)
        db.session.commit()
        return redirect(url_for("admin.templates"))
    return render_template("admin/templates.html", templates=Template.query.order_by(Template.id).all())


@bp.route("/prices", methods=["GET", "POST"])
@admin_required
def prices():
    city = (request.values.get("city") or "Jaipur").strip()
    if request.method == "POST":
        for k, (label, unit, base) in DEFAULT_PRICES.items():
            v = request.form.get(k)
            if v in (None, ""):
                continue
            try:
                val = float(v)
            except ValueError:
                continue
            row = MaterialPrice.query.filter_by(city=city, key=k).first() or MaterialPrice(city=city, key=k, label=label, unit=unit, price=val)
            row.price = val
            db.session.add(row)
        db.session.commit()
        flash(f"Prices saved for {city}.", "success")
        return redirect(url_for("admin.prices", city=city))
    from engine.estimator import prices_for_city
    cur = prices_for_city(city, db_rows=[dict(key=r.key, label=r.label, unit=r.unit, price=r.price) for r in MaterialPrice.query.filter_by(city=city)])
    return render_template("admin/prices.html", city=city, prices=cur, cities=sorted(CITY_FACTORS))


@bp.route("/subscriptions")
@admin_required
def subscriptions():
    rows = db.session.query(Subscription, User).join(User, User.id == Subscription.user_id).order_by(Subscription.id.desc()).all()
    return render_template("admin/subscriptions.html", rows=rows)


@bp.route("/content", methods=["GET", "POST"])
@admin_required
def content():
    from app import DEFAULT_CONTENT
    if request.method == "POST":
        for k in DEFAULT_CONTENT:
            if k in request.form:
                row = SiteContent.query.filter_by(key=k).first() or SiteContent(key=k)
                row.value = request.form[k]
                db.session.add(row)
        db.session.commit()
        flash("Website content updated.", "success")
        return redirect(url_for("admin.content"))
    from app import site_content
    return render_template("admin/content.html", content=site_content(), keys=list(DEFAULT_CONTENT))
