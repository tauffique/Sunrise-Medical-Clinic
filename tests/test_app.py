import re
import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash

from app import create_app
from chatbot import detect_language
from clinic import parse_day
from notifier import ChangeBus
from rag import KnowledgeIndex

ROOT = Path(__file__).resolve().parent.parent
ENCRYPTION_KEY = Fernet.generate_key().decode()


def next_weekday(weekday=0):
    """Return the next date (ISO) that falls on the given weekday, at least two weeks away."""
    day = date.today() + timedelta(days=14)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day.isoformat()


class AppCase(unittest.TestCase):
    overrides = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = {
            "TESTING": True,
            "CLINIC_ENV": "development",
            "INSTANCE_DIR": self.tmp.name,
            "DATABASE": str(Path(self.tmp.name) / "test.db"),
            "SECRET_KEY": "test-secret-key-that-is-long-enough-for-tests",
            "CLINIC_ENCRYPTION_KEY": ENCRYPTION_KEY,
            "SMTP_HOST": "",
            "RATE_CHAT": (1000, 60),
            "RATE_BOOKING": (1000, 60),
            "RATE_LOGIN": (1000, 900),
        }
        base.update(self.overrides)
        self.app = create_app(base, llm=None)
        self.client = self.app.test_client()
        self.store = self.app.extensions["store"]
        self.clinic = self.app.extensions["clinic"]
        self.vault = self.app.extensions["vault"]

    def csrf(self):
        html = self.client.get("/").get_data(as_text=True)
        match = re.search(r'name="csrf-token" content="([^"]+)"', html)
        self.assertIsNotNone(match, "csrf meta tag missing from the home page")
        return match.group(1)

    def book(self, day=None, time="10:00", doctor="dr-meyer", contact="anna@example.com", consent=True):
        payload = {
            "doctor_id": doctor,
            "date": day or next_weekday(0),
            "time": time,
            "name": "Anna Example",
            "contact": contact,
            "reason": "Persistent cough for two weeks",
            "consent": consent,
            "intake": {"conditions": "Asthma", "medications": "", "allergies": "Penicillin", "insurance": ""},
        }
        return self.client.post("/api/appointments", json=payload, headers={"X-CSRF-Token": self.csrf()})


class RagTests(unittest.TestCase):
    def setUp(self):
        docs = json.loads((ROOT / "data" / "knowledge.json").read_text(encoding="utf-8"))
        self.index = KnowledgeIndex(docs)

    def test_symptom_question_finds_cardiology(self):
        hits = self.index.search("I have palpitations and a racing heartbeat")
        self.assertTrue(hits)
        top = hits[0]
        self.assertEqual(top["id"], "cardiology")

    def test_german_question_finds_german_keywords(self):
        hits = self.index.search("Ich habe Herzklopfen und Schwindel")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "cardiology")

    def test_unrelated_question_returns_nothing(self):
        self.assertEqual(self.index.search("zzqx blorp frimble"), [])


class ParseDayTests(unittest.TestCase):
    def test_iso_date_passes_through(self):
        self.assertEqual(str(parse_day("2031-03-04", date(2026, 11, 19))), "2031-03-04")

    def test_tomorrow_is_the_next_day(self):
        self.assertEqual(str(parse_day("tomorrow", date(2026, 11, 19))), "2026-11-20")

    def test_weekday_name_is_the_next_occurrence(self):
        # 2026-11-19 is a Thursday, so the next Tuesday is 2026-11-24.
        self.assertEqual(str(parse_day("tuesday", date(2026, 11, 19))), "2026-11-24")

    def test_garbage_is_rejected(self):
        self.assertIsNone(parse_day("someday maybe", date(2026, 11, 19)))


class LanguageTests(unittest.TestCase):
    def test_english_is_detected(self):
        self.assertEqual(detect_language("I have a headache and want an appointment"), "en")

    def test_german_is_detected(self):
        self.assertEqual(detect_language("Ich habe Kopfschmerzen und möchte einen Termin"), "de")


class ChangeBusTests(unittest.TestCase):
    def test_publish_increments_version_and_wakes_waiters(self):
        bus = ChangeBus()
        before = bus.version
        bus.publish()
        self.assertEqual(bus.version, before + 1)
        self.assertTrue(bus.wait_for_change(before, timeout=0.1))

    def test_wait_times_out_without_change(self):
        bus = ChangeBus()
        self.assertFalse(bus.wait_for_change(bus.version, timeout=0.05))


class BookingTests(AppCase):
    def test_booking_creates_appointment(self):
        response = self.book()
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertIn("message", response.get_json())

    def test_booking_without_consent_is_refused(self):
        response = self.book(consent=False)
        self.assertEqual(response.status_code, 400)

    def test_same_slot_cannot_be_booked_twice(self):
        day = next_weekday(0)
        self.assertEqual(self.book(day=day).status_code, 201)
        second = self.book(day=day, contact="someone.else@example.com")
        self.assertGreaterEqual(second.status_code, 400)

    def test_booking_is_rate_limited(self):
        self.app.extensions["limiter"]  # limiter exists
        for limit in ("RATE_BOOKING",):
            self.app.config[limit] = (2, 60)
        self.app.config["RATE_BOOKING"] = (2, 60)
        self.assertEqual(self.book(time="09:00").status_code, 201)
        self.assertEqual(self.book(time="09:30").status_code, 201)
        self.assertEqual(self.book(time="10:00").status_code, 429)

    def test_post_without_csrf_token_is_forbidden(self):
        payload = {"doctor_id": "dr-meyer", "date": next_weekday(0), "time": "11:00",
                   "name": "Anna Example", "contact": "anna@example.com", "consent": True}
        response = self.client.post("/api/appointments", json=payload)
        self.assertEqual(response.status_code, 403)

    def test_security_headers_are_set(self):
        response = self.client.get("/")
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")


