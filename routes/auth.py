import re
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _safe_next(target):
    if not target:
        return None
    u = urlparse(target)
    return target if not u.netloc and not u.scheme and target.startswith("/") and not target.startswith("//") else None


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))
    if request.method == "POST":
        f = request.form
        name, email = f.get("name", "").strip(), f.get("email", "").strip().lower()
        pw, pw2 = f.get("password", ""), f.get("password2", "")
        err = None
        if len(name) < 2:
            err = "Please enter your name."
        elif not EMAIL_RE.match(email):
            err = "Enter a valid email address."
        elif len(pw) < 8 or not re.search(r"\d", pw) or not re.search(r"[A-Za-z]", pw):
            err = "Password must be 8+ characters with letters and numbers."
        elif pw != pw2:
            err = "Passwords do not match."
        elif User.query.filter_by(email=email).first():
            err = "An account with this email already exists."
        if err:
            flash(err, "error")
            return render_template("auth/register.html", form=f)
        u = User(name=name, email=email, phone=f.get("phone", "").strip()[:30], city=f.get("city", "").strip()[:80])
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash("Welcome to SMARTGHAR AI!", "success")
        return redirect(url_for("pages.dashboard"))
    return render_template("auth/register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(request.form.get("password", "")):
            if not u.is_active_user:
                flash("This account has been disabled. Contact support.", "error")
                return render_template("auth/login.html")
            login_user(u, remember=bool(request.form.get("remember")))
            return redirect(_safe_next(request.args.get("next")) or url_for("pages.dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("pages.home"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        f = request.form
        action = f.get("action")
        if action == "password":
            if not current_user.check_password(f.get("current", "")):
                flash("Current password is incorrect.", "error")
            elif len(f.get("new", "")) < 8 or f.get("new") != f.get("new2"):
                flash("New password must be 8+ characters and match the confirmation.", "error")
            else:
                current_user.set_password(f["new"])
                db.session.commit()
                flash("Password updated.", "success")
        else:
            name = f.get("name", "").strip()
            if len(name) < 2:
                flash("Please enter your name.", "error")
            else:
                current_user.name = name[:120]
                current_user.phone = f.get("phone", "").strip()[:30]
                current_user.city = f.get("city", "").strip()[:80]
                db.session.commit()
                flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")
