"""The sole boundary between the UI and the six-function core.api contract.

Rendering never selects activities. This module normalizes presentation fields
and performs mutations on a copy so a rejected import cannot damage a session.
"""

from __future__ import annotations

import csv
import importlib
import io
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

REQUIRED_API = ("load_dataset", "import_test_data", "list_employees", "get_employee_view", "complete_activity", "get_hr_view")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class AdapterError(ValueError):
    """An actionable data/integration problem that the interface can display."""


def _rows(value, id_field):
    if isinstance(value, dict):
        return [dict(v, **{id_field: k}) if isinstance(v, dict) else {id_field: k, "current": v} for k, v in value.items()]
    return list(value or [])


def _text(value):
    if isinstance(value, dict):
        return str(value.get("text") or value.get("explanation") or value.get("reason") or "")
    return str(value or "")


def _explanation_fields(rec, view):
    """Display the engine's evidence; never ask a model or generate new reasons."""
    ai = rec.get("ai_explanation", rec.get("personal_explanation"))
    ai_meta = ai if isinstance(ai, dict) else {}
    global_ai = view.get("ai", {}) if isinstance(view.get("ai"), dict) else {}
    status = str(rec.get("ai_status", ai_meta.get("status", global_ai.get("status", "")))).lower()
    source = str(rec.get("explanation_source", ai_meta.get("source", ""))).lower()
    failed = status in {"timeout", "timed_out", "error", "failed", "fallback", "unavailable"}
    reasons = rec.get("reasons", [])
    fallback = _text(rec.get("deterministic_explanation") or rec.get("fallback_explanation"))
    # The current core returns verified personal reasons, not free LLM prose.
    # Quoting its first reason is presentation, not a second explanation engine.
    fallback = fallback or (_text(reasons[0]) if reasons else "")
    explanation = _text(rec.get("explanation"))
    ai_text = _text(ai)
    if failed:
        display = fallback or explanation
        display_source = "rules"
    elif ai_text or source in {"ai", "llm", "openai", "nvidia"}:
        display = ai_text or explanation
        display_source = "ai"
    else:
        display = explanation or fallback
        display_source = "demo" if source == "demo" else "rules"
    factors = rec.get("factors", [])
    if isinstance(factors, dict):
        factors = [{"label": key, "value": value} for key, value in factors.items()]
    texts = []
    labels = {"grade": "Грейд", "skill_gap": "Разрыв по навыкам", "history": "История участия", "role": "Роль", "prerequisites": "Требования"}
    for factor in factors:
        if isinstance(factor, dict):
            value = _text(factor.get("text") or factor.get("description") or factor.get("value"))
            label = factor.get("label", factor.get("name", factor.get("type", "")))
            label = labels.get(label, label)
            texts.append(f"{label}: {value}" if label and value else value)
        else:
            texts.append(str(factor))
    return {"display_explanation": display, "display_explanation_source": display_source,
            "display_factors": [s for s in texts if s], "ai_fallback": failed}


