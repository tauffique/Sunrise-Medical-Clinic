import logging
"""Booking rules and appointment lifecycle.

The website, the chatbot and the staff area all go through this class, so the same
rules apply everywhere: working days, free slots, consent, the 24-hour change notice,
encryption of personal data and the audit trail.
"""
import hmac
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from i18n import DAYS
from store import SlotTaken

DATE_FMT = "%Y-%m-%d %H:%M"
ALL_SLOTS = [f"{(540 + 30 * i) // 60:02d}:{(540 + 30 * i) % 60:02d}" for i in range(16)]  # 09:00 .. 16:30
STATUSES = ("requested", "confirmed", "done", "cancelled")
NOTICE_HOURS = 24
INTAKE_FIELDS = ("conditions", "medications", "allergies", "insurance")

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
WEEKDAYS = {
    "monday": 0, "montag": 0,
    "tuesday": 1, "dienstag": 1,
    "wednesday": 2, "mittwoch": 2,
    "thursday": 3, "donnerstag": 3,
    "friday": 4, "freitag": 4,
    "saturday": 5, "samstag": 5,
    "sunday": 6, "sonntag": 6,
}


class BookingError(Exception):
    """A patient-facing reason why an action cannot be completed.

    `key` is a message key from i18n.py; `params` are filled in when the text is rendered.
    """

    def __init__(self, key, **params):
        super().__init__(key)
        self.key = key
        self.params = params


_MONTHS = {
    "jan": 1, "january": 1, "januar": 1, "feb": 2, "february": 2, "februar": 2,
    "mar": 3, "march": 3, "märz": 3, "maerz": 3, "apr": 4, "april": 4,
    "may": 5, "mai": 5, "jun": 6, "june": 6, "juni": 6, "jul": 7, "july": 7, "juli": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "oktober": 10, "okt": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12, "dez": 12, "dezember": 12,
}


def _month_date(lowered, today):
    """Reads '22 nov', '22. november', 'november 22' and 'nov 22nd'. Past dates roll to next year."""
    patterns = (
        (r"\b(\d{1,2})(?:st|nd|rd|th|\.)?\s+(?:of\s+)?([a-zäöüß]+)\b", True),
        (r"\b([a-zäöüß]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b", False),
    )
    for pattern, day_first in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        day, name = (match.group(1), match.group(2)) if day_first else (match.group(2), match.group(1))
        month = _MONTHS.get(name)
        if month is None:
            continue
        try:
            candidate = date(today.year, month, int(day))
            if candidate < today:
                candidate = date(today.year + 1, month, int(day))
        except ValueError:
            return None
        return candidate
    return None


