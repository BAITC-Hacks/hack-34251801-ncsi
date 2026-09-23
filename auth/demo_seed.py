"""Explicit, local-only demo provisioning; never run by the login page.

These credentials are public demonstration fixtures, not application secrets.
The command does not replace existing accounts, passwords or profile links.
"""

import secrets
import sqlite3
import time
import uuid

from auth.service import AuthError, _derive_key, _safe_user

DEMO_PASSWORD = 'CareerQuest2026!'
DEMO_ACCOUNTS = (
    {'slot': 'admin', 'email': 'admin@careerquest.test', 'role': 'admin', 'employee_id': None, 'name': 'Демо администратор'},
    {'slot': 'hr', 'email': 'hr@careerquest.test', 'role': 'hr', 'employee_id': None, 'name': 'Демо HR'},
    {'slot': 'employee1', 'email': 'employee1@careerquest.test', 'role': 'employee', 'employee_id': 'E0001', 'name': 'Демо сотрудник 1'},
    {'slot': 'employee2', 'email': 'employee2@careerquest.test', 'role': 'employee', 'employee_id': 'E0002', 'name': 'Демо сотрудник 2'},
)


def seed_demo_accounts(service, employees):
    """Create all missing fixtures atomically, keeping previously seeded users.

    Only the trusted local CLI calls this function. A marker distinguishes our
    fixture accounts from an existing user's coincidentally matching address.
    BEGIN IMMEDIATE serializes parallel calls and rolls back the whole batch
    on a conflicting address, occupied profile or unavailable starter profile.
    """
    employee_ids = {row['employee_id'] for row in employees}
    with service._connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''CREATE TABLE IF NOT EXISTS auth_demo_accounts (
            slot TEXT PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE REFERENCES auth_users(user_id) ON DELETE CASCADE
        )''')
        existing, pending = [], []
        for spec in DEMO_ACCOUNTS:
            row = conn.execute('''SELECT u.* FROM auth_demo_accounts d
                JOIN auth_users u ON u.user_id=d.user_id WHERE d.slot=?''', (spec['slot'],)).fetchone()
            if row:
                existing.append(_safe_user(row))
                continue
            if conn.execute('SELECT 1 FROM auth_users WHERE email=?', (spec['email'],)).fetchone():
                raise AuthError(f"Аккаунт {spec['email']} уже существует и не создан этой командой. Данные не изменены; для показа используйте отдельную папку базы.")
            profile = spec['employee_id']
            if profile:
                if profile not in employee_ids:
                    raise AuthError(f'В базе профилей нет {profile}. Для демо нужен стартовый набор с E0001 и E0002.')
                if conn.execute('SELECT 1 FROM auth_users WHERE employee_id=?', (profile,)).fetchone():
                    raise AuthError(f'Профиль {profile} уже привязан к другому аккаунту. Данные не изменены; для показа используйте отдельную папку базы.')
            pending.append(spec)
        created = []
        for spec in pending:
            salt = secrets.token_bytes(32)
            password_hash = _derive_key(DEMO_PASSWORD, salt)
            user_id = str(uuid.uuid4())
            try:
                conn.execute('''INSERT INTO auth_users
                    (user_id,name,email,password_salt,password_hash,role,employee_id,created_at)
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (user_id, spec['name'], spec['email'], salt, password_hash,
                     spec['role'], spec['employee_id'], time.time()))
                conn.execute('INSERT INTO auth_demo_accounts(slot,user_id) VALUES (?,?)', (spec['slot'], user_id))
            except sqlite3.IntegrityError:
                raise AuthError('Не удалось создать демонстрационные аккаунты: конфликт данных. Изменения отменены.') from None
            created.append(_safe_user(conn.execute('SELECT * FROM auth_users WHERE user_id=?', (user_id,)).fetchone()))
        conn.commit()
    return {'created': created, 'existing': existing}
