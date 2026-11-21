"""Command-line tools: staff accounts, reminder emails and retention cleanup.

    python manage.py create-user --email reception@clinic.example --role reception
    python manage.py create-user --email dr.sharma@clinic.example --role doctor --doctor-id dr-sharma
    python manage.py send-reminders     # run hourly (cron or a systemd timer)
    python manage.py cleanup            # run daily: deletes expired appointments and chat sessions
"""
import argparse
import getpass
import sqlite3
import sys

from werkzeug.security import generate_password_hash

from app import create_app
from notifications import send_reminders

MIN_PASSWORD_LENGTH = 12


def _create_user(app, email, role, doctor_id):
    store = app.extensions["store"]
    clinic = app.extensions["clinic"]
    email = email.strip().lower()
    if role == "doctor" and (not doctor_id or doctor_id not in clinic.by_id):
        sys.exit(f"A doctor account needs --doctor-id set to one of: {', '.join(clinic.by_id)}")
    if role != "doctor" and doctor_id:
        sys.exit("--doctor-id is only used with --role doctor")
    first = getpass.getpass("Password: ")
    if len(first) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if getpass.getpass("Repeat password: ") != first:
        sys.exit("The passwords do not match.")
    try:
        store.create_user(email, generate_password_hash(first), role, doctor_id or None)
    except sqlite3.IntegrityError:
        sys.exit(f"A user with the email {email} already exists.")
    store.audit("cli", f"create-user:{role}")
    print(f"Created {role} account {email}.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Clinic administration commands.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init-db", help="create the database and its tables")

    user = commands.add_parser("create-user", help="create a reception or doctor login")
    user.add_argument("--email", required=True)
    user.add_argument("--role", choices=["reception", "doctor"], required=True)
    user.add_argument("--doctor-id", help="required for doctor accounts, e.g. dr-sharma")

    commands.add_parser("send-reminders", help="email confirmed appointments that start within 24 hours")
    commands.add_parser("cleanup", help="delete expired appointments and chat sessions")

    args = parser.parse_args(argv)
    app = create_app()
    with app.app_context():
        if args.command == "init-db":
            print(f"Database ready at {app.config['DATABASE']}.")
        elif args.command == "create-user":
            _create_user(app, args.email, args.role, args.doctor_id)
        elif args.command == "send-reminders":
            sent = send_reminders(app.config, app.extensions["clinic"])
            print(f"Reminders sent: {sent}.")
        elif args.command == "cleanup":
            clinic = app.extensions["clinic"]
            removed = clinic.purge_expired()
            sessions = app.extensions["store"].purge_sessions(app.config["SESSION_RETENTION_HOURS"])
            print(f"Removed {removed} expired appointments and {sessions} chat sessions.")


if __name__ == "__main__":
    main()