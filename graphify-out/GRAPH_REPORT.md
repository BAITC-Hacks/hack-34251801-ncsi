# Graph Report - hack-34251801-ncsi  (2026-09-23)

## Corpus Check
- Corpus is ~44,319 words. File relationships are mapped; the graph does not replace record-level dataset validation.

## Summary
- 415 nodes · 955 edges · 13 communities (11 shown, 2 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 44 edges (avg confidence: 0.93)
- Token cost: unavailable (host session exposes no measured per-chunk token usage).

## Community Hubs (Navigation)
- HR Growth and Research
- Contract and Browser Checks
- Dataset and Task Contracts
- Streamlit Growth Screens
- Adapter Integration and Tests
- Legacy Core Ranking
- Growth Persistence and Tests
- Explicit Demo Modes
- Legacy AI Providers
- Development Map Validation
- Compatibility UI Facade
- UI Test Package
- UI Package

## God Nodes (most connected - your core abstractions)
1. `CoreAdapter` - 34 edges
2. `GrowthService` - 30 edges
3. `GrowthTests` - 20 edges
4. `Career Quest HR growth application` - 19 edges
5. `GrowthStore` - 18 edges
6. `e()` - 15 edges
7. `html()` - 15 edges
8. `Legacy Six public core API operations` - 15 edges
9. `render_employee()` - 14 edges
10. `get_employee_view()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Legacy Validated AI event and reason indices` --references--> `refine()`  [EXTRACTED]
  CORE_NOTES.md → core/ai.py
- `Legacy AI deterministic fallback guarantees` --references--> `refine()`  [EXTRACTED]
  CORE_NOTES.md → core/ai.py
- `Legacy Internal dataset schema` --references--> `validate()`  [EXTRACTED]
  CORE_NOTES.md → core/engine.py
- `Legacy Completion gains and assessment baseline` --references--> `current_levels()`  [EXTRACTED]
  CORE_NOTES.md → core/engine.py
- `Legacy Deterministic recommendation eligibility` --references--> `get_employee_view()`  [EXTRACTED]
  CORE_NOTES.md → core/engine.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Shared skill identifier contract** — case_case_1_career_quest_dataset_readme_employee_skills, case_case_1_career_quest_dataset_readme_required_skills, case_case_1_career_quest_dataset_readme_develops_skills, case_case_1_career_quest_dataset_readme_prerequisites, case_case_1_career_quest_dataset_readme_skill_catalog [EXTRACTED 1.00]
- **HR approved learning flow** — readme_certificates, core_growth_certificates, readme_xp, core_growth_growthservice_snapshot [EXTRACTED 1.00]
- **Metered cached AI research flow** — readme_ai_tracks, readme_budget, readme_cache, readme_sources, core_growth_ai_growthadvisor_recommend [EXTRACTED 1.00]

## Communities (13 total, 2 thin omitted)

### Community 0 - "HR Growth and Research"
Cohesion: 0.06
Nodes (46): contextlib, _bounded_http(), worker(), ai_calls SQLite table, fingerprint(), GrowthAdvisor, _http(), limits() (+38 more)

### Community 1 - "Contract and Browser Checks"
Cohesion: 0.07
Nodes (36): argparse, concurrent_futures, copy, core, importlib, io, json, os (+28 more)

### Community 2 - "Dataset and Task Contracts"
Cohesion: 0.06
Nodes (51): activity_history.csv participation log, career_goal nullable role and grade, critical_skills promotion requirement, Career Quest synthetic dataset, develops_skills gain and max_level, Employee assessed skills, employees.json employee profiles, events.json development catalog (+43 more)

### Community 3 - "Streamlit Growth Screens"
Cohesion: 0.13
Nodes (43): employee_view(), finish_activity(), main(), Run with: python -m streamlit run app.py, render_employee(), complete_map_step(), render_hr(), render_hr_overview() (+35 more)

### Community 4 - "Adapter Integration and Tests"
Cohesion: 0.06
Nodes (15): Path, Session imports and persistent HR identity, Managed AI versus legacy reranking, AdapterContractTests, AppInteractionTests, CoreIntegrationTests, Real core and UI boundary, including provider outcomes without network calls., AdapterError (+7 more)

### Community 5 - "Legacy Core Ranking"
Cohesion: 0.09
Nodes (34): _check(), complete_activity(), get_employee_view(), get_hr_view(), import_test_data(), list_employees(), load_dataset(), Stable public API: starter-kit engine and explicit optional demo mode. (+26 more)

### Community 6 - "Growth Persistence and Tests"
Cohesion: 0.13
Nodes (6): GrowthStore, Persistent SQLite growth records, GrowthTests, request(), provider_response(), GrowthUIFlowTests

### Community 7 - "Explicit Demo Modes"
Cohesion: 0.12
Nodes (15): collections, complete_activity(), get_employee_view(), get_hr_view(), import_test_data(), Temporary, explicitly labelled UI fixture. Never used if core/api.py exists., Provisional demo schema only; real engine owns official validation., csv (+7 more)

### Community 8 - "Legacy AI Providers"
Cohesion: 0.11
Nodes (13): contextvars, _bounded_request(), work(), Optional, bounded AI tie-breaker. Models cannot invent facts or change gains., refine(), _request(), settings(), Legacy Validated AI event and reason indices (+5 more)

### Community 9 - "Development Map Validation"
Cohesion: 0.23
Nodes (5): DevelopmentMapTests, A valid actual-schema profile with one gap and one skill at the event cap., branch_label(), build_map_model(), Join facts for presentation; no eligibility, scoring or level calculation.

### Community 10 - "Compatibility UI Facade"
Cohesion: 0.20
Nodes (3): dict, UIFlowTests, Engine

## Knowledge Gaps
- **7 isolated node(s):** `Skill proficiency scale 0-5`, `preferred_language kk ru en`, `manager_id department lead`, `self_paced available anytime`, `Participation completed in_progress dropped no_show declined overdue` (+2 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 113 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CoreAdapter` connect `Adapter Integration and Tests` to `HR Growth and Research`, `Contract and Browser Checks`, `Streamlit Growth Screens`, `Legacy Core Ranking`, `Growth Persistence and Tests`, `Development Map Validation`, `Compatibility UI Facade`?**
  _High betweenness centrality (0.169) - this node is a cross-community bridge._
- **Why does `GrowthService` connect `HR Growth and Research` to `Contract and Browser Checks`, `Adapter Integration and Tests`, `Legacy Core Ranking`, `Growth Persistence and Tests`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `GrowthTests` connect `Growth Persistence and Tests` to `HR Growth and Research`, `Contract and Browser Checks`, `Adapter Integration and Tests`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `CoreAdapter` (e.g. with `Engine` and `AdapterContractTests`) actually correct?**
  _`CoreAdapter` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `GrowthService` (e.g. with `GrowthAdvisor` and `GrowthTests`) actually correct?**
  _`GrowthService` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `GrowthTests` (e.g. with `GrowthAdvisor` and `GrowthService`) actually correct?**
  _`GrowthTests` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Skill proficiency scale 0-5`, `preferred_language kk ru en`, `manager_id department lead` to the rest of the system?**
  _7 weakly-connected nodes found - possible documentation gaps or missing edges._

## Extraction Coverage and Provenance

- Excluded runtime `.career-quest/`, SQLite/DB files, `.env*`, secret files, AppleDouble metadata, virtual environments, dependencies and generated output before detection. Their contents were not read or added to the graph.
- Portable `extraction.json` preserves 376 declared nodes and 968 raw edges before import stubs and endpoint collapse.
- `task.docx` office conversion dependency was unavailable. Text was recovered locally via ZIP/XML into `task_docx_extracted.txt`; semantic source provenance remains `task.docx`. Its detailed Voice Router requirements describe the alternative case.
- Documentation and missing dynamic Python call semantics were reviewed by a host-agent subagent; structural code extraction uses installed Graphify AST APIs. Portable snapshot hashes are in `source_manifest.json`.
- `activity_history.csv` has no structural extractor; its contract is represented from the dataset README.
- Token cost is unavailable, not measured as zero. Rebuilds reuse preserved semantic results without an LLM call.
- Graphify structural extraction emitted no entities for: case/case_1/career_quest_dataset/employees.json, case/case_1/career_quest_dataset/events.json, case/case_1/career_quest_dataset/skills.json. JSON schema relationships are documented by README semantics; individual data records are not graphed.
- Graph health warning: 165 dangling-endpoint edges; 13 collapsed undirected edges. See GRAPH_HEALTH.md for exact diagnostics.
- The raw dangling endpoints are import references. Graphify materialized 39 import stub nodes; the exported graph has zero dangling endpoints. Package aliases core/ui are also represented as namespace stubs.
- Dynamic calls missing from AST were reviewed across app.py, CoreAdapter, GrowthService, GrowthAdvisor and growth views. The managed UI baseline invokes engine.get_employee_view(use_ai=False); only an explicit research button requests paid AI. Legacy/unmanaged API branches remain in the source graph with their conditions.
- core/engine.py's module docstring says no LLM calls, but get_employee_view invokes ai.refine when use_ai=True. The graph follows the executable call.
