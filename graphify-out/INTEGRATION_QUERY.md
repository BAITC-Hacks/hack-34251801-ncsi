# Authenticated interactive growth integration

Current snapshot: authentication/storage merge, course-direction filtering and mandatory training assigned by HR.

## Account and dataset boundary

The default app authenticates persistent accounts. `PersistentAdapter.require` revalidates the session, stored role and employee binding. `AuthorizedGrowth` checks access and reads the latest persisted dataset before forwarding growth operations. `DatasetStore` keeps imports and legacy history across restarts. Optional free role selection is enabled only by `CAREER_QUEST_DEMO_MODE=1`.

Sources: `app.py` / `main`; `auth/service.py` / `current_user`; `ui/persistent_adapter.py` / `require`, `AuthorizedGrowth._latest`; `storage/dataset.py` / `read`, `mutate`.

## Shared plan, choices and research

Map, course list and route use `development_plan`; authenticated calls cross `AuthorizedGrowth` and then the shared `GrowthService`. Map comparison selects an employee-specific direction filter. Numbered direction blocks show course alternatives and reset to all directions. Choosing/hiding a course changes backend records, not skill levels. Choices and HR decisions survive AI refreshes.

The map can start first/weekly background research; manual refresh is explicit. GPT-5 uses low reasoning and one hosted search. Reservations, errors and known charges persist. Unknown costs are retained. The 0.10 USD request admission estimate and 5 USD application limit are application controls; search has no numeric returned-token cap, so the estimate is not a provider hard-spending guarantee.

Sources: `ui/growth_views.py` / `render_growth_map`, `render_tracks`, `render_route`, `set_direction_filter`; `core/growth.py` / `development_plan`, `choose_course`, `hide_course`, `start_research`; `core/growth_ai.py` / `read`, `_prepare`, `start`, `_execute`.

## Mandatory courses assigned by HR

HR uses the same saved plan and budgeted search. Authenticated assignment passes through `AuthorizedGrowth.assign_course` or `assign_custom_course` to the corresponding `GrowthService` operation. It stores an approved mandatory request and explanation, restores hidden suggestions, and reuses existing course lifecycle records. Employees cannot cancel mandatory requests. Completion still requires certificate review before XP or skills change.

Sources: `ui/growth_views.py` / `course_card`, `custom_course_form`; `ui/persistent_adapter.py` / `AuthorizedGrowth.assign_course`, `assign_custom_course`; `core/growth.py` / `_assign_course_request`, `cancel_training`.

## Interactive presentation and confirmed progress

Local Streamlit v2 returns selection and viewport state; it does not call a model or independently rank recommendations. JavaScript/Python links describe shared state, not cross-language function calls. Confirmed skills/certificates are facts; future skills remain proposals.

Route completion opens a certificate form. HR approval atomically records awards and training status. A later `snapshot` reads approved certificates to calculate XP and levels: persisted data flow, not a direct call from review to snapshot. Stable containers and callbacks avoid stale page trees; isolated browser checks exercise real interaction and role transitions.

Sources: `ui/map_component.py`; `ui/map_frontend/map.js`; `ui/growth_views.py` / `certificate_form.submit.save`, `render_hr_requests.review`; `core/growth.py` / `review_certificate`, `snapshot`; `app.py` / `main`.

`VALIDATION.json` records current graph integrity and source hashes. `integration_query_raw.txt` lists selected current graph links. `BENCHMARK.md` retains a clearly marked earlier measurement. Graph generation made no external API requests; application live-search evidence is documented separately in README.

Final incoming auth update: login derives the stored account role automatically and the workspace header provides sign-out. Source: auth/service.py, auth/ui.py, auth/integration_ui.py and app.py. README checks cover the merged auth/storage and growth scenarios.
