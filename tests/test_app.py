"""API + auth smoke tests (SQLite in a temp file). Run: python -m pytest -q"""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from config import Config
from tests.sample_inputs import SAMPLES


@pytest.fixture()
def client():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
    class T(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + f.name
        TESTING = True
    from app import create_app
    app = create_app(T)
    with app.app_context():
        from models import db, User
        a = User(name="Admin", email="a@x.io", is_admin=True); a.set_password("Admin@12345"); db.session.add(a); db.session.commit()
    yield app.test_client()
    os.unlink(f.name)


def register(c, email="u@x.io"):
    return c.post("/register", data=dict(name="Test User", email=email, password="Passw0rd1", password2="Passw0rd1"), follow_redirects=True)


def test_public_pages(client):
    for u in ("/", "/house-plans", "/pricing", "/about", "/contact", "/tools", "/login", "/register"):
        assert client.get(u).status_code == 200


def test_auth_required(client):
    assert client.get("/dashboard").status_code == 302
    assert client.get("/api/projects").status_code == 401
    assert client.get("/admin/").status_code in (302, 401)


def test_register_login_and_admin_guard(client):
    assert register(client).status_code == 200
    assert client.get("/dashboard").status_code == 200
    assert client.get("/admin/").status_code == 403


def test_plot_and_generate(client):
    r = client.post("/api/plot/calc", json=dict(length=30, width=40, road="E"))
    assert r.status_code == 200 and abs(r.json["areas"]["sqft"] - 1200) < .1
    r = client.post("/api/generate", json=SAMPLES["30x40_east_2bhk_g1"])
    assert r.status_code == 200 and len(r.json["options"]) >= 2
    assert client.post("/api/generate", json=dict(length=3, width=4)).status_code == 400


def test_project_crud_estimate_pdf(client):
    register(client)
    gen = client.post("/api/generate", json=SAMPLES["20x50_north_1floor"]).json
    r = client.post("/api/projects", json=dict(name="P1", inputs=SAMPLES["20x50_north_1floor"], plans=gen["options"]))
    assert r.status_code == 201; pid = r.json["id"]
    assert client.get(f"/api/projects/{pid}").json["name"] == "P1"
    plan = gen["options"][0]
    fin = client.post("/api/finalize", json=dict(plan=plan)); assert fin.status_code == 200
    est = client.post("/api/estimate", json=dict(plan=plan, city="Delhi", overrides=dict(cement=500))).json
    assert est["estimate"]["total"] > 0 and est["prices"]["cement"]["price"] == 500
    for kind in ("plan", "estimate"):
        pdf = client.post(f"/api/export/{kind}", json=dict(plan=plan, project_id=pid, name="T"))
        assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
    assert client.delete(f"/api/projects/{pid}").status_code == 200


def test_free_plan_limit_and_ownership(client):
    register(client)
    for i in range(3):
        assert client.post("/api/projects", json=dict(name=f"p{i}", inputs={}, plans=[])).status_code == 201
    assert client.post("/api/projects", json=dict(name="p4", inputs={}, plans=[])).status_code == 402
    client.get("/logout"); register(client, "other@x.io")
    assert client.get("/api/projects/1").status_code == 404


def test_tools(client):
    r = client.post("/api/tools/concrete", json=dict(length=20, width=15, thickness_in=5, mix="M20"))
    assert r.status_code == 200 and r.json["results"]
    assert client.post("/api/tools/area", json=dict(shape="rectangle", a=-1, b=2)).status_code == 400
    assert client.post("/api/tools/nope", json={}).status_code == 400
