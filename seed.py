"""Create tables, the admin account, material prices, house templates and a demo user with sample projects.
Usage:  python seed.py"""
import json
from app import create_app
from config import Config
from models import db, User, Project, Template, MaterialPrice
from engine.estimator import DEFAULT_PRICES, CITY_FACTORS
from engine.plan import generate_plans
from tests.sample_inputs import SAMPLES

TEMPLATES = [
    ("Compact 2BHK - 30x40 East facing", "Vastu-friendly two-storey home with pooja room and parking.", "30x40_east_2bhk_g1"),
    ("Narrow Plot 20x50 North facing", "Efficient single-floor plan with terrace for narrow urban plots.", "20x50_north_1floor"),
    ("Luxury Villa 40x60 South facing", "Basement + three floors for a large joint family.", "40x60_south_3floors"),
    ("1200 sq ft West facing", "Starter home generated from area alone.", "area_only_1200_west"),
]


def run():
    app = create_app()
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email=Config.ADMIN_EMAIL).first():
            a = User(name="Administrator", email=Config.ADMIN_EMAIL, is_admin=True, plan="studio", city="Jaipur")
            a.set_password(Config.ADMIN_PASSWORD)
            db.session.add(a)
        demo = User.query.filter_by(email="demo@smartghar.local").first()
        if not demo:
            demo = User(name="Demo User", email="demo@smartghar.local", city="Jaipur", plan="pro")
            demo.set_password("Demo@12345")
            db.session.add(demo)
        if MaterialPrice.query.count() == 0:
            for city, f in CITY_FACTORS.items():
                for k, (label, unit, price) in DEFAULT_PRICES.items():
                    db.session.add(MaterialPrice(city=city, key=k, label=label, unit=unit, price=round(price * f, 2)))
        if Template.query.count() == 0:
            for title, desc, key in TEMPLATES:
                db.session.add(Template(title=title, description=desc, inputs_json=json.dumps(SAMPLES[key])))
        db.session.commit()
        if Project.query.filter_by(user_id=demo.id).count() == 0:
            for title, desc, key in TEMPLATES[:2]:
                res = generate_plans(SAMPLES[key])
                db.session.add(Project(user_id=demo.id, name=title, inputs_json=json.dumps(SAMPLES[key]),
                                       plans_json=json.dumps(res["options"])))
            db.session.commit()
        print("Seed complete.")
        print(f"  Admin: {Config.ADMIN_EMAIL} / {Config.ADMIN_PASSWORD}")
        print("  Demo : demo@smartghar.local / Demo@12345")


if __name__ == "__main__":
    run()
