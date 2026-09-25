from __future__ import annotations
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

APP_NAME = os.getenv("APP_NAME", "There Is Another Path")
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "The Path Finder")
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:8000").rstrip("/")
_legacy_db_path = os.getenv("DATABASE_PATH", str(DATA_DIR / "pathfinder.db"))
_default_sqlite = f"sqlite:///{Path(_legacy_db_path).as_posix()}"
DATABASE_URL = (os.getenv("DATABASE_URL") or _default_sqlite).strip()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "").strip()
PRODUCT_PRICE_USD = int(os.getenv("PRODUCT_PRICE_USD", "19"))
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in {"1", "true", "yes", "on"}
META_PIXEL_ID = os.getenv("META_PIXEL_ID", "").strip()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-before-production")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "thereisanotherp4th@gmail.com")
SELLER_LEGAL_NAME = os.getenv("SELLER_LEGAL_NAME", "").strip()
BILLING_LABEL = os.getenv("BILLING_LABEL", "RIQUELME").strip()
REFUND_DAYS = int(os.getenv("REFUND_DAYS", "7"))


# Privacy & session security
DATA_ENCRYPTION_KEY = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "pf_session").strip() or "pf_session"
SESSION_COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE",
    "true" if PUBLIC_BASE_URL.startswith("https://") else "false"
).lower() in {"1", "true", "yes", "on"}
ASSESSMENT_RETENTION_DAYS = int(os.getenv("ASSESSMENT_RETENTION_DAYS", "90"))
EXPOSE_API_DOCS = os.getenv("EXPOSE_API_DOCS", "false").lower() in {"1", "true", "yes", "on"}