class EncryptionTests(AppCase):
    def test_patient_name_is_not_stored_in_plain_text(self):
        self.assertEqual(self.book().status_code, 201)
        raw = sqlite3.connect(self.app.config["DATABASE"])
        try:
            rows = raw.execute("SELECT * FROM appointments").fetchall()
            flat = repr(rows)
        finally:
            raw.close()
        self.assertTrue(rows)
        self.assertNotIn("Anna Example", flat)
        self.assertNotIn("anna@example.com", flat)
        self.assertNotIn("Asthma", flat)

    def test_contact_lookup_hash_is_stable_and_normalised(self):
        a = self.vault.lookup_hash("Anna@Example.com")
        b = self.vault.lookup_hash("anna@example.com")
        self.assertEqual(a, b)


class ErasureTests(AppCase):
    def test_delete_contact_data_removes_appointments(self):
        self.assertEqual(self.book(contact="erase@example.com").status_code, 201)
        digest = self.vault.lookup_hash("erase@example.com")
        self.clinic.delete_contact_data(digest)
        remaining = self.store.list_appointments("dr-meyer", next_weekday(0))
        self.assertEqual(remaining, [])


class ChatTests(AppCase):
    SESSION = "session-emergency-0001"

    def chat(self, message, session_id, lang="en"):
        return self.client.post(
            "/api/chat",
            json={"session_id": session_id, "message": message, "lang": lang},
            headers={"X-CSRF-Token": self.csrf()},
        )

    def test_emergency_is_flagged_with_112(self):
        response = self.chat("I think someone is having a stroke, they collapsed", self.SESSION)
        self.assertEqual(response.status_code, 200)
        self.assertIn("112", response.get_json()["reply"])

    def test_german_message_gets_german_reply(self):
        response = self.chat("Wo ist die Praxis und wann haben Sie geöffnet?", "session-de-00001", lang="en")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hauptstraße", response.get_json()["reply"])

    def test_history_survives_a_new_request(self):
        sid = "session-history-0001"
        self.chat("What are your opening hours?", sid)
        response = self.client.get(f"/api/chat/history?session_id={sid}")
        messages = response.get_json()["messages"]
        self.assertGreaterEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")

    def test_invalid_session_id_is_rejected(self):
        response = self.chat("Hello", "short")
        self.assertEqual(response.status_code, 400)


class StreamTests(AppCase):
    def test_stream_is_event_stream(self):
        response = self.client.get("/api/stream", buffered=False)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.mimetype.startswith("text/event-stream"))
        response.close()


class StaffTests(AppCase):
    def setUp(self):
        super().setUp()
        self.store.create_user(
            email="reception@clinic.test",
            password_hash=generate_password_hash("correct horse battery"),
            role="reception",
            doctor_id=None,
        )
        self.store.create_user(
            email="meyer@clinic.test",
            password_hash=generate_password_hash("correct horse battery"),
            role="doctor",
            doctor_id="dr-meyer",
        )

    def login(self, email):
        return self.client.post(
            "/staff/login",
            data={"email": email, "password": "correct horse battery", "csrf_token": self.csrf()},
        )

    def test_wrong_password_is_refused(self):
        response = self.client.post(
            "/staff/login",
            data={"email": "reception@clinic.test", "password": "wrong", "csrf_token": self.csrf()},
        )
        self.assertNotEqual(response.status_code, 302)

    def test_dashboard_requires_login(self):
        response = self.client.get("/staff/")
        self.assertIn(response.status_code, (302, 401))

    def test_reception_sees_name_but_not_reason(self):
        self.book(day=next_weekday(0))
        self.login("reception@clinic.test")
        html = self.client.get(f"/staff/?date={next_weekday(0)}").get_data(as_text=True)
        self.assertIn("Anna Example", html)
        self.assertNotIn("Persistent cough", html)
        self.assertNotIn("Asthma", html)

    def test_doctor_sees_reason_and_intake(self):
        self.book(day=next_weekday(0))
        self.login("meyer@clinic.test")
        html = self.client.get(f"/staff/?date={next_weekday(0)}").get_data(as_text=True)
        self.assertIn("Persistent cough", html)
        self.assertIn("Asthma", html)

    def test_cancelling_frees_the_slot(self):
        day = next_weekday(0)
        self.book(day=day, time="14:00")
        self.login("reception@clinic.test")
        appt = self.store.list_appointments("dr-meyer", day)[0]
        self.client.post(
            f"/staff/appointments/{appt['id']}/status",
            data={"status": "cancelled", "csrf_token": self.csrf()},
        )
        self.assertEqual(self.book(day=day, time="14:00", contact="new@example.com").status_code, 201)


if __name__ == "__main__":
    unittest.main()