def parse_day(text, today=None):
    """Accept 'YYYY-MM-DD', 'today'/'heute', 'tomorrow'/'morgen' or a weekday name.

    A weekday means the next occurrence after today ('tuesday' on a Tuesday means next week).
    """
    today = today or date.today()
    text = text or ""
    match = _DATE_RE.search(text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    lowered = text.lower()
    month_day = _month_date(lowered, today)
    if month_day:
        return month_day
    if re.search(r"\btomorrow\b|\bmorgen\b", lowered):
        return today + timedelta(days=1)
    if re.search(r"\btoday\b|\bheute\b", lowered):
        return today
    for word in re.findall(r"[a-zäöüß]+", lowered):
        if word in WEEKDAYS:
            delta = (WEEKDAYS[word] - today.weekday()) % 7 or 7
            return today + timedelta(days=delta)
    return None


def parse_time(text):
    """Return 'HH:MM' found in the text, or None."""
    match = _TIME_RE.search(text or "")
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _clean_intake(intake):
    if not isinstance(intake, dict):
        return {}
    cleaned = {}
    for key in INTAKE_FIELDS:
        value = str(intake.get(key, "") or "").strip()[:500]
        if value:
            cleaned[key] = value
    return cleaned


class Clinic:
    def __init__(self, doctors, store, vault, bus, tz_name="Europe/Berlin", retention_days=90):
        self.doctors = doctors
        self.by_id = {d["id"]: d for d in doctors}
        self.store = store
        self.vault = vault
        self.bus = bus
        self.tz = ZoneInfo(tz_name)
        self.retention_days = retention_days
        self.on_new_request = None  # the app sets this to send staff alerts

    # ----- time and lookup helpers -----

    def now(self):
        """Current clinic-local time as a naive datetime."""
        return datetime.now(self.tz).replace(tzinfo=None)

    def doctor_for_specialty(self, specialty):
        return next((d for d in self.doctors if d["specialty"] == specialty), None)

    def find_doctor(self, text):
        """Match a doctor by last name or specialty mentioned in free text."""
        lowered = (text or "").lower()
        for doctor in self.doctors:
            last_name = doctor["name"].split()[-1].lower()
            if last_name in lowered or doctor["specialty"].lower() in lowered:
                return doctor
        return None

    def days_text(self, doctor, lang="en"):
        return ", ".join(DAYS[lang]["abbr"][i] for i in doctor["working_days"])

    # ----- availability -----

    def validate_day(self, doctor_id, day, now=None):
        now = now or self.now()
        doctor = self.by_id.get(doctor_id)
        if doctor is None:
            raise BookingError("err_unknown_doctor")
        if day < now.date():
            raise BookingError("err_past_date")
        if day.weekday() not in doctor["working_days"]:
            raise BookingError(
                "err_not_working",
                doctor=doctor["name"],
                weekday=day.weekday(),
                working=doctor["working_days"],
            )
        return doctor

    def slots(self, doctor_id, day, now=None):
        """Free 30-minute slots for a doctor on a given day."""
        now = now or self.now()
        doctor = self.by_id.get(doctor_id)
        if doctor is None or day < now.date() or day.weekday() not in doctor["working_days"]:
            return []
        booked = self.store.booked_times(doctor_id, day.isoformat())
        free = []
        for slot in ALL_SLOTS:
            if slot in booked:
                continue
            if day == now.date():
                hour, minute = int(slot[:2]), int(slot[3:])
                if datetime(day.year, day.month, day.day, hour, minute) <= now:
                    continue
            free.append(slot)
        return free

    def availability(self, doctor_id, year, month, now=None):
        """Map of ISO date -> free slot count, for the working days of a month."""
        now = now or self.now()
        doctor = self.by_id.get(doctor_id)
        if doctor is None:
            return {}
        day = date(year, month, 1)
        next_month = date(year + (month == 12), month % 12 + 1, 1)
        days = {}
        while day < next_month:
            if day.weekday() in doctor["working_days"] and day >= now.date():
                days[day.isoformat()] = len(self.slots(doctor_id, day, now=now))
            day += timedelta(days=1)
        return days

    # ----- creating and changing appointments -----

    def book(self, doctor_id, day, time_str, name, contact, reason="", intake=None,
             consent=False, source="web", lang="en", now=None):
        now = now or self.now()
        if consent is not True:
            raise BookingError("err_consent")
        name = (name or "").strip()
        contact = (contact or "").strip()
        if len(name) < 2:
            raise BookingError("err_name")
        if not contact:
            raise BookingError("err_contact")
        self.validate_day(doctor_id, day, now)
        if time_str not in self.slots(doctor_id, day, now):
            raise BookingError("err_slot_unavailable")

        intake = _clean_intake(intake)
        try:
            appt_id = self.store.create_appointment(
                doctor_id=doctor_id,
                starts_at=f"{day.isoformat()} {time_str}",
                status="requested",
                source=source,
                lang=lang if lang in ("en", "de") else "en",
                contact_hash=self.vault.lookup_hash(contact),
                name_enc=self.vault.seal(name[:100]),
                contact_enc=self.vault.seal(contact[:200]),
                reason_enc=self.vault.seal((reason or "").strip()[:500]),
                intake_enc=self.vault.seal_json(intake) if intake else "",
                consent_at=now.isoformat(timespec="seconds"),
            )
        except SlotTaken as exc:
            raise BookingError("err_slot_taken") from exc
        self.bus.publish()
        if self.on_new_request is not None:
            try:
                self.on_new_request(appt_id)
            except Exception:  # an e-mail problem must not block the booking
                logging.getLogger(__name__).exception("New-request alert failed for %s", appt_id)
        return appt_id

    def reschedule(self, appt_id, day, time_str, actor, now=None):
        now = now or self.now()
        row = self._require(appt_id)
        self.check_change_allowed(row["starts_at"], now)
        self.validate_day(row["doctor_id"], day, now)
        if time_str not in self.slots(row["doctor_id"], day, now):
            raise BookingError("err_slot_unavailable")
        try:
            self.store.update_appointment(appt_id, starts_at=f"{day.isoformat()} {time_str}")
        except SlotTaken as exc:
            raise BookingError("err_slot_taken") from exc
        self.store.audit(actor, "reschedule", appt_id)
        self.bus.publish()

    def set_status(self, appt_id, status, actor):
        if status not in STATUSES:
            raise ValueError(f"unknown status {status}")
        self._require(appt_id)
        self.store.update_appointment(appt_id, status=status)
        self.store.audit(actor, f"status:{status}", appt_id)
        self.bus.publish()

    def mark_reminded(self, appt_id, now=None):
        now = now or self.now()
        self.store.update_appointment(appt_id, reminder_sent_at=now.isoformat(timespec="seconds"))

    def check_change_allowed(self, starts_at, now=None):
        now = now or self.now()
        starts = datetime.strptime(starts_at, DATE_FMT)
        if starts - now < timedelta(hours=NOTICE_HOURS):
            raise BookingError("err_too_late")

    # ----- patient self-service -----

    def find_for_contact(self, appt_id, contact, now=None):
        """The appointment if `contact` matches it and it is still upcoming, otherwise None."""
        now = now or self.now()
        row = self.store.get_appointment(appt_id)
        if row is None or row["status"] not in ("requested", "confirmed"):
            return None
        if row["starts_at"] <= now.strftime(DATE_FMT):
            return None
        if not hmac.compare_digest(row["contact_hash"], self.vault.lookup_hash(contact)):
            return None
        return row

    def cancel_by_patient(self, appt_id, now=None):
        row = self._require(appt_id)
        self.check_change_allowed(row["starts_at"], now)
        self.set_status(appt_id, "cancelled", actor="patient")

    def delete_contact_data(self, contact_hash):
        """Erase every appointment held for this contact (right to erasure)."""
        count = self.store.delete_appointments_for_contact(contact_hash)
        self.store.audit("patient", f"erasure:{count}")
        self.bus.publish()
        return count

    # ----- views and retention -----

    def view(self, row):
        """Decrypted, presentation-ready copy of an appointment row."""
        doctor = self.by_id.get(row["doctor_id"], {})
        starts = row["starts_at"]
        return {
            "id": row["id"],
            "doctor_id": row["doctor_id"],
            "doctor": doctor.get("name", row["doctor_id"]),
            "specialty": doctor.get("specialty", ""),
            "date": starts[:10],
            "time": starts[11:16],
            "starts_at": starts,
            "status": row["status"],
            "source": row["source"],
            "lang": row["lang"],
            "contact_hash": row["contact_hash"],
            "consent_at": row["consent_at"],
            "created_at": row["created_at"],
            "reminder_sent_at": row["reminder_sent_at"],
            "name": self.vault.open(row["name_enc"]),
            "contact": self.vault.open(row["contact_enc"]),
            "reason": self.vault.open(row["reason_enc"]),
            "intake": self.vault.open_json(row["intake_enc"]) or {},
        }

    def list_views(self, doctor_id=None, day_iso=None):
        return [self.view(row) for row in self.store.list_appointments(doctor_id, day_iso)]

    def purge_expired(self, now=None):
        """Delete appointments older than the retention period (by appointment date)."""
        now = now or self.now()
        cutoff = (now - timedelta(days=self.retention_days)).strftime(DATE_FMT)
        count = self.store.purge_appointments_before(cutoff)
        if count:
            self.store.audit("system", f"retention-purge:{count}")
            self.bus.publish()
        return count

    def _require(self, appt_id):
        row = self.store.get_appointment(appt_id)
        if row is None:
            raise BookingError("err_not_found")
        return row