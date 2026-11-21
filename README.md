# Sunrise Medical Clinic

A clinic website with a bilingual (English and German) chatbot. The chatbot answers questions from a knowledge base, flags emergencies, suggests the right specialist, and books, reschedules or cancels appointments. Patients give consent first, and the doctor sees a pre-appointment questionnaire.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 manage.py init-db
python3 manage.py create-user --email reception@clinic.example --role reception
python3 app.py                     # open http://127.0.0.1:8000
```

In development, the encryption key is created automatically in `instance/dev-encryption.key`. Do not use that file in production.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Configuration

Copy `.env.example` to `.env` and fill in the values. In production (`CLINIC_ENV=production`) the app refuses to start unless `SECRET_KEY` and `CLINIC_ENCRYPTION_KEY` are set.

**Back up `CLINIC_ENCRYPTION_KEY` separately from the database.** If the key is lost, stored health details cannot be recovered.

## Chatbot

- Answers come from `data/knowledge.json` using TF-IDF retrieval, with no external service.
- Optional: install `anthropic` and set `ANTHROPIC_API_KEY` to let Claude write answers. Those answers are marked for staff review. Review the output before real patients use this path.
- Language is detected from each message. The page language is used only for the first message of a conversation.
- Chat history is encrypted and saved, so it survives restarts. Patients can clear it with the reset button or by asking the bot to delete their data.

## Data protection

- Consent is required before booking, and it is recorded with each appointment.
- Health details (conditions, medications, allergies, insurance) are encrypted at rest with Fernet.
- Contact details are stored as a keyed hash for lookup, so a patient can find their booking by reference and contact without the contact being stored in plain text.
- Appointments are deleted after `RETENTION_DAYS`. Chat sessions are deleted after `SESSION_RETENTION_HOURS`.
- Patients can request erasure through the chatbot. Staff can run the cleanup manually.
- Staff actions are written to an audit log.

## Staff roles

- **Reception** sees names, contact details and appointment times. It does not see reasons or health details.
- **Doctor** sees only their own patients, including the reason for the visit and the questionnaire answers.

Create accounts with the CLI. There is no self-service sign-up.

```bash
python3 manage.py create-user --email dr.meyer@clinic.example --role doctor --doctor-id dr-meyer
```

## Scheduled jobs

Run these daily with cron or your scheduler:

```bash
python3 manage.py send-reminders   # sends 24-hour reminder e-mails with .ics files
python3 manage.py cleanup          # deletes expired appointments and chat sessions
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/doctors` | List doctors and their specialties |
| GET | `/api/availability?doctor_id=&month=YYYY-MM` | Free days for a month |
| GET | `/api/slots?doctor_id=&date=YYYY-MM-DD` | Free times for one day |
| POST | `/api/appointments` | Book (requires consent and the CSRF header) |
| POST | `/api/chat` | Send a chat message |
| GET | `/api/chat/history?session_id=` | Restore a conversation |
| GET | `/api/stream` | Server-Sent Events for live updates |

JSON requests must send the token from the page's `csrf-token` meta tag in the `X-CSRF-Token` header.

## Deployment

```bash
docker build -t sunrise-clinic .
docker run -p 8000:8000 --env-file .env -v clinic-data:/app/instance sunrise-clinic
```

Run the container behind an HTTPS reverse proxy. The app runs one worker with 16 threads. Live updates use an in-process change bus, so do not run more than one worker unless you replace that bus with a shared broker.

## Before going live

- [ ] Replace all placeholder clinic details in `.env` and `data/knowledge.json`.
- [ ] Have a clinician and a native German speaker review every German text.
- [ ] Set up real SMTP delivery and test the confirmation and reminder e-mails.
- [ ] Decide on a data processing agreement with your hosting provider and document the legal basis for processing.
- [ ] Review the privacy and imprint pages with a lawyer.
- [ ] Back up the database and the encryption key, and test restoring both.
- [ ] Add staff two-factor authentication or a password reset flow. These are not included yet.

## Known limits

- No SMS reminders.
- No password reset or two-factor authentication for staff.
- Staff accounts can only be created from the command line.
- Single worker only (see Deployment).
- Claude-written answers are not clinically validated.# Sunrise-Medical-Clinic
