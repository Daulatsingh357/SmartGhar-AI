import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import db, Project, DownloadLog, Template, MaterialPrice, User, Subscription
from datetime import datetime, timedelta

bp = Blueprint("pages", __name__)

PLANS = [
    dict(key="free", name="Starter", price="Free", period="", features=["3 saved projects", "3 layout options per design", "2D naksha + 3D viewer", "PNG / SVG export", "Civil calculators"]),
    dict(key="pro", name="Professional", price="₹999", period="/month", features=["Unlimited projects", "PDF naksha + estimate PDF", "Electrical & plumbing layouts", "Elevations, section & site plan", "Priority AI commentary"], highlight=True),
    dict(key="studio", name="Studio", price="₹2,999", period="/month", features=["Everything in Professional", "Team seats (5)", "Custom material price books", "Template library access", "White-label PDF exports"]),
]
PLAN_LIMITS = {"free": 3, "pro": 10**6, "studio": 10**6}


@bp.route("/")
def home():
    featured = Template.query.filter_by(featured=True).order_by(Template.id).limit(6).all()
    return render_template("home.html", featured=featured)


@bp.route("/house-plans")
def house_plans():
    return render_template("plans.html", templates=Template.query.order_by(Template.id).all())


@bp.route("/pricing")
def pricing():
    return render_template("pricing.html", plans=PLANS)


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        if request.form.get("name") and request.form.get("email") and request.form.get("message"):
            flash("Thanks! Your message has been received - we will reply shortly.", "success")
            return redirect(url_for("pages.contact"))
        flash("Please fill in all fields.", "error")
    return render_template("contact.html")


@bp.route("/tools")
def tools():
    return render_template("tools.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.updated_at.desc()).all()
    downloads = (DownloadLog.query.filter_by(user_id=current_user.id)
                 .order_by(DownloadLog.created_at.desc()).limit(20).all())
    names = {p.id: p.name for p in projects}
    return render_template("dashboard.html", projects=projects, downloads=downloads, names=names,
                           limit=PLAN_LIMITS.get(current_user.plan, 3))


@bp.route("/studio")
@login_required
def studio_new():
    tpl = request.args.get("template", type=int)
    inputs = None
    if tpl:
        t = db.session.get(Template, tpl)
        if t:
            inputs = json.loads(t.inputs_json)
            inputs["name"] = t.title
    return render_template("studio.html", project=None, preset=inputs)


@bp.route("/studio/<int:pid>")
@login_required
def studio(pid):
    p = db.session.get(Project, pid)
    if not p or (p.user_id != current_user.id and not current_user.is_admin):
        abort(404)
    return render_template("studio.html", project=p, preset=None)


@bp.route("/subscribe/<plan>", methods=["POST"])
@login_required
def subscribe(plan):
    if plan not in PLAN_LIMITS:
        abort(404)
    current_user.plan = plan
    db.session.add(Subscription(user_id=current_user.id, plan=plan, status="active",
                                ends_at=datetime.utcnow() + timedelta(days=30) if plan != "free" else None))
    db.session.commit()
    flash(f"Plan changed to {plan.title()}. (Demo billing - no payment taken.)", "success")
    return redirect(url_for("pages.dashboard"))
