"""Application factory: wires configuration, storage, encryption, the chatbot and the web and staff areas.

Run locally:      python app.py            (http://127.0.0.1:8000)
Run in production: see README (gunicorn, CLINIC_ENV=production, secrets from the environment).
"""
import json
import logging
import os
import secrets
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from chatbot import ChatBot
from clinic import Clinic
from config import Config
import accounts
from notifications import notify_staff_new_request
from crypto import Vault
from i18n import t
from llm import LLMClient
from notifier import ChangeBus
from rag import KnowledgeIndex
from security import RateLimiter, apply_security_headers
from staff import bp as staff_bp
from store import Store
from web import _pick_language, bp as web_bp

BASE_DIR = Path(__file__).resolve().parent
log = logging.getLogger(__name__)
_AUTO = object()  # sentinel: use the Claude client if ANTHROPIC_API_KEY is set


def _load(name):
    return json.loads((BASE_DIR / "data" / name).read_text(encoding="utf-8"))


def create_app(overrides=None, llm=_AUTO):
    Config.check_production()
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    if not app.config["SECRET_KEY"]:
        # Development only: a random key means sessions end on restart. Production refuses to start without one.
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    Path(app.config["INSTANCE_DIR"]).mkdir(parents=True, exist_ok=True)

    doctors = _load("doctors.json")
    store = Store(app.config["DATABASE"])
    accounts.ensure_schema(store)
    bootstrap_email = os.environ.get("BOOTSTRAP_STAFF_EMAIL", "").strip().lower()
    bootstrap_hash = os.environ.get("BOOTSTRAP_STAFF_PASSWORD_HASH", "")
    if bootstrap_email and bootstrap_hash and store.get_user_by_email(bootstrap_email) is None:
        store.create_user(
            email=bootstrap_email,
            password_hash=bootstrap_hash,
            role=os.environ.get("BOOTSTRAP_STAFF_ROLE", "reception"),
            doctor_id=os.environ.get("BOOTSTRAP_STAFF_DOCTOR_ID") or None,
        )
    vault = Vault.from_config(app.config)
    bus = ChangeBus()
    clinic = Clinic(
        doctors, store, vault, bus,
        tz_name=app.config["CLINIC_TZ"],
        retention_days=app.config["RETENTION_DAYS"],
    )
    clinic.on_new_request = lambda appt_id: notify_staff_new_request(app.config, store, appt_id)
    index = KnowledgeIndex(_load("knowledge.json"))
    if llm is _AUTO:
        llm = LLMClient.from_env()
    bot = ChatBot(clinic, index, store, vault, llm=llm, privacy_url="/privacy")

    app.extensions.update(store=store, vault=vault, clinic=clinic, bus=bus, bot=bot, limiter=RateLimiter())
    app.register_blueprint(web_bp)
    app.register_blueprint(staff_bp)

    @app.after_request
    def _security_headers(response):
        return apply_security_headers(response)

    @app.errorhandler(HTTPException)
    def _http_error(exc):
        g.lang = _pick_language()
        key = {404: "error_404", 429: "rate_limited", 500: "error_500"}.get(exc.code, "error_generic")
        if request.path.startswith("/api/"):
            return jsonify(error=t(key, g.lang), key=key), exc.code
        return render_template("error.html", status=exc.code, message_key=key), exc.code

    @app.errorhandler(Exception)
    def _unexpected(exc):
        log.exception("Unhandled error")
        return _http_error(_as_500())

    return app


def _as_500():
    from werkzeug.exceptions import InternalServerError

    return InternalServerError()


if __name__ == "__main__":
    create_app().run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8000")),  # 5000 is used by AirPlay Receiver on macOS
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )