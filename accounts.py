"""Staff password handling: changing a password and forcing a new one on first sign-in."""
from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 12


def ensure_schema(store):
    """Adds the must_change_password column to databases created before this feature."""
    columns = [row["name"] for row in store._query("PRAGMA table_info(users)")]
    if "must_change_password" not in columns:
        store._write("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")


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
