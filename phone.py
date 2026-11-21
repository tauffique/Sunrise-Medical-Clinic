"""Phone line: Twilio calls the clinic and the chatbot answers by voice (Phase 1, English)."""
import html
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, request

bp = Blueprint("phone", __name__, url_prefix="/phone")
log = logging.getLogger(__name__)

VOICE = "Polly.Joanna"  # Twilio's built-in English voice, included with Twilio
MAX_SPOKEN_CHARS = 500
GOODBYE_WORDS = ("goodbye", "bye", "that's all", "thank you, bye")


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
        '<Gather input="speech" language="en-US" speechTimeout="auto" hints="' + SPEECH_HINTS + '" '
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


@bp.route("/voice", methods=["POST"])
def incoming():
    return _twiml(_say(_greeting()) + _listen())


@bp.route("/answer", methods=["POST"])
def answer():
    call_id = request.form.get("CallSid", "")
    speech = (request.form.get("SpeechResult") or "").strip()
    if not call_id:
        return _twiml(_say("Sorry, something went wrong. Goodbye.") + "<Hangup/>")
    if not speech:
        return _twiml(_say("Sorry, I did not catch that.") + _listen("Could you say that again?"))
    if any(word in speech.lower() for word in GOODBYE_WORDS):
        return _twiml(_say("Thank you for calling. Goodbye.") + "<Hangup/>")
    try:
        result = current_app.extensions["bot"].reply(call_id, speech, lang="en")
        text = result["reply"] if isinstance(result, dict) else getattr(result, "reply", "")
    except Exception:
        log.exception("phone chat failed")
        text = ""
    text = _speakable(text or "Sorry, I could not answer that. Please contact the reception.")
    return _twiml(_say(text) + _listen("Anything else I can help with?"))
