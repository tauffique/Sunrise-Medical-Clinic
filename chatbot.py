"""Chatbot: emergency triage, RAG answers, and step-by-step flows.

Flows: booking (doctor, date, time, consent, details, optional intake questions, confirm),
self-service changes (verify reference + contact, then cancel, reschedule or delete data),
and an emergency short-cut. Conversation state is encrypted and stored per session, so a
patient can continue after a server restart.
"""
import re
from datetime import timedelta

from clinic import BookingError, parse_day, parse_time
from i18n import LANGS, render_error, specialty_name, t

MAX_VERIFY_ATTEMPTS = 3
HISTORY_LIMIT = 60

EMERGENCY_RE = re.compile(
    r"chest pain|can'?t breathe|cannot breathe|trouble breathing|difficulty breathing|stroke|"
    r"unconscious|seizure|heavy bleeding|suicid|kill myself|want to die|overdose|"
    r"brustschmerz|atemnot|bewusstlos|schlaganfall|suizid",
    re.I,
)
BOOK_RE = re.compile(
    r"\b(book|booking|appointments?|schedule|reserve|slot|termin|buchen|sprechstunde)\b", re.I
)
MANAGE_RE = re.compile(
    r"\b(cancel|reschedule|absagen|stornieren|verschieben)\b"
    r"|\b(delete|erase|löschen)\b.*\b(data|daten)\b"
    r"|\bmy (appointment|booking)\b",
    re.I,
)
ABORT_RE = re.compile(r"^\s*(cancel|stop|start over|reset|abbrechen)\b", re.I)
MANAGE_ABORT_RE = re.compile(r"^\s*(stop|start over|reset|abbrechen)\b", re.I)
YES_RE = re.compile(r"^\s*(y|yes|yeah|yep|sure|ok|okay|confirm|please|ja|j|klar|gerne)\b", re.I)
GREET_RE = re.compile(r"^\s*(hi|hello|hey|hallo|servus|guten (morgen|tag|abend))\b[\s!.?]*$", re.I)
CLOSE_RE = re.compile(
    r"^\s*(no|nope|nein|no thanks|no thank you|nein danke|that'?s all|that'?s it|bye|goodbye|tschüss|ciao|thanks|thank you|danke|vielen dank)\b[\s!.?]*$",
    re.I,
)
SKIP_RE = re.compile(r"^\s*(skip|none|-|überspringen|ueberspringen|keine|keiner)\s*$", re.I)
CONTACT_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+|\+?\d[\d\s()/-]{6,}\d")
CANCEL_WORD_RE = re.compile(r"\b(cancel|absagen|stornieren)\b", re.I)
RESCHEDULE_WORD_RE = re.compile(r"\b(reschedule|verschieben)\b", re.I)
DELETE_WORD_RE = re.compile(r"\b(delete|erase|löschen|data|daten)\b", re.I)
EN_HINT_RE = re.compile(
    r"\b(the|and|my|want|need|book|appointment|please|what|hours|doctor|pain|have|is|are|to|"
    r"cancel|reschedule|when|how|i)\b",
    re.I,
)
DE_HINT_RE = re.compile(
    r"\b(ich|nicht|habe|möchte|moechte|termin|bitte|kopf|schmerz|schmerzen|fieber|herz|hallo|guten|"
    r"nein|ja|abbrechen|dienstag|montag|mittwoch|donnerstag|freitag|samstag|sonntag|morgen|heute|"
    r"arzt|praxis|mein|meine|wann|wie|verschieben|absagen|löschen|daten)\b",
    re.I,
)
INTAKE_STEPS = [
    ("conditions", "intake_medications"),
    ("medications", "intake_allergies"),
    ("allergies", "intake_insurance"),
    ("insurance", None),
]


def detect_language(message):
    """'de' or 'en' when the message clearly is one of them, otherwise None."""
    german = len(DE_HINT_RE.findall(message))
    english = len(EN_HINT_RE.findall(message))
    if german and not english:
        return "de"
    if english and not german:
        return "en"
    return None


