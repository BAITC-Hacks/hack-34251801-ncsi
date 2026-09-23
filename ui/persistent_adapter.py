"""Authenticated application boundary; core calculations remain unchanged."""

from auth.service import AuthError
from copy import deepcopy
from storage.dataset import DatasetStore
from ui.core_adapter import CoreAdapter


class PersistentAdapter(CoreAdapter):
    def __init__(self, data_dir, service, token, store=None):
        super().__init__(data_dir)
        self.auth_service = service
        self.token = token
        self.dataset_store = store or DatasetStore()
        self.managed_ai = True
        self.dataset_revision = None

    def require(self, roles=None, employee_id=None):
        user = self.auth_service.current_user(self.token)
        if not user:
            raise AuthError("Сессия завершена. Войдите снова.")
        if roles and user['role'] not in roles:
            raise PermissionError("У вашего аккаунта нет доступа к этому действию.")
        if employee_id is not None and user['role'] == 'employee':
            if not user.get('employee_id') or user['employee_id'] != employee_id:
                raise PermissionError("Можно открыть только профиль, назначенный вашему аккаунту.")
        return user

    def load_dataset(self):
        self.require()
        dataset, self.dataset_revision = self.dataset_store.load_or_initialize(
            lambda: CoreAdapter.load_dataset(self))
        # Seed data may change in a later checkout. Display exactly the catalogue
        # used by core in this persistent workspace, not freshly downloaded files.
        self.catalog = {s['skill_id']: deepcopy(s) for s in dataset['skills']}
        self.events = {event['event_id']: deepcopy(event) for event in dataset['events']}
        self.role_profiles = deepcopy(dataset['role_profiles'])
        self.as_of_date = dataset['as_of_date']
        return dataset

    def list_employees(self, dataset):
        user = self.require()
        rows = super().list_employees(dataset)
        if user['role'] == 'employee':
            rows = [row for row in rows if row['employee_id'] == user.get('employee_id')]
        return rows

    def get_employee_view(self, dataset, employee_id):
        self.require({'employee', 'hr', 'admin'}, employee_id)
        return super().get_employee_view(dataset, employee_id)

    def get_hr_view(self, dataset):
        self.require({'hr', 'admin'})
        return super().get_hr_view(dataset)

    def complete_activity(self, dataset, employee_id, event_id):
        self.require({'employee'}, employee_id)
        def complete(latest):
            self.require({'employee'}, employee_id)
            return CoreAdapter.complete_activity(self, latest, employee_id, event_id)
        updated, self.dataset_revision, view = self.dataset_store.mutate(complete)
        return updated, view

    def import_test_data(self, dataset, employees_bytes=None, history_bytes=None):
        self.require({'admin'})
        def import_files(latest):
            self.require({'admin'})
            updated = CoreAdapter.import_test_data(self, latest, employees_bytes, history_bytes)
            return updated, None
        updated, self.dataset_revision, _ = self.dataset_store.mutate(import_files)
        return updated

    @property
    def growth(self):
        if not hasattr(self, '_authorized_growth'):
            raw = CoreAdapter.growth.fget(self)
            self._authorized_growth = AuthorizedGrowth(self, raw)
        return self._authorized_growth


class AuthorizedRows:
    def __init__(self, adapter, raw):
        self.adapter, self.raw = adapter, raw

    def rows(self, table, employee_id=None):
        user = self.adapter.require()
        if user['role'] == 'employee':
            if not employee_id:
                raise PermissionError("Общий список доступен только HR и администратору.")
            self.adapter.require({'employee'}, employee_id)
        return self.raw.rows(table, employee_id)


class AuthorizedGrowth:
    """Validate the stored role/ownership even for fragment reruns and callbacks."""
    def __init__(self, adapter, raw):
        self.adapter, self.raw = adapter, raw
        self.store = AuthorizedRows(adapter, raw.store)
        self.traits = raw.traits

    def budget(self):
        self.adapter.require()
        return self.raw.budget()

    def baseline_view(self, dataset, employee_id):
        self.adapter.require(employee_id=employee_id)
        return self.raw.baseline_view(dataset, employee_id)

    def preserve_baseline_before_simulation(self, dataset, employee_id):
        self.adapter.require({'employee'}, employee_id)
        return self.raw.preserve_baseline_before_simulation(dataset, employee_id)

    def _latest(self, employee_id, roles=None):
        self.adapter.require(roles, employee_id)
        dataset, _ = self.adapter.dataset_store.read()
        return dataset

    def profile(self, dataset, employee_id):
        return self.raw.profile(self._latest(employee_id), employee_id)

    def snapshot(self, dataset, employee_id, today=None):
        return self.raw.snapshot(self._latest(employee_id), employee_id, today)

    def facts(self, dataset, employee_id):
        return self.raw.facts(self._latest(employee_id), employee_id)

    def recommend(self, dataset, employee_id, generate=False):
        latest = self._latest(employee_id, {'employee'} if generate else None)
        return self.raw.recommend(latest, employee_id, generate)

    def save_profile(self, dataset, employee_id, hire_date, traits, actor='employee'):
        latest = self._latest(employee_id, {'hr'})
        return self.raw.save_profile(latest, employee_id, hire_date, traits, actor='hr')

    def submit_certificate(self, dataset, employee_id, *args, **kwargs):
        latest = self._latest(employee_id, {'employee'})
        return self.raw.submit_certificate(latest, employee_id, *args, **kwargs)

    def review_certificate(self, dataset, certificate_id, approve, awards=None, reason='', actor='employee'):
        self.adapter.require({'hr'})
        latest, _ = self.adapter.dataset_store.read()
        return self.raw.review_certificate(latest, certificate_id, approve, awards, reason, actor='hr')

    def request_training(self, dataset, employee_id, plan_id, track_index, course_index):
        latest = self._latest(employee_id, {'employee'})
        return self.raw.request_training(latest, employee_id, plan_id, track_index, course_index)

    def decide_training(self, request_id, approve, reason, actor='employee'):
        self.adapter.require({'hr'})
        return self.raw.decide_training(request_id, approve, reason, actor='hr')
