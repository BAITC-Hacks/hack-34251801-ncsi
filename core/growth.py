"""Persistent HR workflow. Extends the existing engine without changing its files."""

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from . import engine

TRAITS = {"resilience": "Стрессоустойчивость", "communication": "Коммуникация",
          "initiative": "Инициативность", "analysis": "Аналитика",
          "discipline": "Самоорганизация", "teamwork": "Командная работа"}
ROOT = Path(__file__).resolve().parents[1]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def text(value, label, limit=300, required=True):
    value = str(value or "").strip()
    if (required and not value) or len(value) > limit:
        raise ValueError(f"{label}: заполните поле, не более {limit} символов.")
    return value


def public_url(value, required=True):
    value = text(value, "Ссылка", 1500, required)
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Нужна публичная ссылка https:// без логина и пароля.")
    import ipaddress
    host = parsed.hostname.lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Используйте доменное имя учебного провайдера, не IP-адрес.")
    if "." not in host or host.endswith((".local", ".localhost", ".internal")):
        raise ValueError("Используйте публичный домен учебного провайдера.")
    return urlunsplit(("https", parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


class GrowthStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("CAREER_QUEST_GROWTH_DB", ROOT / ".career-quest/growth.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    employee_id TEXT PRIMARY KEY, hire_date TEXT NOT NULL,
                    traits TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS certificates (
                    id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, fingerprint TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                    awards TEXT NOT NULL DEFAULT '{}', reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, reviewed_at TEXT);
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS training_requests (
                    id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, url TEXT NOT NULL,
                    payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                    reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, reviewed_at TEXT,
                    UNIQUE(employee_id, url));
                CREATE TABLE IF NOT EXISTS ai_calls (
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, model TEXT NOT NULL,
                    status TEXT NOT NULL, reserved INTEGER NOT NULL, charged INTEGER NOT NULL DEFAULT 0,
                    usage TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS cert_employee ON certificates(employee_id);
                CREATE INDEX IF NOT EXISTS plan_employee ON plans(employee_id);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def rows(self, table, employee_id=None):
        if table not in {"certificates", "training_requests", "plans"}:
            raise ValueError("Неизвестная коллекция.")
        sql = f"SELECT * FROM {table}" + (" WHERE employee_id=?" if employee_id else "") + " ORDER BY created_at DESC, id"
        with self.connection() as db:
            rows = [dict(row) for row in db.execute(sql, (employee_id,) if employee_id else ())]
        for row in rows:
            row["payload"] = json.loads(row["payload"])
            if "awards" in row:
                row["awards"] = json.loads(row["awards"])
        return rows


class GrowthService:
    def __init__(self, store=None):
        self.store = store or GrowthStore()

    @staticmethod
    def _hr(actor):
        if actor != "hr":
            raise PermissionError("Это действие доступно HR.")

    def profile(self, dataset, employee_id):
        employee = engine.employee(dataset, employee_id)
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM profiles WHERE employee_id=?", (employee_id,)).fetchone()
        return ({**dict(row), "traits": json.loads(row["traits"]), "assessed": True} if row else
                {"employee_id": employee_id, "hire_date": employee["hire_date"], "traits": {}, "assessed": False})

    def save_profile(self, dataset, employee_id, hire_date, traits, actor="employee"):
        self._hr(actor)
        engine.employee(dataset, employee_id)
        started = date.fromisoformat(str(hire_date))
        if not date(1960, 1, 1) <= started <= date(date.today().year + 1, 12, 31):
            raise ValueError("Проверьте дату выхода сотрудника.")
        if set(traits) != set(TRAITS) or any(type(v) is not int or not 0 <= v <= 5 for v in traits.values()):
            raise ValueError("Задайте все шесть характеристик целыми числами от 0 до 5.")
        with self.store.connection() as db:
            db.execute("INSERT INTO profiles VALUES (?,?,?,?) ON CONFLICT(employee_id) DO UPDATE SET hire_date=excluded.hire_date, traits=excluded.traits, updated_at=excluded.updated_at",
                       (employee_id, started.isoformat(), dump(traits), now_iso()))

    def submit_certificate(self, dataset, employee_id, title, provider, course_url, completed_on,
                           evidence, skill_ids, tags=""):
        engine.employee(dataset, employee_id)
        completed = date.fromisoformat(str(completed_on))
        if completed > date.today() or completed < date(1960, 1, 1):
            raise ValueError("Дата завершения должна быть в прошлом или сегодня.")
        if not isinstance(skill_ids, list) or set(skill_ids) - {s['skill_id'] for s in dataset['skills']}:
            raise ValueError("Выберите навыки из каталога.")
        payload = {"title": text(title, "Курс", 160), "provider": text(provider, "Провайдер", 100),
                   "url": public_url(course_url), "completed_on": completed.isoformat(),
                   "evidence": text(evidence, "Ссылка или номер сертификата", 500),
                   "skill_ids": sorted(set(skill_ids)), "tags": text(tags, "Дополнительные навыки", 300, False)}
        # A certificate/course is credited once, even if it is submitted with a new date.
        fingerprint = hashlib.sha256(dump([employee_id, payload['url'].split('?')[0].rstrip('/').lower()]).encode()).hexdigest()
        cid = uuid4().hex
        try:
            with self.store.connection() as db:
                db.execute("INSERT INTO certificates(id,employee_id,fingerprint,payload,created_at) VALUES (?,?,?,?,?)",
                           (cid, employee_id, fingerprint, dump(payload), now_iso()))
        except sqlite3.IntegrityError:
            raise ValueError("Этот курс уже отправлен. Посмотрите статус в портфолио.") from None
        return cid

    def review_certificate(self, dataset, certificate_id, approve, awards=None, reason="", actor="employee"):
        self._hr(actor)
        reason = text(reason, "Комментарий HR", 500, required=not approve)
        awards = awards or {}
        if set(awards) - {s['skill_id'] for s in dataset['skills']} or any(type(v) is not int or not 0 <= v <= 1 for v in awards.values()):
            raise ValueError("HR может подтвердить прирост 0–1 для навыка из каталога.")
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM certificates WHERE id=?", (certificate_id,)).fetchone()
            if row is None or row['status'] != 'pending':
                raise ValueError("Заявка уже рассмотрена или не найдена.")
            engine.employee(dataset, row['employee_id'])
            db.execute("UPDATE certificates SET status=?, awards=?, reason=?, reviewed_at=? WHERE id=?",
                       ('approved' if approve else 'rejected', dump(awards if approve else {}), reason, now_iso(), certificate_id))

    def snapshot(self, dataset, employee_id, today=None):
        """Only approved achievements affect this growth profile and AI facts."""
        today = today or date.today()
        profile = self.profile(dataset, employee_id)
        certificates = self.store.rows('certificates', employee_id)
        approved = [c for c in certificates if c['status'] == 'approved']
        person = engine.employee(dataset, employee_id)
        # UI_ records are the old starter-kit simulation, not HR-approved certificates.
        baseline_history = [h for h in dataset['history'] if h['employee_id'] == employee_id and not h['record_id'].startswith('UI_')]
        levels = engine.current_levels(dataset, person, baseline_history)
        for certificate in approved:
            for sid, gain in certificate['awards'].items():
                levels[sid] = min(5, levels.get(sid, 0) + gain)
        candidate = deepcopy(dataset)
        employee = engine.employee(candidate, employee_id)
        employee['skills'] = levels
        employee['last_review_date'] = candidate['as_of_date']
        employee['hire_date'] = profile['hire_date']
        # Reuse the original engine for requirements, progress and fallback activities.
        view = engine.get_employee_view(candidate, employee_id, use_ai=False)
        days = max(0, (today - date.fromisoformat(profile['hire_date'])).days)
        xp = days * 10 + len(approved) * 100
        return {'profile': profile, 'certificates': certificates, 'view': view,
                'skills': levels, 'xp': xp, 'tenure_xp': days * 10, 'learning_xp': len(approved) * 100,
                'level': 1 + xp // 1000, 'level_xp': xp % 1000, 'next_level_xp': 1000,
                'requests': self.store.rows('training_requests', employee_id)}

    def facts(self, dataset, employee_id):
        snapshot = self.snapshot(dataset, employee_id)
        person = engine.employee(dataset, employee_id)
        labels = {s['skill_id']: s['name'] for s in dataset['skills']}
        skills = [{'ref': sid, 'name': labels[sid], 'level': value} for sid, value in sorted(snapshot['skills'].items()) if value > 0]
        certificates = [{'ref': c['id'], 'title': c['payload']['title'], 'provider': c['payload']['provider'],
                         'tags': c['payload']['tags'], 'skill_ids': c['payload']['skill_ids'], 'awards': c['awards']}
                        for c in snapshot['certificates'] if c['status'] == 'approved'][:25]
        return {'role': person['role'], 'grade': person['grade'], 'goal': person.get('career_goal'),
                'skills': skills, 'certificates': certificates,
                'traits': {TRAITS[k]: v for k, v in snapshot['profile']['traits'].items()}}

    def recommend(self, dataset, employee_id, generate=False):
        from .growth_ai import GrowthAdvisor
        return GrowthAdvisor(self.store).recommend(employee_id, self.facts(dataset, employee_id), generate)

    def request_training(self, dataset, employee_id, plan_id, track_index, course_index):
        engine.employee(dataset, employee_id)
        plans = self.store.rows('plans', employee_id)
        plan = next((p for p in plans if p['id'] == plan_id), None)
        if not plan:
            raise ValueError("План сотрудника не найден.")
        from .growth_ai import fingerprint
        if plan['fingerprint'] != fingerprint(self.facts(dataset, employee_id)):
            raise ValueError("Портфолио изменилось. Обновите треки перед заявкой.")
        try:
            track = plan['payload']['tracks'][track_index]
            course = track['courses'][course_index]
        except (IndexError, TypeError):
            raise ValueError("Курс не найден в плане.") from None
        payload = dict(course, track=track['title'], plan_id=plan_id)
        rid = uuid4().hex
        try:
            with self.store.connection() as db:
                db.execute("INSERT INTO training_requests(id,employee_id,url,payload,created_at) VALUES (?,?,?,?,?)",
                           (rid, employee_id, public_url(course['url']), dump(payload), now_iso()))
        except sqlite3.IntegrityError:
            raise ValueError("Заявка на этот курс уже существует.") from None
        return rid

    def decide_training(self, request_id, approve, reason, actor="employee"):
        self._hr(actor)
        reason = text(reason, "Решение HR", 500)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("UPDATE training_requests SET status=?, reason=?, reviewed_at=? WHERE id=? AND status='pending'",
                                 ('approved' if approve else 'rejected', reason, now_iso(), request_id)).rowcount
            if not changed:
                raise ValueError("Заявка уже рассмотрена или не найдена.")
