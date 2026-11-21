"""Field-level encryption for personal and health data, and keyed hashes for lookups.

Names, contact details, reasons for visit and medical intake answers are stored
encrypted (Fernet = AES-128-CBC + HMAC-SHA256). Contact details also get a keyed
hash so a patient can be matched without decrypting every row.
"""
import hashlib
import hmac
import json
import logging
import re
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)


class Vault:
    def __init__(self, key):
        key = key.encode("ascii") if isinstance(key, str) else key
        self._fernet = Fernet(key)
        # A separate key for lookups, derived so the two never share key material.
        self._lookup_key = hashlib.sha256(b"lookup:" + key).digest()

    @classmethod
    def from_config(cls, config):
        key = config["ENCRYPTION_KEY"]
        if not key:
            if config["APP_ENV"] == "production":
                raise RuntimeError("CLINIC_ENCRYPTION_KEY is required in production.")
            path = Path(config["INSTANCE_DIR"]) / "dev-encryption.key"
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(Fernet.generate_key())
            key = path.read_text(encoding="ascii").strip()
            log.warning("CLINIC_ENCRYPTION_KEY not set; using development key at %s", path)
        return cls(key)

    def seal(self, text):
        return self._fernet.encrypt((text or "").encode("utf-8")).decode("ascii")

    def open(self, token):
        if not token:
            return ""
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken:
            log.error("A stored value could not be decrypted; check the encryption key.")
            return ""

    def seal_json(self, value):
        return self.seal(json.dumps(value, ensure_ascii=False))

    def open_json(self, token):
        raw = self.open(token)
        return json.loads(raw) if raw else None

    def lookup_hash(self, value):
        """Stable keyed hash of a contact detail, tolerant of case, spaces and dashes."""
        normalized = re.sub(r"[^a-z0-9@+.]", "", (value or "").lower())
        return hmac.new(self._lookup_key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()