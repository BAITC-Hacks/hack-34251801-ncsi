"""Single integration boundary. UI never imports core directly."""
from pathlib import Path
from copy import deepcopy
from importlib import import_module, invalidate_caches
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = ('load_dataset', 'import_test_data', 'list_employees', 'get_employee_view', 'complete_activity', 'get_hr_view')

class Engine:
    def __init__(self):
        invalidate_caches()
        has_core = (ROOT / 'core' / 'api.py').is_file()
        self.api = import_module('core.api' if has_core else 'ui.demo_adapter')
        self.is_demo = not has_core or getattr(self.api, 'DEMO_ONLY', False)
        missing = [name for name in FUNCTIONS if not callable(getattr(self.api, name, None))]
        if missing:
            raise ValueError('В API отсутствуют функции: ' + ', '.join(missing))
        self.key = ('core-demo' if has_core else 'demo') if self.is_demo else 'core'

    def load(self, path):
        return self.api.load_dataset(str(path))

    def employees(self, dataset):
        return self.api.list_employees(dataset)

    def employee(self, dataset, employee_id):
        return self.api.get_employee_view(dataset, employee_id)

    def hr(self, dataset):
        return self.api.get_hr_view(dataset)

    def ai_status(self):
        try:
            return import_module('core.ai').LAST_STATUS.get()
        except ImportError:
            return 'Демонстрационный адаптер'

    def complete(self, dataset, employee_id, event_id):
        candidate = deepcopy(dataset)
        result = self.api.complete_activity(candidate, employee_id, event_id)
        # Supports in-place API returning an employee view, or a returned dataset.
        if isinstance(result, dict) and 'employees' in result and 'employee' not in result:
            candidate = result
        return candidate

    def import_files(self, dataset, employees, history):
        if employees is None and history is None:
            raise ValueError('Выберите хотя бы один файл.')
        with TemporaryDirectory(prefix='career-quest-') as temp:
            paths = []
            for upload, name in ((employees, 'employees.json'), (history, 'activity_history.csv')):
                if upload is None:
                    paths.append(None)
                    continue
                content = upload.getvalue()
                if len(content) > 10 * 1024 * 1024:
                    raise ValueError('Размер каждого файла — не более 10 МБ.')
                content.decode('utf-8-sig')
                path = Path(temp) / name
                path.write_bytes(content)
                paths.append(str(path))
            candidate = deepcopy(dataset)
            result = self.api.import_test_data(candidate, employees_file=paths[0], history_file=paths[1])
            if not isinstance(result, dict):
                raise ValueError('Движок не вернул dataset после импорта.')
            self.employees(result)
            return result

def friendly_error(exc):
    import json
    if isinstance(exc, UnicodeDecodeError):
        return 'Не удалось прочитать кодировку. Сохраните файл в UTF-8.'
    if isinstance(exc, json.JSONDecodeError):
        return f'Некорректный JSON, строка {exc.lineno}. Проверьте запятые и кавычки.'
    if isinstance(exc, FileNotFoundError):
        return 'Файлы набора данных не найдены. Проверьте папку стартового кита.'
    if isinstance(exc, (ValueError, KeyError)):
        return 'Проверьте данные: ' + str(exc)
    return 'Не удалось выполнить операцию. Подробности доступны ниже для диагностики.'
