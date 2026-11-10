import os
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or "sqlite:///" + os.path.join(BASE_DIR, "smartghar.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LLM_API_URL = os.getenv("LLM_API_URL", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@smartghar.local")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@12345")
    DISCLAIMER = ("All designs are preliminary planning concepts. Obtain professional architectural review "
                  "and structural safety verification, and confirm local bye-laws, before construction.")
