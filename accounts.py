"""Staff accounts: names, admin rights, creating accounts, password changes and resets."""
import re
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 12
MAX_NAME_LENGTH = 80
ROLES = ("reception", "doctor")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOCTOR_ID_RE = re.compile(r"^[a-z0-9-]{1,40}$")


def ensure_schema(store):
    """Adds columns that databases created before these features do not have."""
    columns = [row["name"] for row in store._query("PRAGMA table_info(users)")]
    if "must_change_password" not in columns:
        store._write("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
    if "name" not in columns:
        store._write("ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    if "is_admin" not in columns:
        store._write("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")


def clean_name(raw):
    """Returns the trimmed name, or None if it is empty or too long."""
    name = " ".join((raw or "").split())
    if not name or len(name) > MAX_NAME_LENGTH:
        return None
    return name


def set_display_name(store, user_id, raw_name):
    """Returns an error message, or None when the name was saved."""
    name = clean_name(raw_name)
    if name is None:
        return f"Enter a name of up to {MAX_NAME_LENGTH} characters."
    store._write("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
    store.audit(str(user_id), "display-name-set")
    return None


def password_problem(new_password, confirm):
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if new_password != confirm:
        return "The two passwords do not match."
    return None


def change_password(store, user, current_password, new_password):
    """Returns an error message, or None when the password was changed."""
    if not check_password_hash(user["password_hash"], current_password):
        return "The current password is not correct."
    if check_password_hash(user["password_hash"], new_password):
        return "Choose a password that is different from the current one."
    store._write(
        "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
        (generate_password_hash(new_password), user["id"]),
    )
    store.audit(user["email"], "password-changed")
    return None


def generate_temporary_password():
    return secrets.token_urlsafe(9)


def create_staff_account(store, email, role, doctor_id, name, actor):
    """Returns (temporary_password, None) on success or (None, error message)."""
    email = (email or "").strip().lower()
    doctor_id = (doctor_id or "").strip() or None
    name = clean_name(name)
    if not EMAIL_RE.match(email):
        return None, "Enter a valid email address."
    if name is None:
        return None, f"Enter a name of up to {MAX_NAME_LENGTH} characters."
    if role not in ROLES:
        return None, "Choose a valid role."
    if role == "doctor" and not (doctor_id and DOCTOR_ID_RE.match(doctor_id)):
        return None, "Doctor accounts need a doctor ID such as dr-fischer."
    if role == "reception":
        doctor_id = None
    if store.get_user_by_email(email) is not None:
        return None, "An account with this email already exists."
    temporary = generate_temporary_password()
    store._write(
        "INSERT INTO users (email, password_hash, role, doctor_id, name, must_change_password) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (email, generate_password_hash(temporary), role, doctor_id, name),
    )
    store.audit(actor, f"account-created:{email}")
    return temporary, None


def reset_temporary_password(store, user, actor):
    """Gives the account a new temporary password and requires a change at next sign-in."""
    temporary = generate_temporary_password()
    store._write(
        "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?",
        (generate_password_hash(temporary), user["id"]),
    )
    store.audit(actor, f"password-reset:{user['email']}")
    return temporary


def list_staff(store):
    return store._query(
        "SELECT id, email, role, doctor_id, name, active, must_change_password "
        "FROM users ORDER BY role, email"
    )
