"""Stable public API: starter-kit engine and explicit optional demo mode."""
from . import demo, engine

DEMO_ONLY = False

def load_dataset(data_dir: str) -> dict:
    if data_dir != '__demo__':
        return engine.load_dataset(data_dir)
    dataset = demo.load_dataset(data_dir)
    dataset['_demo_only'] = True
    return dataset

def _check(dataset):
    if not isinstance(dataset, dict) or 'employees' not in dataset:
        raise ValueError('Некорректный dataset.')

def import_test_data(dataset: dict, employees_file=None, history_file=None) -> dict:
    _check(dataset)
    return (demo if dataset.get('_demo_only') else engine).import_test_data(dataset, employees_file, history_file)

def list_employees(dataset: dict) -> list[dict]:
    _check(dataset)
    return (demo if dataset.get('_demo_only') else engine).list_employees(dataset)

def get_employee_view(dataset: dict, employee_id: str) -> dict:
    _check(dataset)
    if not any(e['employee_id'] == employee_id for e in dataset['employees']):
        raise ValueError('Сотрудник не найден.')
    return (demo if dataset.get('_demo_only') else engine).get_employee_view(dataset, employee_id)

def complete_activity(dataset: dict, employee_id: str, event_id: str) -> dict:
    _check(dataset)
    return (demo if dataset.get('_demo_only') else engine).complete_activity(dataset, employee_id, event_id)

def get_hr_view(dataset: dict) -> dict:
    _check(dataset)
    return (demo if dataset.get('_demo_only') else engine).get_hr_view(dataset)
