"""Public website: pages, booking and chat API, chat history and the live-update stream."""
import logging
import re

from flask import (
    Blueprint, Response, abort, current_app, g, jsonify, redirect, render_template,
    request, stream_with_context, url_for,
)

from clinic import BookingError, parse_day, parse_time
from i18n import LANGS, render_error, specialty_name, t
from security import csrf_token, csrf_valid, rate_allowed

bp = Blueprint("web", __name__)
log = logging.getLogger(__name__)

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
STREAM_TIMEOUT_SECONDS = 25
LANG_COOKIE_DAYS = 365


def _clinic():
    return current_app.extensions["clinic"]


def _bot():
    return current_app.extensions["bot"]


def _stamp():
    return _clinic().now().strftime("%H:%M:%S")


def _pick_language():
    """Explicit ?lang= wins, then the language cookie, then the browser's Accept-Language header."""
    for value in (request.args.get("lang"), request.cookies.get("lang")):
        if value in LANGS:
            return value
    return request.accept_languages.best_match(LANGS) or "en"


def _err(key, status, **params):
    return jsonify(error=t(key, g.lang, **params), key=key), status


def _limited():
    return jsonify(error=t("rate_limited", g.lang), key="rate_limited"), 429


@bp.before_request
def _before():
    g.lang = _pick_language()
    if request.method == "POST" and not csrf_valid(request.headers.get("X-CSRF-Token")):
        return _err("generic_error", 403)


@bp.app_context_processor
def _template_helpers():
    lang = g.get("lang", "en")
    return {
        "lang": lang,
        "langs": LANGS,
        "T": lambda key, **params: t(key, lang, **params),
        "specialty_name": lambda name: specialty_name(name, lang),
        "csrf_token": csrf_token,
        "clinic_name": current_app.config["CLINIC_NAME"],
    }


def _doctor_json(doctor, lang):
    clinic = _clinic()
    return {
        "id": doctor["id"],
        "name": doctor["name"],
        "specialty": specialty_name(doctor["specialty"], lang),
        "bio": doctor.get("bio", ""),
        "days": clinic.days_text(doctor, lang),
    }


# ----- pages -----

@bp.get("/")
def index():
    doctors = [_doctor_json(d, g.lang) for d in _clinic().doctors]
    strings = {key: t(key, g.lang) for key in I18N_KEYS}
    return render_template(
        "index.html", doctors=doctors, strings=strings, retention_days=_clinic().retention_days,
    )


@bp.get("/lang/<code>")
def set_language(code):
    if code not in LANGS:
        abort(404)
    response = redirect(url_for("web.index", lang=code))
    response.set_cookie(
        "lang", code, max_age=LANG_COOKIE_DAYS * 24 * 3600, samesite="Lax",
        secure=current_app.config["SESSION_COOKIE_SECURE"],
    )
    return response


@bp.get("/privacy")
def privacy():
    return render_template("page.html", title_key="privacy_title", body_key="privacy_text")


@bp.get("/imprint")
def imprint():
    return render_template("page.html", title_key="imprint_title", body_key="imprint_text")


# ----- JSON API -----

@bp.get("/api/doctors")
def api_doctors():
    return jsonify([_doctor_json(d, g.lang) for d in _clinic().doctors])


@bp.get("/api/availability")
def api_availability():
    match = MONTH_RE.match(request.args.get("month", ""))
    if not match:
        return _err("err_month", 400)
    days = _clinic().availability(request.args.get("doctor_id", ""), int(match[1]), int(match[2]))
    return jsonify(days=days, updated_at=_stamp())


@bp.get("/api/slots")
def api_slots():
    clinic = _clinic()
    doctor_id = request.args.get("doctor_id", "")
    day = parse_day(request.args.get("date", ""))
    if day is None:
        return _err("err_date_format", 400)
    try:
        clinic.validate_day(doctor_id, day)
    except BookingError as exc:
        return jsonify(error=render_error(exc, g.lang), key=exc.key, slots=[]), 400
    return jsonify(slots=clinic.slots(doctor_id, day), updated_at=_stamp())


@bp.post("/api/appointments")
def api_book():
    if not rate_allowed("booking"):
        return _limited()
    data = request.get_json(silent=True) or {}
    intake = data.get("intake") if isinstance(data.get("intake"), dict) else {}
    try:
        day = parse_day(str(data.get("date", "")))
        if day is None:
            raise BookingError("err_date_format")
        appt_id = _clinic().book(
            str(data.get("doctor_id", "")),
            day,
            parse_time(str(data.get("time", ""))) or "",
            str(data.get("name", "")),
            str(data.get("contact", "")),
            str(data.get("reason", ""))[:500],
            intake=intake,
            consent=data.get("consent") is True,
            source="web",
            lang=g.lang,
        )
    except BookingError as exc:
        return jsonify(error=render_error(exc, g.lang), key=exc.key), 400
    return jsonify(id=appt_id, status="requested", message=t("request_sent", g.lang, id=appt_id)), 201


@bp.post("/api/chat")
def api_chat():
    if not rate_allowed("chat"):
        return _limited()
    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id", ""))
    if not SESSION_ID_RE.match(session_id):
        return _err("err_session", 400)
    return jsonify(_bot().reply(session_id, str(data.get("message", "")), lang=g.lang))


@bp.get("/api/chat/history")
def api_chat_history():
    session_id = request.args.get("session_id", "")
    if not SESSION_ID_RE.match(session_id):
        return _err("err_session", 400)
    history = _bot().history(session_id)
    return jsonify(history if history is not None else {"lang": g.lang, "messages": []})


@bp.get("/api/stream")
def api_stream():
    """Server-Sent Events: one 'change' event whenever an appointment changes. Clients refetch the data."""
    bus = current_app.extensions["bus"]

    def events():
        last = bus.version
        yield "retry: 3000\n\n"
        yield f"event: ready\ndata: {last}\n\n"
        while True:
            current = bus.wait_for_change(last, timeout=STREAM_TIMEOUT_SECONDS)
            if current != last:
                last = current
                yield f"event: change\ndata: {current}\n\n"
            else:
                yield ": ping\n\n"

    return Response(
        stream_with_context(events()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Strings the browser script needs. Sent as JSON so no text is hard-coded in JavaScript.
I18N_KEYS = [
    "live_updated", "free_slots", "fully_booked", "not_available", "sending", "request_sent",
    "generic_error", "network_error", "chat_greeting", "book_with", "pick_date", "pick_date_slots",
    "no_free_day", "choose_doctor_first", "calendar_error", "selected_none", "selected_fmt",
    "date_only_fmt", "rate_limited", "chat_new", "chat_placeholder", "err_consent",
    "err_name", "err_contact", "err_slot_taken", "err_slot_unavailable",
    "bot_greet_morning", "bot_greet_afternoon", "bot_greet_evening", "bot_how_help",
]