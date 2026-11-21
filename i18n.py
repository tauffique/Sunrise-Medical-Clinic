"""Patient-facing text in English and German.

Staff pages are English only. Every key must exist in both languages; `t()` falls
back to English if a German key is missing.
"""
import logging

LANGS = ("en", "de")
log = logging.getLogger(__name__)

DAYS = {
    "en": {
        "names": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "abbr": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    },
    "de": {
        "names": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
        "abbr": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    },
}

SPECIALTY_DE = {
    "General Practice": "Allgemeinmedizin",
    "Cardiology": "Kardiologie",
    "Dermatology": "Dermatologie",
    "Orthopedics": "Orthopädie",
}

MESSAGES = {
    "en": {
        # ----- website -----
        "nav_doctors": "Doctors",
        "nav_contact": "Contact",
        "nav_book": "Book",
        "hero_title": "Caring for you and your family",
        "hero_text": "Book an appointment online, or chat with our assistant to find the right doctor for your concern.",
        "btn_book": "Book an appointment",
        "btn_chat": "Chat with our assistant",
        "doctors_heading": "Our doctors",
        "available": "Available",
        "book_heading": "Book an appointment",
        "doctor_label": "Doctor",
        "name_label": "Full name",
        "contact_label": "Phone or email",
        "reason_label": "Reason for visit (optional)",
        "intake_label": "Anything the doctor should know, such as conditions, medications or allergies (optional)",
        "consent_label": "I agree that the clinic stores my details and health information to arrange this appointment, for up to {days} days. See the privacy notice.",
        "submit": "Request appointment",
        "close": "Close",
        "pick_date": "Choose a date",
        "selected_none": "No date or time selected yet.",
        "selected_fmt": "Selected: {date} at {time}",
        "date_only_fmt": "Date: {date}. Now pick a free time.",
        "pick_date_slots": "Pick a date to see free times.",
        "no_free_day": "No free times on this day.",
        "choose_doctor_first": "Choose a doctor first.",
        "calendar_error": "Could not load the calendar.",
        "live_updated": "Live · updated {time}",
        "free_slots": "{n} free",
        "fully_booked": "Fully booked",
        "not_available": "Not available",
        "sending": "Sending…",
        "request_sent": "Request sent (reference #{id}). The clinic will confirm by phone or email.",
        "generic_error": "Something went wrong. Please try again.",
        "network_error": "Connection problem. Please try again.",
        "chat_title": "Clinic assistant",
        "chat_greeting": "How can I help you?",
        "chat_placeholder": "Describe your concern or ask a question",
        "chat_new": "New conversation",
        "health_heading": "Health information (optional)",
        "f_conditions": "Current or past conditions",
        "f_medications": "Medications",
        "f_allergies": "Allergies",
        "f_insurance": "Insurance (statutory, private or none)",
        "send": "Send",
        "book_with": "Book with {name}",
        "open_chat": "Open chat",
        "close_chat": "Close chat",
        "close_booking": "Close booking",
        "contact_heading": "Contact",
        "hours_line": "Monday to Friday, 09:00 to 17:00",
        "emergency_line": "In an emergency, call 112.",
        "footer_disclaimer": "This website and its assistant do not replace medical advice, diagnosis or emergency care.",
        "link_privacy": "Privacy notice",
        "link_imprint": "Imprint",
        "privacy_title": "Privacy notice",
        "privacy_text": (
            "Which data we collect: name, phone or email, the reason for your visit and, if you choose to give them, "
            "medical details such as conditions, medications, allergies and insurance type.\n\n"
            "Why: only to arrange, confirm, change and remind you of your appointment, and to provide the care you book.\n\n"
            "How it is protected: personal and health details are stored encrypted. Only the doctor you booked with can "
            "see your medical details. Reception sees your name, contact details and appointment time. All access is logged.\n\n"
            "How long: appointment data is deleted automatically after the retention period. You can ask us to delete "
            "your data at any time, for example by typing 'delete my data' in the chat.\n\n"
            "Your rights: you can request access, correction, restriction or deletion of your data, and lodge a complaint "
            "with a data protection authority."
        ),
        "imprint_title": "Imprint",
        "imprint_text": (
            "Sunrise Medical Clinic\nHauptstraße 1, 12345 Musterstadt\n\n"
            "Replace this placeholder with the legally required imprint for your practice before going live."
        ),
        "error_title": "Something went wrong",
        "error_404": "We couldn't find that page.",
        "error_500": "An unexpected error occurred. Please try again later.",
        "error_generic": "Please check your request and try again.",
        "back_home": "Back to home",
        "rate_limited": "Too many requests. Please wait a moment and try again.",
        # ----- validation errors (shown to patients) -----
        "err_consent": "Please agree to the data processing notice to continue.",
        "err_unknown_doctor": "I don't recognise that doctor.",
        "err_past_date": "That date has already passed.",
        "err_not_working": "{doctor} doesn't work on {day}. Available days: {days}.",
        "err_date_format": "Please provide a valid date (YYYY-MM-DD).",
        "err_name": "Please tell us the patient's name.",
        "err_contact": "Please give a phone number or email so we can confirm.",
        "err_slot_unavailable": "That time isn't available. Please pick one of the free times.",
        "err_slot_taken": "Sorry, that slot was just taken. Please choose another time.",
        "err_not_found": "That appointment could not be found.",
        "err_too_late": "Changes within 24 hours of the appointment need a phone call to the front desk.",
        "err_month": "month must look like YYYY-MM",
        "err_session": "A valid session_id is required.",
        "err_pick_date": "Please pick a valid date.",
        # ----- chatbot -----
        "bot_empty": "Type a message and I'll help.",
        "bot_emergency": "This may be a medical emergency. Please call 112 (or your local emergency number) now, or go to the nearest emergency department. I can't handle emergencies in chat.",
        "bot_cancelled": "No problem, I've cancelled that request. How else can I help?",
        "bot_no_suggestion": "No problem. Tell me more if you'd like another suggestion.",
        "bot_greet_morning": "Good morning!",
        "bot_greet_afternoon": "Good afternoon!",
        "bot_greet_evening": "Good evening!",
        "bot_how_help": "How can I help you?",
        "bot_closing": "Thank you for contacting Sunrise Medical Clinic. Have a good day. If you have a medical emergency, call 112.",        "bot_suggestion": "A good next step would be {doctor} ({specialty}). Would you like to book an appointment? Reply 'yes' to book with them, or say 'book' to choose another doctor.",
        "bot_disclaimer": "I'm an automated assistant, not a doctor, so this is not a diagnosis. If your symptoms are severe or getting worse, please see a doctor promptly.",
        "bot_which_doctor": "Sure, I can book that. Which doctor would you like to see?",
        "bot_doctor_not_matched": "I couldn't match that to one of our doctors. Please choose:",
        "bot_ask_date": "{doctor} ({specialty}) is in on {days}. Pick a date in the calendar below, or type one like 'tuesday', 'tomorrow' or {example}.",
        "bot_date_invalid": "Please pick a date in the calendar, or type one like 'tuesday', 'tomorrow' or 2026-11-25.",
        "bot_choose_other_date": "Please choose another date.",
        "bot_no_slots": "There are no free slots that day. Please try another date.",
        "bot_time_prompt": "Free times on {date}: {times}. Pick a time below, or type one.",
        "bot_time_taken": "That time has just been taken or isn't offered. Free times right now: {times}.",
        "bot_day_full": "That day is now fully booked. Please pick another date.",
        "bot_consent": "Before I collect your details: we store your name, contact details and health information only to arrange this appointment, and delete them after {days} days. Reply 'yes' to agree, or 'cancel' to stop. Privacy notice: {url}",
        "bot_consent_again": "I need your agreement to continue. Reply 'yes' to agree, or 'cancel' to stop.",
        "bot_ask_name": "Thanks. What is the patient's full name?",
        "bot_name_short": "Please enter the patient's full name.",
        "bot_ask_contact": "What's the best phone number or email to confirm on?",
        "bot_contact_invalid": "Please enter a valid phone number or email address.",
        "bot_reason_keep": "Reason for the visit? Type 'skip' to keep what you told me: \"{reason}\"",
        "bot_reason_ask": "Reason for the visit? Type 'skip' to leave it blank.",
        "bot_intake_offer": "Would you like to answer a few short questions for the doctor (conditions, medications, allergies, insurance)? Reply 'yes' or 'skip'.",
        "bot_intake_conditions": "Any past or current medical conditions? Type 'skip' if none.",
        "bot_intake_medications": "Are you taking any medications? Type 'skip' if none.",
        "bot_intake_allergies": "Any allergies? Type 'skip' if none.",
        "bot_intake_insurance": "Insurance type: statutory, private or none? Type 'skip' to leave it blank.",
        "bot_confirm": "Please confirm:\nDoctor: {doctor}\nDate: {date} at {time}\nPatient: {name}\nContact: {contact}\nReason: {reason}\n\nReply 'yes' to send the request, or 'cancel' to stop.",
        "bot_confirm_again": "Reply 'yes' to send the request, or 'cancel' to stop.",
        "bot_nothing_booked": "Okay, nothing was booked. How else can I help?",
        "bot_done": "Your request is in (reference #{id}). {doctor}'s team will confirm it with you at {contact}. Anything else I can help with?",
        "bot_finish_fail": "Sorry, I couldn't book that: {error} Say 'book' to try again.",
        "bot_manage_intro": "I can help you change or cancel an appointment. Please send your reference number.",
        "bot_manage_ask_contact": "Thanks. Please confirm the phone number or email you booked with.",
        "bot_manage_ref_invalid": "Please send your reference number, for example 12.",
        "bot_manage_not_found": "I couldn't find a matching upcoming appointment. Please check the reference number and try again.",
        "bot_manage_locked": "Too many failed attempts. For your security, please call the front desk to change your appointment.",
        "bot_manage_found": "Your appointment: {doctor} on {date} at {time} (reference #{id}). Type 'cancel', 'reschedule' or 'delete my data'.",
        "bot_manage_unknown": "Please type 'cancel', 'reschedule' or 'delete my data'.",
        "bot_manage_cancel_confirm": "Cancel your appointment with {doctor} on {date} at {time}? Reply 'yes' to confirm.",
        "bot_manage_kept": "Okay, your appointment stays as it is.",
        "bot_manage_cancelled": "Your appointment has been cancelled. Thank you for letting us know.",
        "bot_confirm_reschedule": "Move your appointment with {doctor} to {date} at {time}? Reply 'yes' to confirm.",
        "bot_manage_rescheduled": "Done. Your appointment is now on {date} at {time} (reference #{id}).",
        "bot_manage_delete_confirm": "This permanently deletes all appointment data we hold for you. Reply 'yes' to confirm.",
        "bot_manage_deleted": "Your appointment data has been deleted.",
        "bot_yes_no_hint": "Please reply 'yes' or 'no'.",
        "bot_choose_action": "Please choose an option first.",
        # ----- emails -----
        "mail_confirm_subject": "Your appointment at {clinic} is confirmed",
        "mail_confirm_body": (
            "Hello,\n\nyour appointment with {doctor} is confirmed.\n\n"
            "Date: {date}\nTime: {time}\nReference: #{id}\nAddress: {address}\n\n"
            "Please cancel or reschedule at least 24 hours in advance. A calendar file is attached.\n\n{clinic}"
        ),
        "mail_reminder_subject": "Reminder: your appointment at {clinic}",
        "mail_reminder_body": (
            "Hello,\n\nthis is a reminder of your appointment with {doctor} on {date} at {time} "
            "(reference #{id}).\nAddress: {address}\n\n{clinic}"
        ),
    },
    "de": {
        "nav_doctors": "Ärzte",
        "nav_contact": "Kontakt",
        "nav_book": "Termin",
        "hero_title": "Medizin für Sie und Ihre Familie",
        "hero_text": "Buchen Sie online einen Termin oder fragen Sie unseren Assistenten, welcher Arzt zu Ihrem Anliegen passt.",
        "btn_book": "Termin buchen",
        "btn_chat": "Mit dem Assistenten chatten",
        "doctors_heading": "Unsere Ärzte",
        "available": "Sprechzeiten",
        "book_heading": "Termin buchen",
        "doctor_label": "Arzt",
        "name_label": "Vollständiger Name",
        "contact_label": "Telefon oder E-Mail",
        "reason_label": "Anliegen (optional)",
        "intake_label": "Was der Arzt wissen sollte, z. B. Vorerkrankungen, Medikamente oder Allergien (optional)",
        "consent_label": "Ich stimme zu, dass die Praxis meine Daten und Gesundheitsangaben zur Terminvereinbarung bis zu {days} Tage speichert. Siehe Datenschutzhinweise.",
        "submit": "Termin anfragen",
        "close": "Schließen",
        "pick_date": "Datum wählen",
        "selected_none": "Noch kein Datum oder keine Uhrzeit gewählt.",
        "selected_fmt": "Gewählt: {date} um {time}",
        "date_only_fmt": "Datum: {date}. Bitte jetzt eine freie Uhrzeit wählen.",
        "pick_date_slots": "Wählen Sie ein Datum, um freie Zeiten zu sehen.",
        "no_free_day": "An diesem Tag sind keine Zeiten frei.",
        "choose_doctor_first": "Bitte zuerst einen Arzt wählen.",
        "calendar_error": "Der Kalender konnte nicht geladen werden.",
        "live_updated": "Live · aktualisiert {time}",
        "free_slots": "{n} frei",
        "fully_booked": "Ausgebucht",
        "not_available": "Nicht verfügbar",
        "sending": "Wird gesendet…",
        "request_sent": "Anfrage gesendet (Referenz #{id}). Die Praxis bestätigt telefonisch oder per E-Mail.",
        "generic_error": "Etwas ist schiefgelaufen. Bitte erneut versuchen.",
        "network_error": "Verbindungsproblem. Bitte erneut versuchen.",
        "chat_title": "Praxis-Assistent",
        "chat_greeting": "Wie kann ich Ihnen helfen?",
        "chat_placeholder": "Beschreiben Sie Ihr Anliegen oder stellen Sie eine Frage",
        "chat_new": "Neues Gespräch",
        "health_heading": "Gesundheitsangaben (optional)",
        "f_conditions": "Aktuelle oder frühere Erkrankungen",
        "f_medications": "Medikamente",
        "f_allergies": "Allergien",
        "f_insurance": "Versicherung (gesetzlich, privat oder keine)",
        "send": "Senden",
        "book_with": "Termin bei {name}",
        "open_chat": "Chat öffnen",
        "close_chat": "Chat schließen",
        "close_booking": "Buchung schließen",
        "contact_heading": "Kontakt",
        "hours_line": "Montag bis Freitag, 9:00 bis 17:00 Uhr",
        "emergency_line": "Im Notfall rufen Sie 112 an.",
        "footer_disclaimer": "Diese Website und ihr Assistent ersetzen keine ärztliche Beratung, Diagnose oder Notfallversorgung.",
        "link_privacy": "Datenschutz",
        "link_imprint": "Impressum",
        "privacy_title": "Datenschutzhinweise",
        "privacy_text": (
            "Welche Daten wir erheben: Name, Telefon oder E-Mail, das Anliegen Ihres Besuchs und, wenn Sie sie angeben, "
            "medizinische Angaben wie Vorerkrankungen, Medikamente, Allergien und Versicherungsart.\n\n"
            "Wofür: ausschließlich zur Vereinbarung, Bestätigung, Änderung und Erinnerung Ihres Termins sowie zur "
            "Behandlung, die Sie buchen.\n\n"
            "Wie wir sie schützen: Personen- und Gesundheitsdaten werden verschlüsselt gespeichert. Nur der gebuchte "
            "Arzt kann Ihre medizinischen Angaben einsehen. Das Empfangspersonal sieht Name, Kontaktdaten und Termin. "
            "Alle Zugriffe werden protokolliert.\n\n"
            "Wie lange: Termindaten werden nach Ablauf der Aufbewahrungsfrist automatisch gelöscht. Sie können die "
            "Löschung jederzeit verlangen, zum Beispiel indem Sie im Chat 'Daten löschen' eingeben.\n\n"
            "Ihre Rechte: Sie können Auskunft, Berichtigung, Einschränkung oder Löschung Ihrer Daten verlangen und sich "
            "bei einer Datenschutzaufsichtsbehörde beschweren."
        ),
        "imprint_title": "Impressum",
        "imprint_text": (
            "Sunrise Medical Clinic\nHauptstraße 1, 12345 Musterstadt\n\n"
            "Ersetzen Sie diesen Platzhalter vor dem Go-live durch das gesetzlich vorgeschriebene Impressum Ihrer Praxis."
        ),
        "error_title": "Etwas ist schiefgelaufen",
        "error_404": "Diese Seite wurde nicht gefunden.",
        "error_500": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
        "error_generic": "Bitte prüfen Sie Ihre Eingabe und versuchen Sie es erneut.",
        "back_home": "Zur Startseite",
        "rate_limited": "Zu viele Anfragen. Bitte kurz warten und erneut versuchen.",
        "err_consent": "Bitte stimmen Sie den Datenschutzhinweisen zu, um fortzufahren.",
        "err_unknown_doctor": "Diesen Arzt kenne ich nicht.",
        "err_past_date": "Dieses Datum liegt in der Vergangenheit.",
        "err_not_working": "{doctor} hat am {day} keine Sprechstunde. Verfügbare Tage: {days}.",
        "err_date_format": "Bitte ein gültiges Datum angeben (JJJJ-MM-TT).",
        "err_name": "Bitte geben Sie den Namen des Patienten an.",
        "err_contact": "Bitte Telefonnummer oder E-Mail für die Bestätigung angeben.",
        "err_slot_unavailable": "Diese Uhrzeit ist nicht verfügbar. Bitte eine der freien Zeiten wählen.",
        "err_slot_taken": "Leider wurde dieser Termin gerade vergeben. Bitte eine andere Zeit wählen.",
        "err_not_found": "Dieser Termin wurde nicht gefunden.",
        "err_too_late": "Änderungen innerhalb von 24 Stunden vor dem Termin bitte telefonisch an die Praxis.",
        "err_month": "Monat im Format JJJJ-MM angeben",
        "err_session": "Eine gültige session_id ist erforderlich.",
        "err_pick_date": "Bitte ein gültiges Datum wählen.",
        "bot_empty": "Schreiben Sie eine Nachricht, dann helfe ich Ihnen.",
        "bot_emergency": "Dies könnte ein medizinischer Notfall sein. Bitte rufen Sie sofort 112 an oder gehen Sie in die nächste Notaufnahme. Im Chat kann ich keine Notfälle bearbeiten.",
        "bot_cancelled": "Kein Problem, ich habe die Anfrage abgebrochen. Wobei kann ich sonst helfen?",
        "bot_no_suggestion": "Kein Problem. Erzählen Sie mir mehr, wenn Sie einen anderen Vorschlag möchten.",
        "bot_greet_morning": "Guten Morgen!",
        "bot_greet_afternoon": "Guten Tag!",
        "bot_greet_evening": "Guten Abend!",
        "bot_how_help": "Wie kann ich Ihnen helfen?",
        "bot_closing": "Vielen Dank für Ihre Nachricht bei der Sunrise Medical Clinic. Ich wünsche Ihnen einen schönen Tag. Bei einem medizinischen Notfall wählen Sie bitte 112.",        "bot_suggestion": "Ein guter nächster Schritt wäre {doctor} ({specialty}). Möchten Sie einen Termin buchen? Antworten Sie mit 'ja', um dort einen Termin zu buchen, oder schreiben Sie 'Termin', um einen anderen Arzt zu wählen.",
        "bot_disclaimer": "Ich bin ein automatischer Assistent und kein Arzt, daher ist dies keine Diagnose. Wenn Ihre Beschwerden stark sind oder sich verschlechtern, suchen Sie bitte zeitnah einen Arzt auf.",
        "bot_which_doctor": "Gerne, ich buche das. Zu welchem Arzt möchten Sie?",
        "bot_doctor_not_matched": "Das konnte ich keinem unserer Ärzte zuordnen. Bitte wählen Sie:",
        "bot_ask_date": "{doctor} ({specialty}) hat Sprechzeit am {days}. Wählen Sie unten ein Datum im Kalender oder geben Sie z. B. 'Dienstag', 'morgen' oder {example} ein.",
        "bot_date_invalid": "Bitte wählen Sie ein Datum im Kalender oder geben Sie z. B. 'Dienstag', 'morgen' oder 2026-11-25 ein.",
        "bot_choose_other_date": "Bitte wählen Sie ein anderes Datum.",
        "bot_no_slots": "An diesem Tag sind keine Termine frei. Bitte wählen Sie ein anderes Datum.",
        "bot_time_prompt": "Freie Zeiten am {date}: {times}. Wählen Sie unten eine Uhrzeit oder geben Sie eine ein.",
        "bot_time_taken": "Diese Uhrzeit wurde gerade vergeben oder ist nicht verfügbar. Freie Zeiten jetzt: {times}.",
        "bot_day_full": "Dieser Tag ist jetzt ausgebucht. Bitte wählen Sie ein anderes Datum.",
        "bot_consent": "Bevor ich Ihre Daten aufnehme: Wir speichern Name, Kontaktdaten und Gesundheitsangaben nur zur Terminvereinbarung und löschen sie nach {days} Tagen. Antworten Sie mit 'ja' zur Zustimmung oder 'abbrechen'. Datenschutzhinweise: {url}",
        "bot_consent_again": "Ich benötige Ihre Zustimmung, um fortzufahren. Antworten Sie mit 'ja' oder 'abbrechen'.",
        "bot_ask_name": "Danke. Wie lautet der vollständige Name des Patienten?",
        "bot_name_short": "Bitte geben Sie den vollständigen Namen des Patienten an.",
        "bot_ask_contact": "Unter welcher Telefonnummer oder E-Mail können wir Sie bestätigen?",
        "bot_contact_invalid": "Bitte geben Sie eine gültige Telefonnummer oder E-Mail-Adresse an.",
        "bot_reason_keep": "Anliegen des Besuchs? Schreiben Sie 'überspringen', um Ihre Angabe zu behalten: \"{reason}\"",
        "bot_reason_ask": "Anliegen des Besuchs? Schreiben Sie 'überspringen', um es leer zu lassen.",
        "bot_intake_offer": "Möchten Sie dem Arzt ein paar kurze Fragen beantworten (Vorerkrankungen, Medikamente, Allergien, Versicherung)? Antworten Sie mit 'ja' oder 'überspringen'.",
        "bot_intake_conditions": "Gibt es Vorerkrankungen oder aktuelle Beschwerden? Schreiben Sie 'überspringen', wenn nichts zutrifft.",
        "bot_intake_medications": "Nehmen Sie Medikamente ein? Schreiben Sie 'überspringen', wenn nicht.",
        "bot_intake_allergies": "Gibt es Allergien? Schreiben Sie 'überspringen', wenn nicht.",
        "bot_intake_insurance": "Versicherungsart: gesetzlich, privat oder keine? Schreiben Sie 'überspringen', um es leer zu lassen.",
        "bot_confirm": "Bitte bestätigen Sie:\nArzt: {doctor}\nDatum: {date} um {time}\nPatient: {name}\nKontakt: {contact}\nAnliegen: {reason}\n\nAntworten Sie mit 'ja', um die Anfrage zu senden, oder 'abbrechen'.",
        "bot_confirm_again": "Antworten Sie mit 'ja', um die Anfrage zu senden, oder 'abbrechen'.",
        "bot_nothing_booked": "Okay, es wurde nichts gebucht. Wobei kann ich sonst helfen?",
        "bot_done": "Ihre Anfrage ist eingegangen (Referenz #{id}). Das Team von {doctor} bestätigt sie Ihnen unter {contact}. Kann ich sonst noch helfen?",
        "bot_finish_fail": "Leider konnte ich das nicht buchen: {error} Schreiben Sie 'Termin', um es erneut zu versuchen.",
        "bot_manage_intro": "Ich helfe Ihnen beim Ändern oder Absagen eines Termins. Bitte senden Sie Ihre Referenznummer.",
        "bot_manage_ask_contact": "Danke. Bitte bestätigen Sie die Telefonnummer oder E-Mail, mit der Sie gebucht haben.",
        "bot_manage_ref_invalid": "Bitte senden Sie Ihre Referenznummer, z. B. 12.",
        "bot_manage_not_found": "Ich habe keinen passenden bevorstehenden Termin gefunden. Bitte prüfen Sie die Referenznummer und versuchen Sie es erneut.",
        "bot_manage_locked": "Zu viele Fehlversuche. Zu Ihrer Sicherheit rufen Sie bitte die Praxis an, um Ihren Termin zu ändern.",
        "bot_manage_found": "Ihr Termin: {doctor} am {date} um {time} (Referenz #{id}). Schreiben Sie 'absagen', 'verschieben' oder 'Daten löschen'.",
        "bot_manage_unknown": "Bitte schreiben Sie 'absagen', 'verschieben' oder 'Daten löschen'.",
        "bot_manage_cancel_confirm": "Ihren Termin bei {doctor} am {date} um {time} absagen? Antworten Sie mit 'ja' zur Bestätigung.",
        "bot_manage_kept": "Okay, Ihr Termin bleibt bestehen.",
        "bot_manage_cancelled": "Ihr Termin wurde abgesagt. Danke, dass Sie uns Bescheid gegeben haben.",
        "bot_confirm_reschedule": "Ihren Termin bei {doctor} auf {date} um {time} verlegen? Antworten Sie mit 'ja' zur Bestätigung.",
        "bot_manage_rescheduled": "Erledigt. Ihr Termin ist jetzt am {date} um {time} (Referenz #{id}).",
        "bot_manage_delete_confirm": "Dies löscht dauerhaft alle Termindaten, die wir zu Ihnen gespeichert haben. Antworten Sie mit 'ja' zur Bestätigung.",
        "bot_manage_deleted": "Ihre Termindaten wurden gelöscht.",
        "bot_yes_no_hint": "Bitte antworten Sie mit 'ja' oder 'nein'.",
        "bot_choose_action": "Bitte wählen Sie zuerst eine Option.",
        "mail_confirm_subject": "Ihr Termin bei {clinic} ist bestätigt",
        "mail_confirm_body": (
            "Guten Tag,\n\nIhr Termin bei {doctor} ist bestätigt.\n\n"
            "Datum: {date}\nUhrzeit: {time}\nReferenz: #{id}\nAdresse: {address}\n\n"
            "Bitte sagen Sie Termine mindestens 24 Stunden vorher ab oder verlegen Sie sie. Eine Kalenderdatei ist angehängt.\n\n{clinic}"
        ),
        "mail_reminder_subject": "Erinnerung: Ihr Termin bei {clinic}",
        "mail_reminder_body": (
            "Guten Tag,\n\nhiermit erinnern wir Sie an Ihren Termin bei {doctor} am {date} um {time} "
            "(Referenz #{id}).\nAdresse: {address}\n\n{clinic}"
        ),
    },
}


def t(key, lang="en", **params):
    table = MESSAGES.get(lang) or MESSAGES["en"]
    text = table.get(key)
    if text is None:
        text = MESSAGES["en"].get(key, key)
    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError):
        log.error("Missing parameter for message %s", key)
        return text


def specialty_name(name, lang):
    if lang == "de":
        return SPECIALTY_DE.get(name, name)
    return name


def render_error(error, lang):
    """Turn a BookingError into patient-facing text in the given language."""
    params = dict(error.params)
    if "weekday" in params:
        params["day"] = DAYS[lang]["names"][params.pop("weekday")]
    if "working" in params:
        params["days"] = ", ".join(DAYS[lang]["abbr"][i] for i in params.pop("working"))
    return t(error.key, lang, **params)