class CoreAdapter:
    def __init__(self, data_dir: str | Path, module=None):
        self.data_dir = Path(data_dir)
        if module is None:
            importlib.invalidate_caches()
            try:
                module = importlib.import_module("core.api")
            except ModuleNotFoundError as exc:
                if exc.name not in {"core", "core.api"}:
                    raise AdapterError(f"Для core/ не установлена зависимость: {exc.name}.") from exc
                raise AdapterError("Не найден core/api.py. Подтяните файлы движка и перезапустите приложение.") from exc
        missing = [name for name in REQUIRED_API if not callable(getattr(module, name, None))]
        if missing:
            raise AdapterError("В core.api отсутствуют функции: " + ", ".join(missing))
        self.api = module
        self.is_demo = module.__name__ == "ui.demo_adapter"
        self.backend_name = "demo" if self.is_demo else "core"
        try:
            payload = json.loads((self.data_dir / "skills.json").read_text(encoding="utf-8-sig"))
            self.catalog = {s["skill_id"]: s for s in payload["skills"]}
            self.role_profiles = payload["role_profiles"]
            self.as_of_date = payload.get("meta", {}).get("as_of_date", "2026-10-01")
            event_payload = json.loads((self.data_dir / "events.json").read_text(encoding="utf-8-sig"))
            self.events = {e["event_id"]: e for e in event_payload["events"]}
        except (OSError, ValueError, KeyError) as exc:
            raise AdapterError(f"Не удалось прочитать каталог из {self.data_dir}: {exc}") from exc

    def skill_name(self, skill_id):
        return self.catalog.get(skill_id, {}).get("name") or str(skill_id).removeprefix("SK_").replace("_", " ").title()

    def load_dataset(self):
        return self.api.load_dataset(str(self.data_dir))

    @property
    def growth(self):
        if not hasattr(self, "_growth"):
            from core.growth import GrowthService
            self._growth = GrowthService()
        return self._growth

    def list_employees(self, dataset):
        return [dict(row, full_name=row.get("full_name", row.get("name", row["employee_id"])))
                for row in self.api.list_employees(dataset)]

    def get_employee_view(self, dataset, employee_id):
        managed = getattr(self, "managed_ai", False) and self.api.__name__ == "core.api"
        view = deepcopy(self.growth.baseline_view(dataset, employee_id) if managed else self.api.get_employee_view(dataset, employee_id))
        employee = view["employee"]
        employee["full_name"] = employee.get("full_name", employee.get("name", employee_id))
        view["ai_status"] = "Предпросмотр UI" if self.is_demo else "Детерминированный расчёт"
        if managed:
            view["ai_status"] = "Расчёт core · AI-треки и поиск запускаются отдельно по кнопке"
        elif not self.is_demo and self.api.__name__ == "core.api":
            try:
                view["ai_status"] = importlib.import_module("core.ai").LAST_STATUS.get()
            except (ImportError, AttributeError):
                pass
        status = view["ai_status"]
        view.setdefault("ai", {"status": "fallback" if status.startswith("Fallback") else "ok" if status.startswith("AI ·") else "disabled", "description": status})
        next_value = view.get("next_grade")
        target = next_value if isinstance(next_value, dict) else {}
        view["next_grade"] = target.get("grade", target.get("target_grade")) if target else next_value
        view["target_role"] = target.get("role", employee.get("role", ""))
        role_profile = next((p for p in self.role_profiles if p["role"] == view["target_role"]
                             and p["grade"] == (view["next_grade"] or employee.get("grade"))), {})
        critical_ids = set(role_profile.get("critical_skills", []))
        skills = []
        for item in _rows(view.get("skills"), "skill_id"):
            sid = item["skill_id"]
            current = item.get("current", item.get("current_level", item.get("level", 0)))
            required = item.get("required", item.get("required_level", item.get("target_level", 0)))
            skills.append({**item, "name": item.get("name") or item.get("label") or self.skill_name(sid), "current": current,
                           "required": required, "gap": max(0, required - current),
                           "critical": bool(item.get("critical", item.get("is_critical", sid in critical_ids))),
                           "type": item.get("type", self.catalog.get(sid, {}).get("type", "hard"))})
        view["skills"] = sorted(skills, key=lambda s: (s["gap"] <= 0, not s["critical"], -s["gap"], s["name"]))
        total_required = sum(s["required"] for s in skills)
        readiness = round(100 * sum(min(s["current"], s["required"]) for s in skills) / total_required) if total_required else 100
        trajectory = view.get("trajectory") or {}
        if not isinstance(trajectory, dict):
            trajectory = {"steps": trajectory}
        trajectory.setdefault("progress_pct", trajectory.get("progress_percent", readiness))
        trajectory.setdefault("gap_count", sum(s["gap"] > 0 for s in skills))
        view["trajectory"] = trajectory
        recommendations = []
        for raw in view.get("recommendations", [])[:3]:
            rec = {**self.events.get(raw["event_id"], {}), **raw}
            reasons = rec.get("reasons", [])
            if isinstance(reasons, dict):
                reasons = list(reasons.values())
            if isinstance(reasons, str):
                reasons = [reasons]
            rec["reasons"] = [str(r.get("text", r.get("reason", r))) if isinstance(r, dict) else str(r) for r in reasons]
            changes = []
            for change in _rows(rec.get("skill_changes"), "skill_id"):
                sid = change["skill_id"]
                before = change.get("before", change.get("current", employee.get("skills", {}).get(sid, 0)))
                after = change.get("after", change.get("expected_level", before + change.get("gain", 0)))
                changes.append({**change, "name": change.get("name") or change.get("label") or self.skill_name(sid),
                                "before": before, "after": after, "gain": after - before})
            rec["skill_changes"] = changes
            rec.update(_explanation_fields(rec, view))
            recommendations.append(rec)
        view["recommendations"] = recommendations
        view.setdefault("history", [])
        for row in view["history"]:
            row.setdefault("title", self.events.get(row.get("event_id"), {}).get("title", row.get("event_id", "Активность")))
        return view

    @staticmethod
    def _mutation_dataset(candidate, result):
        if isinstance(result, dict) and isinstance(result.get("dataset"), dict):
            return result["dataset"]
        if isinstance(result, dict) and "employees" in result and "employee" not in result:
            return result
        # Contract implementations may mutate in place and return an action result.
        return candidate

    def complete_activity(self, dataset, employee_id, event_id):
        candidate = deepcopy(dataset)
        if getattr(self, 'managed_ai', False) and self.api.__name__ == 'core.api':
            self.growth.preserve_baseline_before_simulation(candidate, employee_id)
        result = self.api.complete_activity(candidate, employee_id, event_id)
        updated = self._mutation_dataset(candidate, result)
        # Required re-query, also validates the candidate before it enters session state.
        view = self.get_employee_view(updated, employee_id)
        return updated, view

    def import_test_data(self, dataset, employees_bytes=None, history_bytes=None):
        if not employees_bytes and not history_bytes:
            raise AdapterError("Выберите файл сотрудников JSON и/или файл истории CSV.")
        for content in (employees_bytes, history_bytes):
            if content and len(content) > MAX_UPLOAD_BYTES:
                raise AdapterError("Размер каждого файла должен быть не больше 10 МБ.")
        try:
            if employees_bytes:
                payload = json.loads(employees_bytes.decode("utf-8-sig"))
                rows = payload.get("employees") if isinstance(payload, dict) else payload
                if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
                    raise AdapterError('JSON должен содержать непустой массив сотрудников: {"employees": [...]} или [...].')
                if isinstance(payload, list):
                    employees_bytes = json.dumps({"employees": rows}, ensure_ascii=False).encode("utf-8")
            if history_bytes:
                reader = csv.DictReader(io.StringIO(history_bytes.decode("utf-8-sig")))
                required = {"record_id", "employee_id", "event_id", "date", "status", "completion_pct"}
                if not required.issubset(reader.fieldnames or []):
                    raise AdapterError("В CSV истории отсутствуют столбцы: " + ", ".join(sorted(required - set(reader.fieldnames or []))))
                if not list(reader):
                    raise AdapterError("CSV истории не содержит записей.")
        except (UnicodeDecodeError, json.JSONDecodeError, csv.Error) as exc:
            raise AdapterError("Не удалось прочитать файл. Нужны JSON/CSV в кодировке UTF-8 из стартового кита.") from exc
        candidate = deepcopy(dataset)
        with TemporaryDirectory(prefix="career-quest-import-") as directory:
            files = []
            for name, content in (("employees.json", employees_bytes), ("activity_history.csv", history_bytes)):
                path = Path(directory) / name
                if content:
                    path.write_bytes(content)
                files.append(str(path) if content else None)
            result = self.api.import_test_data(candidate, employees_file=files[0], history_file=files[1])
        updated = self._mutation_dataset(candidate, result)
        self.list_employees(updated)
        return updated

    def get_hr_view(self, dataset):
        result = deepcopy(self.api.get_hr_view(dataset))
        for row in result.get("skill_gaps", []):
            row.setdefault("name", row.get("label") or self.skill_name(row.get("skill_id", "")))
        blocked = result.get("employees_without_next_step", result.get("employees_without_recommendations", []))
        result["employees_without_next_step"] = [dict(row, full_name=row.get("full_name", row.get("name", row.get("employee_id", "")))) for row in blocked]
        rows = result.get("participation", result.get("activity_participation", []))
        result["participation"] = [dict(row, records=row.get("records", row.get("participations", 0))) for row in rows]
        return result
