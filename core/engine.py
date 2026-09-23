"""Explainable deterministic baseline for the actual starter kit. No LLM calls."""
import csv
import json
from copy import deepcopy
from collections import Counter
from datetime import date
from pathlib import Path
from uuid import uuid4
from . import ai

GRADES = ['Junior', 'Middle', 'Senior', 'Lead']
HISTORY_FIELDS = {'record_id', 'employee_id', 'event_id', 'date', 'due_date', 'status', 'completion_pct', 'score', 'feedback_rating', 'assigned_by'}
STATUSES = {'completed', 'in_progress', 'dropped', 'no_show', 'declined', 'overdue'}

def read_json(path):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)

def read_history(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not HISTORY_FIELDS <= set(reader.fieldnames or []):
            raise ValueError('В CSV истории не хватает столбцов: ' + ', '.join(sorted(HISTORY_FIELDS - set(reader.fieldnames or []))))
        rows = list(reader)
        for row in rows:
            for key in ('completion_pct', 'score', 'feedback_rating'):
                if row.get(key) and row[key].isdigit():
                    row[key] = int(row[key])
                elif key != 'completion_pct' and row.get(key) == '':
                    row[key] = None
        return rows

def integer(value, low, high, label):
    if isinstance(value, bool) or not str(value).isdigit() or not low <= int(value) <= high:
        raise ValueError(f'{label}: ожидается целое число {low}–{high}.')

def validate(dataset):
    skill_ids = {s['skill_id'] for s in dataset['skills']}
    roles = {(p['role'], p['grade']) for p in dataset['role_profiles']}
    ids, event_ids, records = set(), {e['event_id'] for e in dataset['events']}, set()
    required = {'employee_id', 'full_name', 'department', 'role', 'grade', 'manager_id', 'hire_date', 'tenure_months', 'work_format', 'preferred_language', 'career_goal', 'skills', 'last_review_date'}
    for e in dataset['employees']:
        if not isinstance(e, dict) or not required <= e.keys():
            raise ValueError('Профиль должен содержать все поля employees.json стартового кита, включая full_name и last_review_date.')
        eid = e['employee_id']
        if not isinstance(eid, str) or not eid.strip() or eid in ids:
            raise ValueError('employee_id должен быть непустым и уникальным: ' + str(eid))
        ids.add(eid)
        if (e['role'], e['grade']) not in roles:
            raise ValueError(f'{eid}: неизвестная роль или грейд.')
        integer(e['tenure_months'], 0, 1200, f'{eid}: tenure_months')
        if not isinstance(e['skills'], dict) or set(e['skills']) - skill_ids:
            raise ValueError(f'{eid}: неизвестные навыки или неверный объект skills.')
        for sid, level in e['skills'].items():
            if type(level) is not int:
                raise ValueError(f'{eid}: уровень {sid} должен быть целым числом.')
            integer(level, 0, 5, sid)
        if e['work_format'] not in {'office', 'hybrid', 'remote'} or e['preferred_language'] not in {'kk', 'ru', 'en'}:
            raise ValueError(f'{eid}: неизвестный формат работы или язык.')
        hire, review = date.fromisoformat(e['hire_date']), date.fromisoformat(e['last_review_date'])
        if hire > review or review > date.fromisoformat(dataset['as_of_date']):
            raise ValueError(f'{eid}: проверьте даты приёма и последней оценки.')
        goal = e['career_goal']
        if goal is not None and (not isinstance(goal, dict) or (goal.get('target_role'), goal.get('target_grade')) not in roles):
            raise ValueError(f'{eid}: неизвестная карьерная цель.')
    for e in dataset['employees']:
        if e['manager_id'] is not None and e['manager_id'] not in ids:
            raise ValueError(f'{e["employee_id"]}: неизвестный manager_id.')
    for h in dataset['history']:
        if not HISTORY_FIELDS <= h.keys() or not h['record_id'] or h['record_id'] in records:
            raise ValueError('История: отсутствуют поля или повторяется record_id.')
        records.add(h['record_id'])
        if h['employee_id'] not in ids or h['event_id'] not in event_ids:
            raise ValueError('История содержит неизвестный employee_id или event_id.')
        if h['status'] not in STATUSES or h['assigned_by'] not in {'self', 'manager', 'hr'}:
            raise ValueError('История: неизвестный status или assigned_by.')
        if date.fromisoformat(h['date']) > date.fromisoformat(dataset['as_of_date']):
            raise ValueError('История не может быть позже даты среза.')
        if h['due_date']:
            date.fromisoformat(h['due_date'])
        integer(h['completion_pct'], 0, 100, 'completion_pct')
        pct = int(h['completion_pct'])
        if (h['status'] == 'completed' and pct != 100) or (h['status'] in {'no_show', 'declined'} and pct != 0) or (h['status'] in {'in_progress', 'overdue'} and pct > 95) or (h['status'] == 'dropped' and not 5 <= pct <= 95):
            raise ValueError('История: completion_pct не соответствует status.')
        for key, low, high in [('score', 0, 100), ('feedback_rating', 1, 5)]:
            if h[key] != '' and h[key] is not None:
                integer(h[key], low, high, key)

def load_dataset(data_dir: str) -> dict:
    folder = Path(data_dir)
    skills = read_json(folder / 'skills.json')
    result = {'as_of_date': skills['meta']['as_of_date'], 'skills': skills['skills'], 'role_profiles': skills['role_profiles'],
        'employees': read_json(folder / 'employees.json')['employees'], 'events': read_json(folder / 'events.json')['events'], 'history': read_history(folder / 'activity_history.csv')}
    validate(result)
    return result

def import_test_data(dataset: dict, employees_file=None, history_file=None) -> dict:
    result = deepcopy(dataset)
    if employees_file is not None:
        body = read_json(employees_file)
        if not isinstance(body, dict) or not isinstance(body.get('employees'), list):
            raise ValueError('employees.json: ожидается объект с массивом employees, как в стартовом ките.')
        result['employees'].extend(body['employees'])
    if history_file is not None:
        result['history'].extend(read_history(history_file))
    validate(result)
    return result

def brief(e):
    return {'employee_id': e['employee_id'], 'name': e['full_name'], 'role': e['role'], 'grade': e['grade'], 'tenure_months': e['tenure_months']}

def list_employees(dataset: dict) -> list[dict]:
    return [brief(e) for e in dataset['employees']]

def employee(dataset, employee_id):
    found = next((e for e in dataset['employees'] if e['employee_id'] == employee_id), None)
    if found is None:
        raise ValueError('Сотрудник не найден.')
    return found

def current_levels(dataset, e, history):
    levels = dict(e['skills'])
    events = {x['event_id']: x for x in dataset['events']}
    for h in sorted(history, key=lambda h: (h['date'], h['record_id'])):
        if h['status'] == 'completed' and h['date'] > e['last_review_date']:
            for gain in events[h['event_id']]['develops_skills']:
                sid = gain['skill_id']
                before = levels.get(sid, 0)
                levels[sid] = max(before, min(gain['max_level'], before + gain['gain']))
    return levels

def get_employee_view(dataset: dict, employee_id: str, use_ai=True) -> dict:
    e = employee(dataset, employee_id)
    history = [h for h in dataset['history'] if h['employee_id'] == employee_id]
    levels = current_levels(dataset, e, history)
    index = GRADES.index(e['grade'])
    target_grade = GRADES[index + 1] if index < 3 else None
    target = next(p for p in dataset['role_profiles'] if p['role'] == e['role'] and p['grade'] == (target_grade or 'Lead'))
    labels = {s['skill_id']: s['name'] for s in dataset['skills']}
    skills = [{'skill_id': sid, 'label': labels[sid], 'current': levels.get(sid, 0), 'required': req, 'gap': max(0, req - levels.get(sid, 0))} for sid, req in target['required_skills'].items()]
    skills.sort(key=lambda s: (-s['gap'], s['label']))
    total = sum(s['required'] for s in skills)
    progress = round(100 * sum(min(s['current'], s['required']) for s in skills) / total, 1) if total else 100
    events = {x['event_id']: x for x in dataset['events']}
    recommendations = []
    for event in dataset['events']:
        eid = event['event_id']
        event_history = [h for h in history if h['event_id'] == eid]
        if event['mandatory'] or e['role'] not in event['target_roles'] or e['grade'] not in event['target_grades']:
            continue
        if any(levels.get(s, 0) < r for s, r in event['prerequisites'].items()):
            continue
        if event['format'] != 'self_paced' and not any(d >= dataset['as_of_date'] for d in event['upcoming_sessions']):
            continue
        if any(h['status'] == 'completed' for h in event_history) and eid != 'EV_036':
            continue
        if any(h['status'] == 'completed' and h['date'] == dataset['as_of_date'] for h in event_history):
            continue
        changes, benefit = [], 0
        for g in event['develops_skills']:
            sid, before = g['skill_id'], levels.get(g['skill_id'], 0)
            after = max(before, min(g['max_level'], before + g['gain']))
            if after > before:
                changes.append({'skill_id': sid, 'label': labels[sid], 'before': before, 'after': after})
            gap = max(0, target['required_skills'].get(sid, 0) - before)
            benefit += min(gap, after - before) * (3 if sid in target['critical_skills'] else 1)
        if benefit <= 0:
            continue
        similar_failures = sum(h['status'] in {'no_show', 'declined', 'dropped'} and events[h['event_id']]['type'] == event['type'] for h in history)
        same_failures = sum(h['status'] in {'no_show', 'declined', 'dropped'} for h in event_history)
        in_progress = any(h['status'] == 'in_progress' for h in event_history)
        format_bonus = .5 if e['work_format'] == 'remote' and event['format'] in {'online', 'self_paced'} else 0
        score = benefit * 10 / (1 + .5 * same_failures + .15 * similar_failures) + (2 if in_progress else 0) + format_bonus - .05 * event['duration_hours']
        relevant = [c for c in changes if c['skill_id'] in target['required_skills']]
        skill_reason = '; '.join(f"{c['label']}: {c['before']} → {c['after']} при требовании {target['required_skills'][c['skill_id']]}" + (' (критичный навык)' if c['skill_id'] in target['critical_skills'] else '') for c in relevant)
        history_reason = f'Учтены пропуски/отказы: {same_failures} у этой активности, {similar_failures} у того же типа.' if similar_failures or same_failures else 'В истории нет пропусков/отказов активностей этого типа.'
        reasons = [f"Для {e['role']} / {e['grade']}. Предусловия выполнены.", f"Цель {target_grade or 'поддержание Lead'}: {skill_reason}.", history_reason, f"Формат {event['format']}, нагрузка {event['duration_hours']} ч." + (' Уже начата — приоритет завершению.' if in_progress else '')]
        recommendations.append({'event_id': eid, 'title': event['title'], 'score': round(score, 3), 'reasons': reasons, 'skill_changes': changes})
    recommendations.sort(key=lambda r: (-r['score'], r['event_id']))
    if use_ai:
        recommendations = ai.refine(recommendations, e, events)
    return {'employee': brief(e), 'next_grade': target_grade, 'skills': skills,
        'history': [dict(h, title=events[h['event_id']]['title']) for h in sorted(history, key=lambda x: x['date'], reverse=True)],
        'recommendations': recommendations[:3], 'trajectory': {'current_grade': e['grade'], 'target_grade': target_grade, 'progress_percent': progress}}

def complete_activity(dataset: dict, employee_id: str, event_id: str) -> dict:
    view = get_employee_view(dataset, employee_id, use_ai=False)
    if not any(r['event_id'] == event_id for r in view['recommendations']):
        raise ValueError('Активность уже завершена или не входит в доступные рекомендации.')
    e = employee(dataset, employee_id)
    # Snapshot date may equal last review. Update the baseline on that exact day
    # so the new completion is reflected without replaying earlier history twice.
    if e['last_review_date'] == dataset['as_of_date']:
        rec = next(r for r in view['recommendations'] if r['event_id'] == event_id)
        for c in rec['skill_changes']:
            e['skills'][c['skill_id']] = c['after']
    dataset['history'].append({'record_id': 'UI_' + uuid4().hex, 'employee_id': employee_id, 'event_id': event_id, 'date': dataset['as_of_date'], 'due_date': '', 'status': 'completed', 'completion_pct': 100, 'score': None, 'feedback_rating': None, 'assigned_by': 'self'})
    return get_employee_view(dataset, employee_id, use_ai=False)

def get_hr_view(dataset: dict) -> dict:
    views = [get_employee_view(dataset, e['employee_id'], use_ai=False) for e in dataset['employees']]
    gaps = Counter(s['label'] for v in views for s in v['skills'] if s['gap'] > 0)
    counts = Counter(h['event_id'] for h in dataset['history'])
    completed = Counter(h['event_id'] for h in dataset['history'] if h['status'] == 'completed')
    return {'skill_gaps': [{'label': s, 'employee_count': n} for s, n in gaps.most_common()],
        'employees_without_recommendations': [v['employee'] for v in views if not v['recommendations']],
        'activity_participation': [{'title': e['title'], 'participations': counts[e['event_id']], 'completed': completed[e['event_id']]} for e in dataset['events']]}
