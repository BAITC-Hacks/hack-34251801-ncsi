# CORE_NOTES — фактический контракт

Источник: README.ru.md и файлы кита в `case/case_1/career_quest_dataset`, main-коммит `c6d946b8fd8e8bba32ed28b977e51898207cf209`. Дата среза 2026-10-01; системная дата не участвует в расчётах. Стартовый кит найден в репозитории и прочитан, схема больше не предположительная.

## Публичный API

- load_dataset(data_dir: str) -> dict: читает четыре файла кита; специальное значение __demo__ явно включает временные данные.
- list_employees(dataset) -> list[dict]: employee_id, name (из full_name), role, grade, tenure_months.
- get_employee_view(dataset, employee_id) -> dict: ровно employee, next_grade, skills, history, recommendations, trajectory по согласованному контракту. history обогащена title.
- complete_activity(dataset, employee_id, event_id) -> dict: изменяет dataset на месте, возвращает employee view. Принимает рекомендованный доступный event_id. Повтор отклоняет.
- import_test_data(dataset, employees_file=None, history_file=None) -> dict: входы — пути файлов UTF-8; возвращает новый dataset; исходный не меняет.
- get_hr_view(dataset) -> dict: skill_gaps [{label,employee_count}], employees_without_recommendations [employee], activity_participation [{title,participations,completed}]. HR не вызывает LLM.

Ошибки пользовательских данных — ValueError. UI также обрабатывает FileNotFoundError, JSONDecodeError, UnicodeDecodeError. Импорт и завершение UI выполняет на копии и фиксирует после успеха. Временные файлы импорта удаляются. Все вызовы UI через ui/adapter.py.

## Внутренний dataset и схема

Ключи: as_of_date, employees, events, skills, role_profiles, history. employees.json и events.json — объекты с массивами employees/events. skills.json содержит meta.as_of_date, skills, role_profiles. Поля профиля и CSV перечислены в README и core/engine.py.

Импорт только добавляет уникальные employee_id/record_id; обновление существующих профилей не реализовано. manager_id проверяется по объединённому списку, навыки/роли/грейды — по каталогам. Неизвестные ссылки, неверные шкалы/даты/статусы и несогласованный completion_pct отклоняются. Импорт истории воспроизводит новые завершения после last_review_date, а не увеличивает сохранённый уровень повторно.

## Формулы и соглашения

Уровень: max(before, min(max_level, before+gain)). Применяются completed строго после last_review_date в порядке date/record_id. События до и в день оценки считаются уже отражёнными в baseline. Для кнопки завершения в день оценки обновляется baseline; новая запись не воспроизводится повторно.

Eligibility: mandatory=False, роль/грейд в аудитории, выполнены prerequisites, self_paced или будущая upcoming_session, нет completed. Исключение — регулярный EV_036, но не два завершения в день среза.

benefit = сумма min(gap, after-before) × weight; weight=3 для critical_skills, иначе 1. Нулевая польза исключается.

score = 10×benefit / (1 + 0.5×same_failures + 0.15×similar_failures) + 2×in_progress + format_bonus - 0.05×duration_hours.

failures: no_show/declined/dropped; similar: тот же event.type за всю историю. format_bonus=0.5 для remote и online/self_paced. Равные оценки упорядочиваются по event_id. Это эвристика, не обученная модель.

Прогресс = сумма min(current,required) / сумма required × 100, до 0.1. Следующий грейд текущей роли: Junior/Middle/Senior/Lead. Для Lead next_grade и target_grade=null, сравнение с Lead. Повышение автоматически не выполняется. Career goal другой роли не меняет детерминированную траекторию.

HR employee_count — сотрудники с gap>0; participations — все записи, включая отказы; completed — завершения. Отсутствие рекомендации не означает плохую результативность сотрудника.

## LLM

core/ai.py поддерживает none/openai/nvidia, модель и ключ через окружение. OpenAI Responses: strict JSON schema, store=false. NVIDIA Chat Completions: JSON с локальной проверкой. Выбор только среди первых трёх кандидатов в пределах max(1,10% top score). Ответ содержит event_id и уникальные индексы существующих reasons. Свободный текст не принимается: сохраняются все факты, изменяется только их порядок.

Ожидание по умолчанию 8, максимум 9 секунд; без повторов, два фоновых запроса, кеш 128, cooldown ошибки 30 секунд. Неверный ответ/ошибка/таймаут даёт исходный результат. HR и собственно завершение не вызывают AI. Имя/employee_id/исходный журнал не отправляются. Ключи в этой среде отсутствуют: live API не проверен. Mock-тесты не доказывают доступность конкретной модели.

## Передача интегратору

Передать core/, tests/, CORE_NOTES.md и README. Основной режим DEMO_ONLY=False работает с китом. core/demo.py и ui/demo_adapter.py остаются для явного __demo__ и тестов, не используются в стандартном запуске. При замене модулей перезапустите Streamlit. Если вторая модель предлагает лучшее ранжирование, заменить engine при сохранении публичного контракта и тестов.

Остались: live API с ключами команды, скрытые профили жюри, оценка качества, постоянное хранение/авторизация вне прототипа. Разные record_id одной сессии семантически не дедуплицируются. Date интерпретируется как дата завершения при completed. Кнопка завершения — симуляция в дату среза.
