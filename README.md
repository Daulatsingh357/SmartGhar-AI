# SMARTGHAR AI - AI-Powered House Planning & 3D Architecture Studio

Enter plot size, road direction, Vastu preference, rooms and floors, and get **three dimension-accurate 2D nakshas**,
an **interactive 3D house**, a Vastu score, a construction cost estimate and a full drawing set (PDF / PNG / SVG).

> **All designs are preliminary planning concepts.** Obtain professional architectural review and structural safety
> verification, and confirm local bye-laws and setbacks, before construction.

## What is real (and what is not)
* **Geometry-first engine** (`engine/`): rooms tile the buildable rectangle exactly (no overlaps), coordinates are real feet snapped to 0.5 ft,
  setbacks come from a plot-size table (override in the form), minimum room sizes are validated. Plans are *not* AI pictures.
* **3D** (`static/js/viewer3d.js`) is generated from the same geometry: walls with real door/window openings, slabs, roofs, furniture, day/night.
* **LLM** is optional and used only for written commentary (`LLM_API_KEY`). Layouts never depend on it - without a key a rule-based summary is shown.
* Quantities / rates are thumb-rule planning values, **not** a Bill of Quantities. Setback values are typical defaults, not your municipality's by-laws.
* Billing/subscriptions are a **demo** (no payment gateway). The contact form acknowledges but does not email.

## Features
Homepage + gallery + pricing - registration/login/profile - dashboard (saved projects, recent designs, downloads) - smart plot calculator
(sq ft / sq m / sq yd, rectangle, trapezium, L-shape, custom polygon) - 15 room types with custom sizes - Vastu (strict / flexible / normal) with score and
explanations - 2D editor (zoom/pan, grid, drag-swap rooms, move shared walls with handles, resize, door/window drag & add/delete, undo/redo, 3 layouts) -
3D (exterior, interior, top/front/side, spin, day/night, floor isolation, roof types, materials, drag furniture) - basement / G+3 / terrace - cost estimator with
editable city rates - 11 civil calculators - 10 drawing types - PDF/PNG/SVG/3D screenshot/print - admin panel (users, projects, templates, prices, subscriptions, content, analytics).

## Windows (CMD) installation
```bat
:: 1. Install Python 3.10+ from python.org (tick "Add Python to PATH")
cd smartghar
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

:: 2. Configure
copy .env.example .env
notepad .env

:: 3. Create tables + admin + demo data + templates + city prices
python seed.py

:: 4. Run
python app.py
:: open http://127.0.0.1:5000
```
Default logins after `seed.py`: **admin** `admin@smartghar.local` / `Admin@12345`, **demo** `demo@smartghar.local` / `Demo@12345`. Change the admin password in `.env` before deploying.

### MySQL (optional; SQLite is used if `DATABASE_URL` is empty)
```bat
mysql -u root -p < schema.sql
mysql -u root -p -e "CREATE USER 'smartghar'@'localhost' IDENTIFIED BY 'password'; GRANT ALL ON smartghar.* TO 'smartghar'@'localhost';"
```
then set `DATABASE_URL=mysql+pymysql://smartghar:password@localhost:3306/smartghar?charset=utf8mb4` in `.env` and run `python seed.py`.

## Tests
```bat
python tests\test_engine.py     :: geometry checks on 4 sample plots x 3 layouts
python -m pytest -q             :: API / auth / PDF / limits
```
Sample projects live in `tests/sample_inputs.py` and are loaded as templates + demo projects by `seed.py`.

## Layout
```
app.py  config.py  models.py  schema.sql  seed.py  requirements.txt  .env.example
engine/   plot.py layout.py vastu.py furniture.py plan.py estimator.py tools.py geom.py
routes/   pages.py auth.py api.py admin.py
services/ pdf.py (ReportLab vector drawings)  llm.py  thumb.py
static/   css/  js/ (plan2d editor2d drawings viewer3d studio panels)  vendor/ (three.js r128, MIT)
templates/ ...
```

## Known limitations
* Layouts are a slicing partition of one buildable rectangle; irregular plots use the largest inscribed rectangle.
* Moving a staircase wall on one floor does not auto-move it on other floors (a validation note flags misalignment).
* Interface styling is custom CSS (Google Fonts load from the web; 3D needs no CDN). Tailwind is not bundled.
* Production: set a strong `SECRET_KEY`, run behind gunicorn/waitress + HTTPS, add CSRF protection (e.g. Flask-WTF) to the HTML forms and rate-limiting to login.
