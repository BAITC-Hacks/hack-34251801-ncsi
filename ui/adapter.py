"""Compatibility facade for the original core team's UI integration tests.

The application uses CoreAdapter directly. This facade delegates to that same
boundary and contains no independent API selection, imports or mutations.
"""
from pathlib import Path
from ui.core_adapter import CoreAdapter

ROOT = Path(__file__).resolve().parents[1]

class Engine:
    def __init__(self):
        self.adapter = CoreAdapter(ROOT / 'case/case_1/career_quest_dataset')
        self.api = self.adapter.api
        self.is_demo = self.adapter.is_demo
        self.key = self.adapter.backend_name

    def load(self, path):
        return self.api.load_dataset(str(path))

    def employees(self, dataset):
        return self.adapter.list_employees(dataset)

    def employee(self, dataset, employee_id):
        return self.adapter.get_employee_view(dataset, employee_id)

    def hr(self, dataset):
        return self.adapter.get_hr_view(dataset)

    def complete(self, dataset, employee_id, event_id):
        updated, _ = self.adapter.complete_activity(dataset, employee_id, event_id)
        return updated

    def import_files(self, dataset, employees, history):
        return self.adapter.import_test_data(dataset, employees.getvalue() if employees is not None else None,
                                             history.getvalue() if history is not None else None)