def _new_state(lang):
    return {
        "lang": lang if lang in LANGS else "en",
        "flow": None,
        "data": {},
        "suggested": None,
        "concern": "",
        "attempts": 0,
        "history": [],
    }


class ChatBot:
    def __init__(self, clinic, index, store, vault, llm=None, privacy_url="/privacy"):
        self.clinic = clinic
        self.index = index
        self.store = store
        self.vault = vault
        self.llm = llm
        self.privacy_url = privacy_url

    # ----- entry point and persistence -----

    def reply(self, session_id, message, lang=None):
        state = self._load(session_id) or _new_state(lang)  # page language only seeds a new session
        message = (message or "").strip()[:1000]
        detected = detect_language(message)
        if detected:
            state["lang"] = detected
        state.setdefault("history", [])
        if message:
            state["history"].append({"role": "user", "text": message})
        result = self._dispatch(state, message)
        state["history"].append({"role": "bot", "text": result["reply"]})
        state["history"] = state["history"][-HISTORY_LIMIT:]
        self.store.save_session(session_id, self.vault.seal_json(state))
        return result

    def history(self, session_id):
        """Saved transcript for a session, so a patient can continue after a page reload or restart."""
        state = self._load(session_id)
        return {"lang": state["lang"], "messages": state.get("history", [])} if state else None

    def _load(self, session_id):
        token = self.store.load_session(session_id)
        return self.vault.open_json(token) if token else None

    def _dispatch(self, st, message):
        lang = st["lang"]
        if not message:
            return self._out(st, t("bot_empty", lang))
        if EMERGENCY_RE.search(message):
            return self._out(st, t("bot_emergency", lang))

        if st["flow"]:
            abort = MANAGE_ABORT_RE if st["flow"].startswith("manage") else ABORT_RE
            if abort.match(message):
                self._reset(st)
                return self._out(st, t("bot_cancelled", lang))
            return self._out(st, self._step(st, message))

        if st["suggested"] and YES_RE.match(message):
            return self._out(st, self._start_booking(st, message))
        if st["suggested"] and NO_RE.match(message):
            st["suggested"] = None
            return self._out(st, t("bot_no_suggestion", lang))
        if CLOSE_RE.match(message):
            return self._out(st, t("bot_closing", lang))
        if GREET_RE.match(message):
            return self._out(st, self._greeting(st))
        if MANAGE_RE.search(message):
            return self._out(st, self._start_manage(st))
        if BOOK_RE.search(message):
            return self._out(st, self._start_booking(st, message))
        return self._out(st, self._answer(st, message))

    # ----- retrieval-augmented answers -----
    def _greeting(self, st):
        hour = self.clinic.now().hour
        if hour < 12:
            key = "bot_greet_morning"
        elif hour < 18:
            key = "bot_greet_afternoon"
        else:
            key = "bot_greet_evening"
        return t(key, st["lang"]) + " " + t("bot_how_help", st["lang"])
    def _answer(self, st, message):
        lang = st["lang"]
        hits = self.index.search(message, k=3)
        if not hits:
            return t("bot_fallback", lang)

        top = hits[0]
        if top["type"] == "specialty":
            explanation = self._explain(message, hits, lang) or self._text(top, lang)
            st["concern"] = message[:300]
            doctor = self.clinic.doctor_for_specialty(top["specialty"])
            if doctor is None:
                return f"{explanation}\n\n{t('bot_disclaimer', lang)}"
            st["suggested"] = doctor["id"]
            suggestion = t("bot_suggestion", lang, doctor=doctor["name"],
                           specialty=specialty_name(doctor["specialty"], lang))
            return f"{explanation}\n\n{suggestion}\n\n{t('bot_disclaimer', lang)}"

        return self._explain(message, hits, lang) or self._text(top, lang)

    def _explain(self, message, hits, lang):
        if self.llm is None:
            return None
        try:
            return self.llm.answer(message, hits, lang) or None
        except Exception:  # network or API problem: fall back to the retrieved text
            return None

    @staticmethod
    def _text(doc, lang):
        return doc.get("text_de") if lang == "de" and doc.get("text_de") else doc["text"]

    # ----- booking flow -----

    def _start_booking(self, st, message):
        lang = st["lang"]
        if st["suggested"] and YES_RE.match(message):
            doctor = self.clinic.by_id[st["suggested"]]
        else:
            doctor = self.clinic.find_doctor(message)
        st["suggested"] = None
        self._reset(st)
        if doctor is None:
            st["flow"] = "doctor"
            return f"{t('bot_which_doctor', lang)}\n{self._doctor_list(lang)}"
        st["data"]["doctor_id"] = doctor["id"]
        st["flow"] = "date"
        return self._ask_date(st, doctor)

    def _step_doctor(self, st, message):
        lang = st["lang"]
        doctor = self.clinic.find_doctor(message)
        if doctor is None:
            return f"{t('bot_doctor_not_matched', lang)}\n{self._doctor_list(lang)}"
        st["data"]["doctor_id"] = doctor["id"]
        st["flow"] = "date"
        return self._ask_date(st, doctor)

    def _step_date(self, st, message):
        lang = st["lang"]
        doctor_id = st["data"]["doctor_id"]
        day = parse_day(message)
        if day is None:
            return t("bot_date_invalid", lang)
        try:
            self.clinic.validate_day(doctor_id, day)
        except BookingError as exc:
            return f"{render_error(exc, lang)} {t('bot_choose_other_date', lang)}"
        free = self.clinic.slots(doctor_id, day)
        if not free:
            return t("bot_no_slots", lang)
        st["data"]["date"] = day.isoformat()
        st["flow"] = "time"
        return t("bot_time_prompt", lang, date=day.isoformat(), times=", ".join(free))

    def _step_time(self, st, message):
        lang = st["lang"]
        data = st["data"]
        day = parse_day(data["date"])
        free = self.clinic.slots(data["doctor_id"], day)  # re-checked on every step, so it is live
        time_str = parse_time(message)
        if time_str is None:
            return t("bot_time_prompt", lang, date=data["date"], times=", ".join(free))
        if time_str not in free:
            if not free:
                data.pop("date", None)
                st["flow"] = "date"
                return t("bot_day_full", lang)
            return t("bot_time_taken", lang, times=", ".join(free))

        data["time"] = time_str
        doctor = self.clinic.by_id[data["doctor_id"]]
        if data.get("reschedule_id"):
            st["flow"] = "confirm_reschedule"
            return t("bot_confirm_reschedule", lang, doctor=doctor["name"],
                     date=data["date"], time=time_str)
        st["flow"] = "consent"
        return t("bot_consent", lang, days=self.clinic.retention_days, url=self.privacy_url)

    def _step_consent(self, st, message):
        lang = st["lang"]
        if not YES_RE.match(message):
            return t("bot_consent_again", lang)
        st["data"]["consent"] = True
        st["flow"] = "name"
        return t("bot_ask_name", lang)

    def _step_name(self, st, message):
        lang = st["lang"]
        name = message.strip()
        if len(name) < 2:
            return t("bot_name_short", lang)
        st["data"]["name"] = name[:100]
        st["flow"] = "contact"
        return t("bot_ask_contact", lang)

    def _step_contact(self, st, message):
        lang = st["lang"]
        if not CONTACT_RE.search(message):
            return t("bot_contact_invalid", lang)
        st["data"]["contact"] = message.strip()[:200]
        st["flow"] = "reason"
        if st["concern"]:
            return t("bot_reason_keep", lang, reason=st["concern"][:120])
        return t("bot_reason_ask", lang)

    def _step_reason(self, st, message):
        lang = st["lang"]
        if SKIP_RE.match(message):
            st["data"]["reason"] = st["concern"]
        else:
            st["data"]["reason"] = message[:500]
        st["flow"] = "intake_offer"
        return t("bot_intake_offer", lang)

    def _step_intake_offer(self, st, message):
        if YES_RE.match(message):
            st["flow"] = "intake_conditions"
            return t("bot_intake_conditions", st["lang"])
        st["flow"] = "confirm"
        return self._confirm_text(st)

    def _make_intake_step(self, key, next_flow):
        def step(st, message):
            if not SKIP_RE.match(message):
                st["data"].setdefault("intake", {})[key] = message.strip()[:500]
            if next_flow:
                st["flow"] = next_flow
                return t(f"bot_{next_flow}", st["lang"])
            st["flow"] = "confirm"
            return self._confirm_text(st)
        return step

    def _step_confirm(self, st, message):
        lang = st["lang"]
        if YES_RE.match(message):
            return self._finish_booking(st)
        if NO_RE.match(message):
            self._reset(st)
            return t("bot_nothing_booked", lang)
        return t("bot_confirm_again", lang)

    def _finish_booking(self, st):
        lang = st["lang"]
        data = st["data"]
        doctor = self.clinic.by_id[data["doctor_id"]]
        try:
            appt_id = self.clinic.book(
                data["doctor_id"], parse_day(data["date"]), data["time"],
                data["name"], data["contact"], data.get("reason", ""),
                intake=data.get("intake"), consent=data.get("consent") is True,
                source="chatbot", lang=lang,
            )
        except BookingError as exc:
            self._reset(st)
            return t("bot_finish_fail", lang, error=render_error(exc, lang))
        self._reset(st)
        st["concern"] = ""
        return t("bot_done", lang, id=appt_id, doctor=doctor["name"], contact=data["contact"])

    def _confirm_text(self, st):
        data = st["data"]
        doctor = self.clinic.by_id[data["doctor_id"]]
        return t(
            "bot_confirm", st["lang"],
            doctor=doctor["name"], date=data["date"], time=data["time"],
            name=data["name"], contact=data["contact"], reason=data.get("reason") or "-",
        )

    # ----- changing or deleting an appointment -----

    def _start_manage(self, st):
        self._reset(st)
        st["flow"] = "manage_ref"
        return t("bot_manage_intro", st["lang"])

    def _step_manage_ref(self, st, message):
        lang = st["lang"]
        match = re.search(r"\d+", message)
        if not match:
            return t("bot_manage_ref_invalid", lang)
        st["data"] = {"ref": int(match.group())}
        st["flow"] = "manage_contact"
        return t("bot_manage_ask_contact", lang)

    def _step_manage_contact(self, st, message):
        lang = st["lang"]
        row = self.clinic.find_for_contact(st["data"]["ref"], message)
        if row is None:
            st["attempts"] += 1
            st["data"] = {}
            if st["attempts"] >= MAX_VERIFY_ATTEMPTS:
                st["attempts"] = 0
                st["flow"] = None
                return t("bot_manage_locked", lang)
            st["flow"] = "manage_ref"
            return t("bot_manage_not_found", lang)

        st["attempts"] = 0
        view = self.clinic.view(row)
        st["data"] = {
            "ref": view["id"],
            "doctor_id": view["doctor_id"],
            "contact_hash": view["contact_hash"],
            "date": view["date"],
            "time": view["time"],
        }
        st["flow"] = "manage_action"
        return t("bot_manage_found", lang, id=view["id"], doctor=view["doctor"],
                 date=view["date"], time=view["time"])

    def _step_manage_action(self, st, message):
        lang = st["lang"]
        data = st["data"]
        doctor = self.clinic.by_id[data["doctor_id"]]
        starts_at = f"{data['date']} {data['time']}"
        try:
            if CANCEL_WORD_RE.search(message):
                self.clinic.check_change_allowed(starts_at)
                st["flow"] = "manage_confirm_cancel"
                return t("bot_manage_cancel_confirm", lang, doctor=doctor["name"],
                         date=data["date"], time=data["time"])
            if RESCHEDULE_WORD_RE.search(message):
                self.clinic.check_change_allowed(starts_at)
                data["reschedule_id"] = data["ref"]
                st["flow"] = "date"
                return self._ask_date(st, doctor)
            if DELETE_WORD_RE.search(message):
                st["flow"] = "manage_confirm_delete"
                return t("bot_manage_delete_confirm", lang)
        except BookingError as exc:
            return render_error(exc, lang)
        return t("bot_manage_unknown", lang)

    def _step_manage_confirm_cancel(self, st, message):
        lang = st["lang"]
        if YES_RE.match(message):
            try:
                self.clinic.cancel_by_patient(st["data"]["ref"])
            except BookingError as exc:
                self._reset(st)
                return render_error(exc, lang)
            self._reset(st)
            return t("bot_manage_cancelled", lang)
        if NO_RE.match(message):
            self._reset(st)
            return t("bot_manage_kept", lang)
        return t("bot_yes_no_hint", lang)

    def _step_confirm_reschedule(self, st, message):
        lang = st["lang"]
        data = st["data"]
        if YES_RE.match(message):
            try:
                self.clinic.reschedule(data["reschedule_id"], parse_day(data["date"]),
                                       data["time"], actor="patient")
            except BookingError as exc:
                self._reset(st)
                return render_error(exc, lang)
            self._reset(st)
            return t("bot_manage_rescheduled", lang, date=data["date"], time=data["time"],
                     id=data.get("ref", ""))
        if NO_RE.match(message):
            self._reset(st)
            return t("bot_manage_kept", lang)
        return t("bot_yes_no_hint", lang)

    def _step_manage_confirm_delete(self, st, message):
        lang = st["lang"]
        if YES_RE.match(message):
            self.clinic.delete_contact_data(st["data"]["contact_hash"])
            self._reset(st)
            st["history"] = []  # the saved transcript holds the patient's details too
            st["concern"] = ""
            return t("bot_manage_deleted", lang)
        if NO_RE.match(message):
            self._reset(st)
            return t("bot_manage_kept", lang)
        return t("bot_yes_no_hint", lang)

    # ----- flow plumbing -----

    def _step(self, st, message):
        flow = st["flow"]
        if flow in INTAKE_STEPS_BY_FLOW:
            key, next_flow = INTAKE_STEPS_BY_FLOW[flow]
            return self._make_intake_step(key, next_flow)(st, message)
        handler = getattr(self, f"_step_{flow}", None)
        if handler is None:
            self._reset(st)
            return t("bot_fallback", st["lang"])
        return handler(st, message)

    def _ask_date(self, st, doctor):
        lang = st["lang"]
        st["flow"] = "date"
        example = (self.clinic.now().date() + timedelta(days=1)).isoformat()
        return t("bot_ask_date", lang, doctor=doctor["name"],
                 specialty=specialty_name(doctor["specialty"], lang),
                 days=self.clinic.days_text(doctor, lang), example=example)

    def _doctor_list(self, lang):
        return "\n".join(
            f"• {d['name']} ({specialty_name(d['specialty'], lang)})" for d in self.clinic.doctors
        )

    def _reset(self, st):
        st["flow"] = None
        st["data"] = {}

    def _out(self, st, text):
        suggested = self.clinic.by_id.get(st["suggested"]) if st["suggested"] else None
        return {
            "reply": text,
            "lang": st["lang"],
            "suggested_doctor": {"id": suggested["id"], "name": suggested["name"]} if suggested else None,
            "booking": st["flow"] is not None,
            "ui": self._ui_for(st),
        }

    def _ui_for(self, st):
        """Which picker the frontend should show for the current step."""
        data = st["data"]
        if st["flow"] == "date" and data.get("doctor_id"):
            return {"type": "calendar", "doctor_id": data["doctor_id"]}
        if st["flow"] == "time" and data.get("doctor_id") and data.get("date"):
            return {"type": "slots", "doctor_id": data["doctor_id"], "date": data["date"]}
        return None


INTAKE_STEPS_BY_FLOW = {f"intake_{key}": (key, nxt) for key, nxt in INTAKE_STEPS}