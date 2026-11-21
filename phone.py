"""Phone line: Twilio calls the clinic and the chatbot answers by voice (Phase 1, English)."""
import difflib
import html
import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import os
import secrets

from flask import Blueprint, Response, current_app, jsonify, request
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

bp = Blueprint("phone", __name__, url_prefix="/phone")
log = logging.getLogger(__name__)

VOICE = "Polly.Joanna"  # Twilio's built-in English voice, included with Twilio
MAX_SPOKEN_CHARS = 300
GOODBYE_WORDS = ("goodbye", "bye", "that's all", "thank you, bye")
THANKS_WORDS = ("thanks", "thank you", "thx", "danke")


def _twiml(body):
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'
    return Response(xml, mimetype="text/xml")


def _say(text):
    return f'<Say voice="{VOICE}">{html.escape(text)}</Say>'


def _greeting():
    hour = datetime.now(ZoneInfo(current_app.config["CLINIC_TZ"])).hour
    part = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    return (
        f"{part}, you have reached {current_app.config['CLINIC_NAME']}. "
        "This call is answered by an automated assistant. "
        "Please do not share detailed medical information. How can I help you?"
    )


SPEECH_HINTS = "appointment, book, doctor, dermatologist, dermatology, general practice, Anna Meyer, Lena Fischer, vaccination, insurance, opening hours, yes, no, goodbye"


def _listen(prompt=None):
    inner = _say(prompt) if prompt else ""
    gather = (
        '<Gather input="speech" language="en-US" speechTimeout="auto" bargeIn="true" hints="' + SPEECH_HINTS + '" '
        'action="/phone/answer" method="POST">' + inner + "</Gather>"
    )
    return gather + _say("I did not hear anything, so I will end the call. Goodbye.") + "<Hangup/>"


def _speakable(text):
    """Collapses line breaks and cuts long replies at the last full sentence."""
    text = " ".join(text.split())
    if len(text) <= MAX_SPOKEN_CHARS:
        return text
    cut = text[:MAX_SPOKEN_CHARS]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > 0 else cut.rsplit(" ", 1)[0]


def _fix_speech(speech, doctors):
    """Corrects words the recognizer misheard, if they are very close to a known doctor name, specialty, or medical term."""
    vocab = {"dermatologist", "cardiologist", "orthopedist", "appointment", "doctor"}
    for doctor in doctors:
        vocab.add(doctor["specialty"].lower())
        vocab.update(part.lower() for part in doctor["name"].replace(".", " ").split())
    words = []
    for word in speech.split():
        core = word.strip(".,?!").lower()
        match = difflib.get_close_matches(core, vocab, n=1, cutoff=0.8) if core and core not in vocab else []
        words.append(match[0] if match else word)
    return " ".join(words)


def _voice_prompts(text):
    """Turns on-screen instructions (calendar, slots below) into things a caller can say."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        low = sentence.lower()
        if "calendar" in low or "below" in low:
            if "date" in low or "day" in low:
                out.append("Please say a date, for example tuesday, tomorrow, or 2026-11-22.")
            elif "time" in low or "slot" in low:
                out.append("Please say a time, for example 10 o'clock.")
        else:
            out.append(sentence)
    return " ".join(out)


PHONE_RE = re.compile(r"\+\d[\d ]{7,}\d|\b0\d[\d ]{8,}\d")


def _spell_numbers(text):
    """Reads phone numbers digit by digit, so 0174 6344155 is not spoken as one large number."""
    def spell(match):
        number = match.group(0).strip()
        digits = re.sub(r"\D", "", number)
        prefix = "plus " if number.startswith("+") else ""
        return prefix + " ".join(digits)
    return PHONE_RE.sub(spell, text)


def _voice_text(text):
    """Keeps phone replies short: long doctor lists become a request for a name or specialty."""
    text = _voice_prompts(text)
    text = _spell_numbers(text)
    lines = text.splitlines()
    bullets = [line for line in lines if line.strip().startswith("•")]
    if len(bullets) > 3:
        kept = " ".join(line for line in lines if not line.strip().startswith("•"))
        return _speakable(kept + " Please say the name of the doctor you want, or the medical area, such as dermatology.")
    return _speakable(text)


@bp.route("/voice", methods=["POST"])
def incoming():
    return _twiml(_listen(_greeting()))


@bp.route("/answer", methods=["POST"])
def answer():
    call_id = request.form.get("CallSid", "")
    speech = (request.form.get("SpeechResult") or "").strip()
    log.info("phone call %s heard: %r", call_id, speech)
    if not call_id:
        return _twiml(_say("Sorry, something went wrong. Goodbye.") + "<Hangup/>")
    if not speech:
        return _twiml(_listen("Sorry, I did not catch that. Could you say that again?"))
    if any(word in speech.lower() for word in GOODBYE_WORDS):
        return _twiml(_say("Thank you for calling. Goodbye.") + "<Hangup/>")
    if any(word in speech.lower() for word in THANKS_WORDS):
        return _twiml(_listen("You're welcome. Is there anything else I can help with?"))
    speech = _fix_speech(speech, current_app.extensions["clinic"].doctors)
    try:
        result = current_app.extensions["bot"].reply(call_id, speech, lang="en")
        text = result["reply"] if isinstance(result, dict) else getattr(result, "reply", "")
    except Exception:
        log.exception("phone chat failed")
        text = ""
    text = _voice_text(text or "Sorry, I could not answer that. Please contact the reception.")
    return _twiml(_listen(text))


@bp.route("/token", methods=["GET"])
def browser_token():
    """Gives the test-call page a short-lived Twilio token. Calls connect to /phone/voice."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    api_key = os.environ.get("TWILIO_API_KEY_SID", "")
    api_secret = os.environ.get("TWILIO_API_KEY_SECRET", "")
    app_sid = os.environ.get("TWILIO_TWIML_APP_SID", "")
    settings = {
        "TWILIO_ACCOUNT_SID": account_sid,
        "TWILIO_API_KEY_SID": api_key,
        "TWILIO_API_KEY_SECRET": api_secret,
        "TWILIO_TWIML_APP_SID": app_sid,
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        return jsonify(error="Browser calling is not configured.", missing=missing), 503
    token = AccessToken(account_sid, api_key, api_secret,
                        identity="visitor-" + secrets.token_hex(6), ttl=3600)
    token.add_grant(VoiceGrant(outgoing_application_sid=app_sid, incoming_allow=False))
    jwt = token.to_jwt()
    if isinstance(jwt, bytes):
        jwt = jwt.decode()
    return jsonify(token=jwt)
