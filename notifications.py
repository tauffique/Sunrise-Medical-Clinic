"""Confirmation and reminder emails, with a calendar (.ics) attachment.

Without SMTP_HOST, emails are written to instance/outbox as .eml files so the flow can
be tested locally. Only patients who gave an email address receive emails; SMS is not
supported.
"""
import logging
import smtplib
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from clinic import DATE_FMT
from i18n import t

log = logging.getLogger(__name__)
ICS_UID_DOMAIN = "clinic.invalid"  # reserved domain, never resolves


def is_email(value):
    return bool(value) and "@" in value and "." in value.split("@")[-1]


def _escape_ics(text):
    return (
        str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    )


def build_ics(view, clinic_name, address, tz_name, duration_minutes=30):
    """Calendar event for an appointment, with times in UTC so every client shows them correctly."""
    local_start = datetime.strptime(view["starts_at"], DATE_FMT).replace(tzinfo=ZoneInfo(tz_name))
    start = local_start.astimezone(ZoneInfo("UTC"))
    end = start + timedelta(minutes=duration_minutes)
    fmt = "%Y%m%dT%H%M%SZ"
    stamp = datetime.now(ZoneInfo("UTC")).strftime(fmt)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{_escape_ics(clinic_name)}//Appointments//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:appointment-{view['id']}@{ICS_UID_DOMAIN}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{start.strftime(fmt)}",
        f"DTEND:{end.strftime(fmt)}",
        f"SUMMARY:{_escape_ics(clinic_name)}: {_escape_ics(view['doctor'])}",
        f"LOCATION:{_escape_ics(address)}",
        f"DESCRIPTION:{_escape_ics('Reference #' + str(view['id']))}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def send_email(config, to_address, subject, body, attachment=None):
    message = EmailMessage()
    message["From"] = config["MAIL_FROM"]
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    if attachment:
        filename, data, mime = attachment
        maintype, subtype = mime.split("/", 1)
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    if config["SMTP_HOST"]:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=20) as smtp:
            smtp.starttls()
            if config["SMTP_USER"]:
                smtp.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            smtp.send_message(message)
    else:
        outbox = Path(config["INSTANCE_DIR"]) / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        path = outbox / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.eml"
        path.write_bytes(message.as_bytes())
        log.info("No SMTP configured; email written to %s", path)
    return True


def send_confirmation(config, view):
    """Send the booking confirmation with a calendar file. Returns False if no email address."""
    if not is_email(view["contact"]):
        return False
    lang = view["lang"]
    subject = t("mail_confirm_subject", lang, clinic=config["CLINIC_NAME"])
    body = t(
        "mail_confirm_body", lang,
        doctor=view["doctor"], date=view["date"], time=view["time"], id=view["id"],
        address=config["CLINIC_ADDRESS"], clinic=config["CLINIC_NAME"],
    )
    ics = build_ics(view, config["CLINIC_NAME"], config["CLINIC_ADDRESS"], config["CLINIC_TZ"])
    return send_email(config, view["contact"], subject, body,
                      ("appointment.ics", ics.encode("utf-8"), "text/calendar"))


def send_reminders(config, clinic, now=None):
    """Email reminders for confirmed appointments starting within the next 24 hours.

    Each appointment is reminded once. Run this hourly (see README). Returns the number sent.
    """
    now = now or clinic.now()
    window_end = now + timedelta(hours=24)
    sent = 0
    for row in clinic.store.due_reminders(now.strftime(DATE_FMT), window_end.strftime(DATE_FMT)):
        view = clinic.view(row)
        if is_email(view["contact"]):
            lang = view["lang"]
            send_email(
                config,
                view["contact"],
                t("mail_reminder_subject", lang, clinic=config["CLINIC_NAME"]),
                t("mail_reminder_body", lang, doctor=view["doctor"], date=view["date"],
                  time=view["time"], id=view["id"], address=config["CLINIC_ADDRESS"],
                  clinic=config["CLINIC_NAME"]),
            )
            sent += 1
        clinic.mark_reminded(row["id"], now)  # also marks appointments without email, so they are not retried
    return sent

def notify_staff_new_request(config, store, appt_id):
    """Tell reception and the doctor that a request is waiting. The e-mail contains no patient details."""
    row = store.get_appointment(appt_id)
    if row is None:
        return
    link = f"{config['PUBLIC_BASE_URL'].rstrip('/')}/staff/login"
    body = (
        "A new appointment request is waiting for review.\n\n"
        f"Requested time: {row['starts_at']} (Europe/Berlin)\n\n"
        f"Sign in to the staff area to see the details: {link}\n\n"
        "This message contains no patient information."
    )
    for address in store.staff_emails_for(row["doctor_id"]):
        send_email(config, address, "New appointment request", body)
