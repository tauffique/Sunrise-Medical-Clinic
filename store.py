"""SQLite persistence.

Personal and health fields are passed in already encrypted (see crypto.py), so the
database file contains no readable patient data.
"""
import sqlite3


class SlotTaken(Exception):
    """Another active appointment already holds this doctor/time slot."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id TEXT NOT NULL,
    starts_at TEXT NOT NULL,                        -- 'YYYY-MM-DD HH:MM', clinic local time
    status TEXT NOT NULL DEFAULT 'requested',       -- requested | confirmed | done | cancelled
    source TEXT NOT NULL DEFAULT 'web',             -- web | chatbot
    lang TEXT NOT NULL DEFAULT 'en',
    contact_hash TEXT NOT NULL DEFAULT '',          -- keyed hash, for matching a patient
    name_enc TEXT NOT NULL,
    contact_enc TEXT NOT NULL,
    reason_enc TEXT NOT NULL DEFAULT '',
    intake_enc TEXT NOT NULL DEFAULT '',            -- encrypted JSON: conditions, medications, ...
    consent_at TEXT NOT NULL,
    reminder_sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_booking
    ON appointments (doctor_id, starts_at) WHERE status != 'cancelled';

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('reception', 'doctor')),
    doctor_id TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL DEFAULT (datetime('now')),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    appointment_id INTEGER
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    sid TEXT PRIMARY KEY,
    state_enc TEXT NOT NULL,                        -- encrypted conversation state
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Store:
    def __init__(self, path):
        self.path = str(path)
        conn = self._connect()
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _query(self, sql, params=()):
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def _write(self, sql, params=()):
        """Run one write statement. Returns (lastrowid, rowcount); integrity errors propagate."""
        conn = self._connect()
        try:
            with conn:
                cur = conn.execute(sql, params)
                return cur.lastrowid, cur.rowcount
        finally:
            conn.close()

    # ----- appointments -----

    def booked_times(self, doctor_id, day_iso):
        rows = self._query(
            "SELECT starts_at FROM appointments "
            "WHERE doctor_id = ? AND starts_at LIKE ? AND status != 'cancelled'",
            (doctor_id, day_iso + "%"),
        )
        return {row["starts_at"][11:16] for row in rows}

    def create_appointment(self, **fields):
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        try:
            appt_id, _ = self._write(
                f"INSERT INTO appointments ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
        except sqlite3.IntegrityError as exc:
            raise SlotTaken(fields.get("starts_at", "")) from exc
        return appt_id

    def get_appointment(self, appt_id):
        rows = self._query("SELECT * FROM appointments WHERE id = ?", (appt_id,))
        return rows[0] if rows else None

    def list_appointments(self, doctor_id=None, day_iso=None):
        sql = "SELECT * FROM appointments WHERE 1 = 1"
        params = []
        if doctor_id:
            sql += " AND doctor_id = ?"
            params.append(doctor_id)
        if day_iso:
            sql += " AND starts_at LIKE ?"
            params.append(day_iso + "%")
        sql += " ORDER BY starts_at, id"
        return self._query(sql, params)

    def update_appointment(self, appt_id, **fields):
        assignments = ", ".join(f"{name} = ?" for name in fields)
        try:
            self._write(
                f"UPDATE appointments SET {assignments} WHERE id = ?",
                (*fields.values(), appt_id),
            )
        except sqlite3.IntegrityError as exc:
            raise SlotTaken(fields.get("starts_at", str(appt_id))) from exc

    def find_upcoming_by_contact(self, contact_hash, after_iso):
        return self._query(
            "SELECT * FROM appointments WHERE contact_hash = ? "
            "AND status IN ('requested', 'confirmed') AND starts_at > ? ORDER BY starts_at",
            (contact_hash, after_iso),
        )

    def delete_appointments_for_contact(self, contact_hash):
        _, count = self._write("DELETE FROM appointments WHERE contact_hash = ?", (contact_hash,))
        return count

    def due_reminders(self, start_iso, end_iso):
        return self._query(
            "SELECT * FROM appointments WHERE status = 'confirmed' AND reminder_sent_at IS NULL "
            "AND starts_at >= ? AND starts_at <= ? ORDER BY starts_at",
            (start_iso, end_iso),
        )

    def purge_appointments_before(self, cutoff_iso):
        _, count = self._write("DELETE FROM appointments WHERE starts_at < ?", (cutoff_iso,))
        return count

    # ----- users -----

    def create_user(self, email, password_hash, role, doctor_id=None):
        self._write(
            "INSERT INTO users (email, password_hash, role, doctor_id) VALUES (?, ?, ?, ?)",
            (email, password_hash, role, doctor_id),
        )

    def get_user_by_email(self, email):
        rows = self._query("SELECT * FROM users WHERE email = ?", (email,))
        return rows[0] if rows else None

    def get_user(self, user_id):
        rows = self._query("SELECT * FROM users WHERE id = ?", (user_id,))
        return rows[0] if rows else None

    def staff_emails_for(self, doctor_id):
        rows = self._query(
            "SELECT email FROM users WHERE active = 1 AND "
            "(role = 'reception' OR (role = 'doctor' AND doctor_id = ?))",
            (doctor_id,),
        )
        return [row["email"] for row in rows]

    # ----- audit log -----

    def audit(self, actor, action, appointment_id=None):
        self._write(
            "INSERT INTO audit_log (actor, action, appointment_id) VALUES (?, ?, ?)",
            (actor, action, appointment_id),
        )

    def recent_audit(self, limit=100):
        return self._query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))

    # ----- chat sessions -----

    def save_session(self, sid, state_enc):
        self._write(
            "INSERT INTO chat_sessions (sid, state_enc, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(sid) DO UPDATE SET state_enc = excluded.state_enc, updated_at = excluded.updated_at",
            (sid, state_enc),
        )

    def load_session(self, sid):
        rows = self._query("SELECT state_enc FROM chat_sessions WHERE sid = ?", (sid,))
        return rows[0]["state_enc"] if rows else None

    def purge_sessions(self, hours):
        _, count = self._write(
            "DELETE FROM chat_sessions WHERE updated_at < datetime('now', ?)",
            (f"-{int(hours)} hours",),
        )
        return count