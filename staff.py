"""Staff area: login, the day list for reception and doctors, status changes and the waiting-room view.

Roles:
- reception: sees every doctor's appointments (names, contact details, times, status).
- doctor: sees only their own patients, including the reason for visit and the questionnaire answers.
Every login and every list view is written to the audit log.
"""
import logging
import re
from functools import wraps

from flask import (
    Blueprint, abort, current_app, g, redirect, render_template, request, session, url_for,
)
from flask import jsonify
from werkzeug.security import check_password_hash

from notifications import send_confirmation
from security import csrf_valid, rate_allowed

bp = Blueprint("staff", __name__, url_prefix="/staff")
log = logging.getLogger(__name__)

STATUS_CHOICES = ("requested", "confirmed", "done", "cancelled")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _ext(name):
    return current_app.extensions[name]


def _current_user():
    user_id = session.get("staff_user_id")
    if not user_id:
        return None
    user = _ext("store").get_user(user_id)
    return user if user and user["active"] else None


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if user is None:
            return redirect(url_for("staff.login"))
        g.staff = user
        return view(*args, **kwargs)

    return wrapper


@bp.before_request
def _check_csrf():
    if request.method == "POST" and not csrf_valid(request.form.get("csrf_token")):
        abort(403)


@bp.route("/login", methods=["GET", "POST"])
def login():
    error, status = None, 200
    if request.method == "POST":
        store = _ext("store")
        if not rate_allowed("login"):
            error, status = "Too many attempts. Please wait 15 minutes and try again.", 429
        else:
            email = request.form.get("email", "").strip().lower()[:254]
            user = store.get_user_by_email(email)
            password = request.form.get("password", "")
            if user and user["active"] and check_password_hash(user["password_hash"], password):
                session.clear()
                session["staff_user_id"] = user["id"]
                store.audit(email, "login")
                return redirect(url_for("staff.dashboard"))
            store.audit(email or "unknown", "login-failed")
            error, status = "Invalid email or password.", 401
    return render_template("staff_login.html", error=error), status


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("staff.login"))


@bp.get("/")
@login_required
def dashboard():
    clinic = _ext("clinic")
    store = _ext("store")
    user = g.staff
    if user["role"] == "doctor" and not user["doctor_id"]:
        abort(403)  # a doctor account without a doctor cannot see any list

    today = clinic.now().date().isoformat()
    day = request.args.get("date", "")
    if not DAY_RE.match(day):
        day = today
    waiting = request.args.get("view") == "waiting"

    if user["role"] == "doctor":
        doctor_filter = user["doctor_id"]
    else:
        doctor_filter = request.args.get("doctor_id") or None
        if doctor_filter not in clinic.by_id:
            doctor_filter = None

    rows = clinic.list_views(doctor_filter, day)
    if waiting:
        rows = [r for r in rows if r["status"] in ("requested", "confirmed")]
    store.audit(user["email"], f"view:{'waiting' if waiting else 'day'}:{day}")

    return render_template(
        "staff_dashboard.html",
        rows=rows,
        day=day,
        today=today,
        waiting=waiting,
        staff=user,
        doctors=clinic.doctors,
        doctor_filter=doctor_filter,
        can_see_health=user["role"] == "doctor",
        statuses=STATUS_CHOICES,
        audit=store.recent_audit(15) if user["role"] == "reception" else [],
    )


@bp.post("/appointments/<int:appt_id>/status")
@login_required
def set_status(appt_id):
    clinic = _ext("clinic")
    store = _ext("store")
    user = g.staff
    row = store.get_appointment(appt_id)
    if row is None:
        abort(404)
    if user["role"] == "doctor" and row["doctor_id"] != user["doctor_id"]:
        abort(403)
    status = request.form.get("status", "")
    if status not in STATUS_CHOICES:
        abort(400)

    previous = row["status"]
    clinic.set_status(appt_id, status, actor=user["email"])
    if status == "confirmed" and previous == "requested":
        try:
            send_confirmation(current_app.config, clinic.view(store.get_appointment(appt_id)))
        except Exception:  # a mail problem must not block the staff workflow
            log.exception("Confirmation email failed for appointment %s", appt_id)

    args = {"date": row["starts_at"][:10]}
    if request.form.get("view") == "waiting":
        args["view"] = "waiting"
    return redirect(url_for("staff.dashboard", **args))

@bp.get("/requests")
@login_required
def open_requests():
    user = g.staff
    if user["role"] == "doctor" and not user["doctor_id"]:
        abort(403)
    doctor_filter = user["doctor_id"] if user["role"] == "doctor" else None
    rows = _ext("store").list_appointments(doctor_filter)
    ids = sorted(row["id"] for row in rows if row["status"] == "requested")
    return jsonify({"ids": ids, "count": len(ids)})
