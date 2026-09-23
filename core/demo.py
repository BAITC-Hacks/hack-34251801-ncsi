"""Temporary, explicitly labelled UI fixture. Never used if core/api.py exists."""
from copy import deepcopy
from collections import Counter
from datetime import date
import json
import csv
import io

LABELS = {'SK_PYTHON': 'Python', 'SK_SYSTEM_DESIGN': 'System Design', 'SK_PUBLIC_SPEAKING': 'Публичные выступления'}

def load_dataset(data_dir: str) -> dict:
    return {'employees': [
        {'employee_id': 'DEMO-01', 'name': 'Алия · демопрофиль', 'role': 'Backend Engineer', 'grade': 'Middle', 'tenure_months': 28, 'skills': {'SK_PYTHON': 3, 'SK_SYSTEM_DESIGN': 2, 'SK_PUBLIC_SPEAKING': 2}},
        {'employee_id': 'DEMO-02', 'name': 'Данияр · пустая история', 'role': 'Backend Engineer', 'grade': 'Middle', 'tenure_months': 14, 'skills': {'SK_PYTHON': 2, 'SK_SYSTEM_DESIGN': 1, 'SK_PUBLIC_SPEAKING': 1}},
        {'employee_id': 'DEMO-03', 'name': 'Самат · цель достигнута', 'role': 'Backend Engineer', 'grade': 'Middle', 'tenure_months': 48, 'skills': dict.fromkeys(LABELS, 4)}],
        'history': [], 'events': [
            {'event_id': 'DEMO-E1', 'title': 'От сервиса к системе: практикум по проектированию надёжных банковских платформ', 'skill_id': 'SK_SYSTEM_DESIGN'},
            {'event_id': 'DEMO-E2', 'title': 'Python: работа с производительностью', 'skill_id': 'SK_PYTHON'},
            {'event_id': 'DEMO-E3', 'title': 'Как представить техническое решение команде', 'skill_id': 'SK_PUBLIC_SPEAKING'}]}

def list_employees(dataset: dict) -> list[dict]:
    return [deepcopy({k: v for k, v in e.items() if k != 'skills'}) for e in dataset['employees']]

def get_employee_view(dataset: dict, employee_id: str) -> dict:
    employee = next(e for e in dataset['employees'] if e['employee_id'] == employee_id)
    history = [h for h in dataset['history'] if h['employee_id'] == employee_id]
    skills = [{'skill_id': k, 'label': label, 'current': employee['skills'].get(k, 0), 'required': 4, 'gap': max(0, 4 - employee['skills'].get(k, 0))} for k, label in LABELS.items()]
    recommendations = []
    for event in dataset['events']:
        skill = next(s for s in skills if s['skill_id'] == event['skill_id'])
        if not skill['gap'] or any(h['event_id'] == event['event_id'] and h['status'] == 'completed' for h in history):
            continue
        recommendations.append({'event_id': event['event_id'], 'title': event['title'], 'score': float(skill['gap']),
            'reasons': [f"Для перехода {employee['grade']} → Senior нужен уровень 4.", f"{skill['label']}: сейчас {skill['current']}, разрыв {skill['gap']}.", 'Эта активность ещё не завершена.' if history else 'История пока пуста — это стартовый шаг.'],
            'skill_changes': [{'skill_id': skill['skill_id'], 'label': skill['label'], 'before': skill['current'], 'after': min(4, skill['current'] + 1)}]})
    return {'employee': {k: v for k, v in employee.items() if k != 'skills'}, 'next_grade': 'Senior', 'skills': skills, 'history': deepcopy(history), 'recommendations': recommendations[:3],
        'trajectory': {'current_grade': employee['grade'], 'target_grade': 'Senior', 'progress_percent': round(sum(min(s['current'], s['required']) for s in skills) / 12 * 100)}}

def complete_activity(dataset: dict, employee_id: str, event_id: str) -> dict:
    view = get_employee_view(dataset, employee_id)
    rec = next((r for r in view['recommendations'] if r['event_id'] == event_id), None)
    if rec is None:
        raise ValueError('Активность уже завершена или больше не доступна.')
    employee = next(e for e in dataset['employees'] if e['employee_id'] == employee_id)
    for change in rec['skill_changes']:
        employee['skills'][change['skill_id']] = change['after']
    dataset['history'].append({'employee_id': employee_id, 'event_id': event_id, 'title': rec['title'], 'status': 'completed', 'date': date.today().isoformat()})
    return get_employee_view(dataset, employee_id)

def get_hr_view(dataset: dict) -> dict:
    views = [get_employee_view(dataset, e['employee_id']) for e in dataset['employees']]
    gaps = Counter(s['label'] for v in views for s in v['skills'] if s['gap'] > 0)
    counts = Counter(h['event_id'] for h in dataset['history'])
    return {'skill_gaps': [{'label': k, 'employee_count': n} for k, n in gaps.most_common()],
        'employees_without_recommendations': [v['employee'] for v in views if not v['recommendations']],
        'activity_participation': [{'title': e['title'], 'participations': counts[e['event_id']]} for e in dataset['events']]}

def import_test_data(dataset: dict, employees_file=None, history_file=None) -> dict:
    """Provisional demo schema only; real engine owns official validation."""
    result = deepcopy(dataset)
    if employees_file:
        with open(employees_file, encoding='utf-8-sig') as f:
            employees = json.load(f)
        if not isinstance(employees, list) or not employees:
            raise ValueError('Профили: ожидается непустой JSON-массив.')
        ids = {e['employee_id'] for e in result['employees']}
        for e in employees:
            if not isinstance(e, dict) or not {'employee_id', 'role', 'grade', 'tenure_months', 'skills'} <= e.keys():
                raise ValueError('В профиле нужны employee_id, role, grade, tenure_months и skills.')
            if not isinstance(e['employee_id'], str) or not e['employee_id'].strip() or e['employee_id'] in ids:
                raise ValueError('employee_id должен быть непустым и уникальным.')
            if type(e['tenure_months']) is not int or e['tenure_months'] < 0:
                raise ValueError('tenure_months должен быть целым неотрицательным числом.')
            if not isinstance(e['skills'], dict) or any(type(v) is not int or not 0 <= v <= 5 for v in e['skills'].values()):
                raise ValueError('Уровни skills должны быть целыми числами от 0 до 5.')
            if e['role'] != 'Backend Engineer' or e['grade'] != 'Middle' or set(e['skills']) - set(LABELS):
                raise ValueError('Демо поддерживает только Backend Engineer / Middle и три демонстрационных навыка. Для остальных профилей нужен core.')
            ids.add(e['employee_id'])
            result['employees'].append(e)
    if history_file:
        with open(history_file, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not {'employee_id', 'event_id', 'status', 'date'} <= set(reader.fieldnames or []):
                raise ValueError('История: нужны столбцы employee_id,event_id,status,date.')
            for row in reader:
                if row['employee_id'] not in {e['employee_id'] for e in result['employees']} or row['event_id'] not in {e['event_id'] for e in result['events']}:
                    raise ValueError('История ссылается на неизвестный профиль или событие.')
                if row['status'] not in {'completed', 'skipped', 'declined'}:
                    raise ValueError('Неизвестный статус истории.')
                date.fromisoformat(row['date'])
                result['history'].append(row)
    return result
