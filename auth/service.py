"""Local account storage; no event journal, passwords, or session tokens in logs.

The UI must use ``current_user(token)`` for the authoritative role on every rerun.
``create_admin`` and ``assign_role`` are trusted server-side provisioning methods;
never expose them as public registration options. Public signup is employee-only.

Password parameters follow the OWASP scrypt recommendation (N=2**17, r=8, p=1):
https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
This local prototype does not verify email ownership or provide SSO/MFA.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROLES = frozenset({"employee", "hr", "admin"})
PASSWORD_MIN_LENGTH = 15
PASSWORD_MAX_LENGTH = 128
SESSION_MAX_AGE = 8 * 60 * 60
SESSION_IDLE_TIMEOUT = 30 * 60
LOGIN_WINDOW = 15 * 60
LOGIN_MAX_FAILURES = 5
SCRYPT_N = 2**17
SCRYPT_R = 8
SCRYPT_P = 1
_SCRYPT_SLOTS = threading.BoundedSemaphore(1)
_DUMMY_SALT = secrets.token_bytes(32)
_DUMMY_EXPECTED = secrets.token_bytes(64)
_LOGIN_ERROR = (
    "Не удалось войти. Проверьте почту, пароль и выбранную роль. "
    "После нескольких неудачных попыток подождите 15 минут."
)
_STORAGE_ERROR = "Хранилище учётных записей недоступно. Повторите попытку позже."
_HASH_ERROR = "Не удалось обработать пароль. Повторите попытку позже."


class AuthError(ValueError):
    """An actionable, safe error message suitable for displaying in the UI."""


def _normalize_email(value: str) -> str:
    if not isinstance(value, str) or len(value) > 320:
        raise AuthError("Укажите корректную электронную почту, например name@company.kz.")
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    if value.count("@") != 1 or any(c.isspace() or unicodedata.category(c)[0] == "C" for c in value):
        raise AuthError("Укажите корректную электронную почту, например name@company.kz.")
    local, domain = value.rsplit("@", 1)
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        raise AuthError("Проверьте домен электронной почты.") from None
    if (
        not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}", local)
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or "." not in domain
        or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in domain.split("."))
        or len(local + "@" + domain) > 254
    ):
        raise AuthError("Укажите корректную электронную почту, например name@company.kz.")
    return local + "@" + domain


def _validate_registration(name: str, email: str, password: str, confirmation: str) -> tuple[str, str]:
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 120:
        raise AuthError("Укажите имя длиной от 2 до 120 символов.")
    if any(unicodedata.category(c)[0] == "C" for c in name):
        raise AuthError("Имя не должно содержать управляющие символы.")
    name = " ".join(name.split())
    if len(name) < 2:
        raise AuthError("Укажите имя длиной от 2 до 120 символов.")
    email = _normalize_email(email)
    if not isinstance(password, str) or not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise AuthError("Пароль должен содержать от 15 до 128 символов. Можно использовать фразу с пробелами.")
    try:
        password.encode("utf-8")
    except UnicodeError:
        raise AuthError("Пароль содержит неподдерживаемые символы.") from None
    if not isinstance(confirmation, str) or password != confirmation:
        raise AuthError("Пароли не совпадают. Повторите пароль ещё раз.")
    return name, email


def _derive_key(password: str, salt: bytes) -> bytes:
    # Bound memory-heavy work within one server process (~128 MiB per hash).
    with _SCRYPT_SLOTS:
        try:
            return hashlib.scrypt(
                password.encode("utf-8"), salt=salt,
                n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                maxmem=256 * 1024 * 1024, dklen=64,
            )
        except (ValueError, MemoryError, OSError):
            raise AuthError(_HASH_ERROR) from None


def _safe_user(row: sqlite3.Row) -> dict:
    return {
        "user_id": row["user_id"], "name": row["name"], "email": row["email"],
        "role": row["role"], "active": bool(row["active"]),
    }


def _token_digest(token: str) -> bytes | None:
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    return hashlib.sha256(token.encode("ascii")).digest()


class AuthService:
    """SQLite-backed credentials and expiring, opaque server-side sessions.

    ``db_path`` overrides CAREER_QUEST_AUTH_DB. By default the database is
    ``auth/.local/auth.sqlite3`` relative to this module, not the current cwd.
    No profile ID or HR permissions are inferred from a person's name/email.
    """

    def __init__(self, db_path: str | Path | None = None):
        configured = db_path if db_path is not None else os.environ.get("CAREER_QUEST_AUTH_DB")
        self.db_path = Path(configured or Path(__file__).parent / ".local" / "auth.sqlite3").expanduser().resolve()
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS auth_users (
                        user_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE,
                        password_salt BLOB NOT NULL,
                        password_hash BLOB NOT NULL,
                        password_version INTEGER NOT NULL DEFAULT 1,
                        role TEXT NOT NULL CHECK (role IN ('employee', 'hr', 'admin')),
                        active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                        created_at REAL NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS auth_sessions (
                        token_hash BLOB PRIMARY KEY,
                        user_id TEXT NOT NULL REFERENCES auth_users(user_id) ON DELETE CASCADE,
                        created_at REAL NOT NULL,
                        last_seen REAL NOT NULL,
                        expires_at REAL NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS auth_sessions_user ON auth_sessions(user_id);
                    CREATE TABLE IF NOT EXISTS auth_login_limits (
                        identifier_hash BLOB PRIMARY KEY,
                        failures INTEGER NOT NULL,
                        window_started REAL NOT NULL,
                        locked_until REAL NOT NULL DEFAULT 0
                    );
                """)
            # Restrict the file on POSIX. Windows deployment uses directory ACLs.
            if os.name != "nt":
                self.db_path.chmod(0o600)
        except OSError:
            raise AuthError(_STORAGE_ERROR) from None

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        except sqlite3.Error:
            if conn is not None and conn.in_transaction:
                conn.rollback()
            raise AuthError(_STORAGE_ERROR) from None
        except BaseException:
            if conn is not None and conn.in_transaction:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()

    def register(self, name: str, email: str, password: str, password_confirmation: str) -> dict:
        """Create an employee account. There is intentionally no role argument."""
        return self._create_user(name, email, password, password_confirmation, "employee")

    def create_admin(self, name: str, email: str, password: str, password_confirmation: str) -> dict:
        """Trusted server CLI only: create the first admin; refuse a second bootstrap."""
        return self._create_user(name, email, password, password_confirmation, "admin", first_admin=True)

    def _create_user(self, name: str, email: str, password: str, confirmation: str, role: str, first_admin: bool = False) -> dict:
        name, email = _validate_registration(name, email, password, confirmation)
        salt = secrets.token_bytes(32)
        derived = _derive_key(password, salt)
        user_id = str(uuid.uuid4())
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if first_admin and conn.execute("SELECT 1 FROM auth_users WHERE role='admin' LIMIT 1").fetchone():
                raise AuthError("Администратор уже создан. Для изменения ролей используйте команду set-role на сервере.")
            try:
                conn.execute(
                    "INSERT INTO auth_users(user_id,name,email,password_salt,password_hash,role,created_at) VALUES(?,?,?,?,?,?,?)",
                    (user_id, name, email, salt, derived, role, time.time()),
                )
            except sqlite3.IntegrityError:
                raise AuthError("Не удалось создать аккаунт с этой почтой. Если вы уже зарегистрированы, войдите.") from None
            row = conn.execute("SELECT * FROM auth_users WHERE user_id=?", (user_id,)).fetchone()
            conn.commit()
        return _safe_user(row)

    def login(self, email: str, password: str, expected_role: str = "employee") -> tuple[str, dict]:
        """Authenticate the selected role against the stored role, never grant it."""
        try:
            normalized = _normalize_email(email)
            valid_email = True
        except AuthError:
            normalized = str(email)[:320].strip().casefold()
            valid_email = False
        identifier = hashlib.sha256(normalized.encode("utf-8", errors="replace")).digest()
        with self._connection() as conn:
            # A known cooldown must not occupy the shared expensive hashing slot.
            # The transaction below checks again to handle concurrent attempts.
            limit = conn.execute(
                "SELECT locked_until FROM auth_login_limits WHERE identifier_hash=?", (identifier,),
            ).fetchone()
            if limit and limit["locked_until"] > time.time():
                raise AuthError(_LOGIN_ERROR)
            row = conn.execute("SELECT * FROM auth_users WHERE email=?", (normalized,)).fetchone() if valid_email else None
        # Non-blocked unknown, inactive and malformed attempts still do one hash.
        valid_password = isinstance(password, str) and 1 <= len(password) <= PASSWORD_MAX_LENGTH
        try:
            candidate = password if valid_password else "invalid-password-input"
            candidate.encode("utf-8")
        except UnicodeError:
            candidate, valid_password = "invalid-password-input", False
        actual_hash = _derive_key(candidate, bytes(row["password_salt"]) if row else _DUMMY_SALT)
        matches = hmac.compare_digest(actual_hash, bytes(row["password_hash"]) if row else _DUMMY_EXPECTED)
        authenticated = False
        now = time.time()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # Retain counters only while they affect authentication; this is not an event log.
            conn.execute("DELETE FROM auth_login_limits WHERE locked_until<=? AND window_started<=?", (now, now - LOGIN_WINDOW))
            limit = conn.execute("SELECT * FROM auth_login_limits WHERE identifier_hash=?", (identifier,)).fetchone()
            locked = bool(limit and limit["locked_until"] > now)
            latest = conn.execute("SELECT * FROM auth_users WHERE user_id=?", (row["user_id"],)).fetchone() if row else None
            authenticated = bool(
                not locked and valid_email and valid_password and matches and latest
                and latest["active"] and latest["role"] == expected_role and expected_role in ROLES
                and latest["password_version"] == 1
                and hmac.compare_digest(bytes(row["password_hash"]), bytes(latest["password_hash"]))
            )
            if authenticated:
                conn.execute("DELETE FROM auth_login_limits WHERE identifier_hash=?", (identifier,))
                self._prune_sessions(conn, now)
                token = secrets.token_urlsafe(32)
                conn.execute(
                    "INSERT INTO auth_sessions(token_hash,user_id,created_at,last_seen,expires_at) VALUES(?,?,?,?,?)",
                    (_token_digest(token), latest["user_id"], now, now, now + SESSION_MAX_AGE),
                )
                user = _safe_user(latest)
            elif not locked:
                failures = (int(limit["failures"]) if limit else 0) + 1
                started = float(limit["window_started"]) if limit else now
                until = now + LOGIN_WINDOW if failures >= LOGIN_MAX_FAILURES else 0
                conn.execute(
                    "INSERT INTO auth_login_limits(identifier_hash,failures,window_started,locked_until) VALUES(?,?,?,?) "
                    "ON CONFLICT(identifier_hash) DO UPDATE SET failures=excluded.failures,window_started=excluded.window_started,locked_until=excluded.locked_until",
                    (identifier, failures, started, until),
                )
            conn.commit()
        if not authenticated:
            raise AuthError(_LOGIN_ERROR)
        return token, user

    @staticmethod
    def _prune_sessions(conn: sqlite3.Connection, now: float) -> None:
        conn.execute("DELETE FROM auth_sessions WHERE expires_at<=? OR last_seen<=?", (now, now - SESSION_IDLE_TIMEOUT))

    def current_user(self, token: str) -> dict | None:
        """Validate expiry, idle timeout and current account role; refresh last_seen."""
        digest = _token_digest(token)
        if digest is None:
            return None
        now = time.time()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._prune_sessions(conn, now)
            row = conn.execute(
                "SELECT u.* FROM auth_sessions s JOIN auth_users u ON s.user_id=u.user_id WHERE s.token_hash=?",
                (digest,),
            ).fetchone()
            if row and row["active"]:
                conn.execute("UPDATE auth_sessions SET last_seen=? WHERE token_hash=?", (now, digest))
                result = _safe_user(row)
            else:
                conn.execute("DELETE FROM auth_sessions WHERE token_hash=?", (digest,))
                result = None
            conn.commit()
        return result

    def logout(self, token: str) -> None:
        """Idempotently revoke one session; a copied token stops working as well."""
        digest = _token_digest(token)
        if digest is not None:
            with self._connection() as conn:
                conn.execute("DELETE FROM auth_sessions WHERE token_hash=?", (digest,))

    def assign_role(self, email: str, role: str) -> dict:
        """Trusted server CLI only; role changes revoke all sessions for that user."""
        email = _normalize_email(email)
        if role not in ROLES:
            raise AuthError("Допустимые роли: employee, hr, admin.")
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM auth_users WHERE email=?", (email,)).fetchone()
            if row is None:
                raise AuthError("Аккаунт с этой почтой не найден. Сначала зарегистрируйте сотрудника.")
            if row["role"] == "admin" and row["active"] and role != "admin":
                admins = conn.execute("SELECT COUNT(*) FROM auth_users WHERE role='admin' AND active=1").fetchone()[0]
                if admins <= 1:
                    raise AuthError("Нельзя понизить роль последнего активного администратора.")
            conn.execute("UPDATE auth_users SET role=? WHERE user_id=?", (role, row["user_id"]))
            conn.execute("DELETE FROM auth_sessions WHERE user_id=?", (row["user_id"],))
            updated = conn.execute("SELECT * FROM auth_users WHERE user_id=?", (row["user_id"],)).fetchone()
            conn.commit()
        return _safe_user(updated)
