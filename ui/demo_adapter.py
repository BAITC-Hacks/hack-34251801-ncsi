"""Temporary, deterministic UI preview. Replaced automatically by core.api.

This is deliberately not the production AI recommendation engine. It uses the
starter data so that empty states, arbitrary profiles and updates can be tested.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

GRADES = ["Junior", "Middle", "Senior", "Lead"]
SNAPSHOT_DATE = "2026-10-01"


def load_dataset(data_dir: str) -> dict:
    root = Path(data_dir)
    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8-sig"))
    skills = read("skills.json")
    with (root / "activity_history.csv").open(encoding="utf-8-sig", newline="") as handle:
        history = list(csv.DictReader(handle))
    return {
        "employees": read("employees.json")["employees"],
        "events": read("events.json")["events"],
        "skill_catalog": skills["skills"],
        "role_profiles": skills["role_profiles"],
        "history": history,
        "snapshot_date": SNAPSHOT_DATE,
    }


def list_employees(dataset: dict) -> list[dict]:
    return deepcopy(dataset["employees"])


def _employee(dataset, employee_id):
    return next(e for e in dataset["employees"] if e["employee_id"] == employee_id)


def get_employee_view(dataset: dict, employee_id: str) -> dict:
    employee = deepcopy(_employee(dataset, employee_id))
    events = {e["event_id"]: e for e in dataset["events"]}
    history = [dict(h, title=events[h["event_id"]]["title"]) for h in dataset["history"] if h["employee_id"] == employee_id]
    effective = employee["skills"].copy()
    for record in sorted(history, key=lambda r: r["date"]):
        if record["status"] == "completed" and employee["last_review_date"] < record["date"] <= SNAPSHOT_DATE:
            for change in events[record["event_id"]]["develops_skills"]:
                sid = change["skill_id"]
                old = effective.get(sid, 0)
                effective[sid] = max(old, min(5, change["max_level"], old + change["gain"]))
    employee["skills"] = effective
    grade_index = GRADES.index(employee["grade"])
    next_grade = GRADES[grade_index + 1] if grade_index < 3 else None
    profile = next((p for p in dataset["role_profiles"] if p["role"] == employee["role"] and p["grade"] == next_grade), {})
    required = profile.get("required_skills", {})
    names = {s["skill_id"]: s for s in dataset["skill_catalog"]}
    skills = [{"skill_id": sid, "name": names[sid]["name"], "type": names[sid]["type"],
               "current": effective.get(sid, 0), "required": level,
               "gap": max(0, level - effective.get(sid, 0)),
               "critical": sid in profile.get("critical_skills", [])}
              for sid, level in required.items()]
    completed = {h["event_id"] for h in history if h["status"] == "completed"}
    # A single explicit UI fixture, never a second ranking engine. Real profiles
    # receive their recommendations exclusively from core.api once it appears.
    recs = []
    if employee_id == "E0001" and "EV_005" not in completed:
        recs = [{**events["EV_005"], "score": 2, "skill_changes": [
            {"skill_id": "SK_SYSTEM_DESIGN", "name": "System Design", "before": 1, "after": 2, "gain": 1},
            {"skill_id": "SK_API_DESIGN", "name": "API Design", "before": 2, "after": 3, "gain": 1}],
            "reasons": ["Пример для Backend Engineer · Junior.", "Пример разрыва: System Design 1 → 2 и API Design 2 → 3.",
                        "Пример фактора истории: активность ещё не завершена."],
            "explanation": "Пример карточки: курс связывает проектирование API и основы архитектуры с требованиями Middle.",
            "explanation_source": "demo"}]
    total = sum(required.values())
    progress = round(100 * sum(min(s["current"], s["required"]) for s in skills) / total) if total else 100
    return {"employee": employee, "next_grade": next_grade, "skills": skills, "history": history,
            "recommendations": recs[:3], "trajectory": {"progress_pct": progress, "gap_count": sum(s["gap"] > 0 for s in skills)},
            "empty_reason": "Достигнут верхний грейд роли." if not next_grade else
                            "Для этого профиля временный адаптер не подбирает активности. Рекомендации появятся после подключения core/."}


def complete_activity(dataset: dict, employee_id: str, event_id: str) -> dict:
    view = get_employee_view(dataset, employee_id)
    if event_id not in {r["event_id"] for r in view["recommendations"]}:
        raise ValueError("Активность уже завершена или больше не доступна для этого сотрудника.")
    dataset["history"].append({"record_id": f"UI_DEMO_{len(dataset['history']) + 1}", "employee_id": employee_id,
                               "event_id": event_id, "date": SNAPSHOT_DATE, "due_date": "", "status": "completed",
                               "completion_pct": 100, "score": "", "feedback_rating": "", "assigned_by": "self"})
    return dataset


def import_test_data(dataset: dict, employees_file=None, history_file=None) -> dict:
    incoming = []
    if employees_file:
        payload = json.loads(Path(employees_file).read_text(encoding="utf-8-sig"))
        incoming = payload["employees"] if isinstance(payload, dict) else payload
    existing = {e["employee_id"] for e in dataset["employees"]}
    known_skills = {s["skill_id"] for s in dataset["skill_catalog"]}
    profiles = {(p["role"], p["grade"]) for p in dataset["role_profiles"]}
    for employee in incoming:
        if not isinstance(employee, dict) or not all(k in employee for k in ("employee_id", "full_name", "role", "grade", "skills", "last_review_date")):
            raise ValueError("Профиль должен содержать employee_id, full_name, role, grade, skills и last_review_date.")
        if employee["employee_id"] in existing:
            raise ValueError(f"Сотрудник {employee['employee_id']} уже существует.")
        if (employee["role"], employee["grade"]) not in profiles:
            raise ValueError("Роль или грейд отсутствует в каталоге.")
        if not isinstance(employee["skills"], dict) or any(s not in known_skills or not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= 5 for s, v in employee["skills"].items()):
            raise ValueError("Навыки должны соответствовать каталогу, уровни — числам от 0 до 5.")
        existing.add(employee["employee_id"])
    records = []
    if history_file:
        with Path(history_file).open(encoding="utf-8-sig", newline="") as handle:
            records = list(csv.DictReader(handle))
        event_ids = {e["event_id"] for e in dataset["events"]}
        record_ids = {h["record_id"] for h in dataset["history"]}
        for record in records:
            if record["employee_id"] not in existing or record["event_id"] not in event_ids:
                raise ValueError("История ссылается на неизвестного сотрудника или активность.")
            if record["record_id"] in record_ids:
                raise ValueError(f"Запись истории {record['record_id']} уже существует.")
            record_ids.add(record["record_id"])
    dataset["employees"].extend(deepcopy(incoming))
    dataset["history"].extend(records)
    return dataset


def get_hr_view(dataset: dict) -> dict:
    gaps, blocked = Counter(), []
    for employee in dataset["employees"]:
        view = get_employee_view(dataset, employee["employee_id"])
        gaps.update(s["skill_id"] for s in view["skills"] if s["gap"] > 0)
        if view["next_grade"] and not view["recommendations"] and view["trajectory"]["gap_count"]:
            blocked.append({**employee, "reason": view["empty_reason"]})
    names = {s["skill_id"]: s["name"] for s in dataset["skill_catalog"]}
    participation = []
    for event in dataset["events"]:
        records = [h for h in dataset["history"] if h["event_id"] == event["event_id"]]
        participation.append({"event_id": event["event_id"], "title": event["title"], "participants": len({h["employee_id"] for h in records}),
                              "records": len(records), "completed": sum(h["status"] == "completed" for h in records)})
    return {"skill_gaps": [{"skill_id": sid, "name": names[sid], "employee_count": count} for sid, count in gaps.most_common()],
            "employees_without_next_step": blocked, "participation": participation, "employee_count": len(dataset["employees"])}
