# Graph Report - hack-34251801-ncsi  (2026-09-23)

## Corpus Check
- Localized final update: authenticated login, workspace sign-out, tests and merged README; excluded env, runtime databases and virtual environments.

## Summary
- 970 nodes · 2532 edges · 41 communities (27 shown, 14 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 128 edges (avg confidence: 0.91)
- Token cost: unavailable (host session does not expose measured semantic token usage).

## Community Hubs (Navigation)
- Employee and HR Actions
- Test Growth Checks
- Test Dataset Checks
- Test Persistent Login
- Test Core Integration Checks
- Career Quest Dataset
- Employee and HR Actions
- Persistent Adapter
- Project Integration
- Application Setup and Delivery
- Map Keyboard and Viewport
- Test Demo Routing Checks
- Approved Growth and Routes
- Service
- Project Integration
- Project Integration
- Test Service
- Test Growth Research Checks
- Approved Growth and Routes
- Approved Growth and Routes
- Original Engine Contract
- Test Ui
- Test Growth Research Checks
- Demo
- Approved Growth and Routes
- Test Growth Research Checks
- Deterministic Career Engine
- Demo Adapter
- Test Starter Kit Checks
- Test Demo Api Checks
- Test Demo Session Checks
- Legacy Explanation Providers
- Test Ai Checks
- Project Integration
- Project Integration
- Project Integration
- Init Checks
- Init
- Authentication and Permissions
- Authentication and Permissions
- Authentication and Permissions

## God Nodes (most connected - your core abstractions)
1. `AuthService` - 64 edges
2. `GrowthService` - 57 edges
3. `GrowthStore` - 39 edges
4. `CoreAdapter` - 34 edges
5. `AuthError` - 34 edges
6. `AuthorizedGrowth` - 28 edges
7. `PersistentAdapter` - 27 edges
8. `AuthServiceTests` - 26 edges
9. `GrowthAdvisor` - 25 edges
10. `ResearchTests` - 24 edges

## Surprising Connections (you probably didn't know these)
- `Legacy Internal dataset schema` --references--> `validate()`  [EXTRACTED]
  CORE_NOTES.md → core/engine.py
- `Original core engine preserved behind adapter` --references--> `CoreAdapter`  [EXTRACTED]
  README.md → ui/core_adapter.py
- `Search-source-verified course URLs` --references--> `validate_response()`  [EXTRACTED]
  README.md → core/growth_ai.py
- `Legacy Deterministic recommendation eligibility` --references--> `get_employee_view()`  [EXTRACTED]
  CORE_NOTES.md → core/engine.py
- `Legacy Required-skill coverage progress` --references--> `get_employee_view()`  [EXTRACTED]
  CORE_NOTES.md → core/engine.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Authenticated entry and owned persistent workspace** — app_main, auth_service_authservice_current_user, ui_persistent_adapter_persistentadapter_require, storage_dataset_datasetstore_read, ui_persistent_adapter_authorizedgrowth_latest [EXTRACTED 1.00]
- **Explicit atomic local demo provisioning** — auth_manage_main, auth_demo_seed_seed_demo_accounts, storage_dataset_datasetstore_load_or_initialize, auth_service_derive_key [EXTRACTED 1.00]
- **Shared skill identifier contract** — case_case_1_career_quest_dataset_readme_employee_skills, case_case_1_career_quest_dataset_readme_required_skills, case_case_1_career_quest_dataset_readme_develops_skills, case_case_1_career_quest_dataset_readme_prerequisites, case_case_1_career_quest_dataset_readme_skill_catalog [EXTRACTED 1.00]
- **HR-approved learning completion lifecycle** — core_growth_growthservice_choose_course, core_growth_growthservice_decide_training, core_growth_growthservice_start_training, core_growth_growthservice_submit_training_completion, core_growth_growthservice_review_certificate, core_growth_growthservice_snapshot [EXTRACTED 1.00]
- **Shared map, course list and personal route plan** — ui_growth_views_render_growth_map, ui_growth_views_render_tracks, ui_growth_views_render_route, core_growth_growthservice_development_plan [EXTRACTED 1.00]

## Communities (41 total, 14 thin omitted)

### Community 0 - "Employee and HR Actions"
Cohesion: 0.06
Nodes (66): finish_activity(), import_data(), logout_account(), main(), Run with: python -m streamlit run app.py, render_admin_status(), render_employee(), render_hr() (+58 more)

### Community 1 - "Test Growth Checks"
Cohesion: 0.06
Nodes (29): ResearchError, GrowthStore, Exception, playwright_sync_api, main(), Read-only browser smoke on a running app. Full mutation acceptance is isolated…, login_demo(), Shared navigation through the integrated, explicitly labelled demo gate. These… (+21 more)

### Community 2 - "Test Dataset Checks"
Cohesion: 0.05
Nodes (29): Any, main(), dataclasses, dotenv, StorageConfigTests, DatasetStoreTests, initialize(), append_employee() (+21 more)

### Community 3 - "Test Persistent Login"
Cohesion: 0.11
Nodes (9): ProfileAccountsTests, bind(), bootstrap(), AuthResilienceTests, AuthService, SQLite-backed credentials and expiring, opaque server-side sessions.…, Create an employee account. There is intentionally no role argument., Match the bootstrap guard, including an existing inactive admin. (+1 more)

### Community 4 - "Test Core Integration Checks"
Cohesion: 0.06
Nodes (12): Engine, AdapterContractTests, CoreIntegrationTests, AdapterError, CoreAdapter, _explanation_fields(), Path, ValueError (+4 more)

### Community 5 - "Career Quest Dataset"
Cohesion: 0.08
Nodes (43): activity_history.csv participation log, career_goal nullable role and grade, critical_skills promotion requirement, Career Quest synthetic dataset, develops_skills gain and max_level, Employee assessed skills, employees.json employee profiles, events.json development catalog (+35 more)

### Community 6 - "Employee and HR Actions"
Cohesion: 0.10
Nodes (37): SQLite course decisions and training lifecycle, One read model for the map, alternatives and persistent personal route. Reading…, math, Active-page rendering and callbacks, action(), alternatives(), certificate_form(), submit() (+29 more)

### Community 7 - "Persistent Adapter"
Cohesion: 0.09
Nodes (10): employee_view(), DemoSeedTests, Create all missing fixtures atomically, keeping previously seeded users. Only…, seed_demo_accounts(), CoreAdapter, PersistentAdapterTests, AuthorizedRows, PersistentAdapter (+2 more)

### Community 8 - "Project Integration"
Cohesion: 0.16
Nodes (26): argparse, concurrent_futures, contextvars, copy, core, Optional, bounded AI tie-breaker. Models cannot invent facts or change gains., Persistent HR workflow. Extends the existing engine without changing its files., datetime (+18 more)

### Community 9 - "Application Setup and Delivery"
Cohesion: 0.06
Nodes (37): Atomic idempotent local demo account fixtures, Scrypt passwords and hashed expiring session tokens, Integrated account roles and employee bindings, Explicit demo routing is separate from authenticated default, First-installation administrator bootstrap, Local prototype identity limitations, Persistent background AI jobs, Micro-dollar budget reservation journal (+29 more)

### Community 10 - "Map Keyboard and Viewport"
Cohesion: 0.09
Nodes (27): cache_resource, Streamlit 1.64.0 runtime, InteractiveMapModelTests, The map displays backend facts and joins only supported references., build_map_model(), _component(), Interactive presentation of the persisted growth plan and approved facts. The…, Join saved recommendations to confirmed facts without predicting levels. (+19 more)

### Community 11 - "Test Demo Routing Checks"
Cohesion: 0.12
Nodes (13): dict, UIFlowTests, assert_rendered(), demo_login(), demo_logout(), employee_tab(), hr_tab(), isolate_demo_storage() (+5 more)

### Community 12 - "Approved Growth and Routes"
Cohesion: 0.10
Nodes (5): Only approved achievements affect this growth profile and AI facts., Project confirmed portfolio changes into the original HR engine., AuthorizedGrowth, Authorized growth reads use latest durable dataset, Validate the stored role/ownership even for fragment reruns and callbacks.

### Community 13 - "Service"
Cohesion: 0.11
Nodes (19): Independent authentication module for Career Quest., AuthError, Unique account-to-employee profile binding, _normalize_email(), Authenticate credentials and return the current stored account role. An…, Validate expiry, idle timeout and current account role; refresh last_seen., Idempotently revoke one session; a copied token stops working as well., Authorize inside the caller's transaction, never from a cached user. (+11 more)

### Community 14 - "Project Integration"
Cohesion: 0.14
Nodes (19): importlib, io, json, pathlib, streamlit_runtime_state_session_state_proxy, streamlit_testing_v1, Tests of a synthetic demo, NOT the official starter-kit schema., Real starter-kit validation; synthetic extra profile uses its actual schema. (+11 more)

### Community 15 - "Project Integration"
Cohesion: 0.14
Nodes (19): Explicit public demo accounts: atomic creation without overwriting local users., Persistent profile links, upgrade migration and atomic administrator actions., Cooldown cost and graceful hashing failures, using isolated local databases., Real SQLite/scrypt checks; test users live only in temporary directories., Streamlit form/session integration against isolated SQLite and real scrypt., Explicit, local-only demo provisioning; never run by the login page. These…, _derive_key(), Local account storage; no event journal, passwords, or session tokens in logs.… (+11 more)

### Community 17 - "Test Growth Research Checks"
Cohesion: 0.12
Nodes (17): _bounded_http(), worker(), _http(), Cached, asynchronous research; costs and unsuccessful attempts survive…, Allowlisted structural diagnostics, without provider prose or source text., request_payload(), _response_diagnostics(), Safe provider errors and response diagnostics (+9 more)

### Community 18 - "Approved Growth and Routes"
Cohesion: 0.23
Nodes (8): course_id(), GrowthService, now_iso(), public_url(), HR assignment reuses a course's lifecycle without repeating completion., text(), track_id(), HR assigns mandatory training through the shared plan

### Community 20 - "Original Engine Contract"
Cohesion: 0.20
Nodes (18): _check(), complete_activity(), get_employee_view(), get_hr_view(), import_test_data(), list_employees(), Stable public API: starter-kit engine and explicit optional demo mode., complete_activity() (+10 more)

### Community 22 - "Test Growth Research Checks"
Cohesion: 0.23
Nodes (4): GrowthAdvisor, limits(), Synchronous compatibility API; new UI uses read/start exclusively., request()

### Community 23 - "Demo"
Cohesion: 0.18
Nodes (10): collections, load_dataset(), complete_activity(), get_employee_view(), get_hr_view(), import_test_data(), load_dataset(), Temporary, explicitly labelled UI fixture. Never used if core/api.py exists. (+2 more)

### Community 24 - "Approved Growth and Routes"
Cohesion: 0.22
Nodes (5): fingerprint(), course_identity(), dump(), Match one course across saved plans and tracking-link variants., save()

### Community 26 - "Deterministic Career Engine"
Cohesion: 0.29
Nodes (10): brief(), import_test_data(), integer(), list_employees(), load_dataset(), Explainable deterministic baseline for the actual starter kit. No LLM calls., read_history(), read_json() (+2 more)

### Community 27 - "Demo Adapter"
Cohesion: 0.27
Nodes (6): complete_activity(), _employee(), get_employee_view(), get_hr_view(), load_dataset(), Temporary, deterministic UI preview. Replaced automatically by core.api. This…

### Community 28 - "Test Starter Kit Checks"
Cohesion: 0.25
Nodes (3): current_levels(), Legacy Completion gains and assessment baseline, StarterKitTests

### Community 31 - "Legacy Explanation Providers"
Cohesion: 0.29
Nodes (7): _bounded_request(), work(), refine(), _request(), settings(), Legacy Validated AI event and reason indices, Legacy AI deterministic fallback guarantees

### Community 33 - "Project Integration"
Cohesion: 0.40
Nodes (3): auth, DemoLoginUITests, Demo routing preserves learning state and never uses the account database.

## Knowledge Gaps
- **16 isolated node(s):** `python-dotenv 1.2.3 configuration loader`, `SQLite course decisions and training lifecycle`, `Safe provider errors and response diagnostics`, `manager_id department lead`, `EV_004 first month onboarding` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 234 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AuthService` connect `Test Persistent Login` to `Employee and HR Actions`, `Project Integration`, `Test Dataset Checks`, `Persistent Adapter`, `Project Integration`, `Service`, `Project Integration`, `Test Service`, `Test Ui`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._
- **Why does `CoreAdapter` connect `Test Core Integration Checks` to `Employee and HR Actions`, `Test Growth Checks`, `Project Integration`, `Application Setup and Delivery`, `Test Demo Routing Checks`, `Approved Growth and Routes`, `Project Integration`, `Approved Growth and Routes`, `Demo`?**
  _High betweenness centrality (0.133) - this node is a cross-community bridge._
- **Why does `Career Quest employee development navigator` connect `Application Setup and Delivery` to `Career Quest Dataset`, `Employee and HR Actions`?**
  _High betweenness centrality (0.122) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `AuthService` (e.g. with `DemoSeedTests` and `ProfileAccountsTests`) actually correct?**
  _`AuthService` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `GrowthService` (e.g. with `GrowthTests` and `GrowthUIFlowTests`) actually correct?**
  _`GrowthService` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `GrowthStore` (e.g. with `GrowthTests` and `ResearchTests`) actually correct?**
  _`GrowthStore` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `CoreAdapter` (e.g. with `Engine` and `AdapterContractTests`) actually correct?**
  _`CoreAdapter` has 7 INFERRED edges - model-reasoned connections that need verification._

## Coverage and Provenance

- Unchanged code and semantic relationships were preserved. The latest authentication changes were re-extracted through Graphify AST; changed README evidence was reviewed against the merged code.
- All 77 source hashes are checked in source_manifest.json. No external API calls were made by graph generation.
- Secret env files, runtime SQLite and virtual environments are excluded. task.docx retains verified ZIP/XML-derived semantics; Office conversion remains unavailable. CSS is hashed as presentation source, without AST entities.
- BENCHMARK.md contains a clearly marked historical measurement; no benchmark/query was repeated during this localized refresh.
