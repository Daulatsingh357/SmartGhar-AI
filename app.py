"""SMARTGHAR AI - Flask application factory."""
import json
import os
from flask import Flask, render_template, jsonify, request
from flask_login import LoginManager
from config import Config
from models import db, User

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify(error="Please log in to continue."), 401
    from flask import redirect, url_for, flash
    flash("Please log in to continue.", "info")
    return redirect(url_for("auth.login", next=request.path))


def create_app(config_obj=Config):
    app = Flask(__name__)
    app.config.from_object(config_obj)
    app.config.setdefault("MAX_CONTENT_LENGTH", 2 * 1024 * 1024)
    db.init_app(app)
    login_manager.init_app(app)

    from routes.pages import bp as pages_bp
    from routes.auth import bp as auth_bp
    from routes.api import bp as api_bp
    from routes.admin import bp as admin_bp
    for b in (pages_bp, auth_bp, api_bp, admin_bp):
        app.register_blueprint(b)

    @app.template_filter("fromjson")
    def fromjson(s):
        try:
            return json.loads(s)
        except Exception:
            return {}

    @app.template_filter("thumb")
    def thumb(s):
        from services.thumb import thumb_svg
        from markupsafe import Markup
        return Markup(thumb_svg(s))

    @app.context_processor
    def inject():
        return dict(disclaimer=app.config["DISCLAIMER"], site=site_content())

    @app.errorhandler(404)
    def nf(e):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found"), 404
        return render_template("error.html", code=404, msg="Page not found"), 404

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify(error="Forbidden"), 403
        return render_template("error.html", code=403, msg="You do not have access to this page"), 403

    @app.errorhandler(500)
    def ise(e):
        if request.path.startswith("/api/"):
            return jsonify(error="Server error"), 500
        return render_template("error.html", code=500, msg="Something went wrong"), 500

    with app.app_context():
        db.create_all()
    return app


DEFAULT_CONTENT = {
    "hero_title": "Design your dream home in minutes",
    "hero_sub": "Enter your plot size, choose Vastu preferences and rooms - SMARTGHAR AI generates a dimension-accurate 2D naksha and an interactive 3D house.",
    "about": "SMARTGHAR AI combines a geometry-based layout engine, Vastu Shastra rules and civil engineering estimators so families, builders and architects can explore realistic plans before they hire a professional.",
    "contact_email": "hello@smartghar.local",
    "contact_phone": "+91 00000 00000",
    "contact_address": "Jaipur, Rajasthan, India",
}


def site_content():
    try:
        from models import SiteContent
        d = dict(DEFAULT_CONTENT)
        for r in SiteContent.query.all():
            d[r.key] = r.value
        return d
    except Exception:
        return dict(DEFAULT_CONTENT)


if __name__ == "__main__":
    create_app().run(debug=os.getenv("FLASK_DEBUG", "1") == "1", port=int(os.getenv("PORT", "5000")))
