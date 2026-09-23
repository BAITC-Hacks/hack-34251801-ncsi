# Graph Report - hack-34251801-ncsi-ui  (2026-09-23)

## Corpus Check
- Corpus is ~35,712 words. File relationships are mapped; the graph does not replace record-level dataset validation.

## Summary
- 275 nodes · 527 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 30 edges (avg confidence: 0.94)
- Token cost: unavailable (host session exposes no measured per-chunk token usage).

## Community Hubs (Navigation)
- Core Career Decisions
- AI Providers and Validation
- Dataset Skill Contracts
- UI Integration and Tests
- Streamlit Views and Components
- Explicit Demo Modes
- Compatibility UI Facade
- Skill Replay Validation
- Demo API Contract Tests
- Core Loading and Errors
- Hackathon Product Requirements
- UI Test Package
- UI Package

## God Nodes (most connected - your core abstractions)
1. `CoreAdapter` - 26 edges
2. `Six public core API operations` - 15 edges
3. `get_employee_view()` - 12 edges
4. `Engine` - 12 edges
5. `AdapterContractTests` - 12 edges
6. `Career Quest Streamlit application` - 12 edges
7. `html()` - 11 edges
8. `employees.json employee profiles` - 11 edges
9. `main()` - 10 edges
10. `e()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Validated AI event and reason indices` --references--> `refine()`  [EXTRACTED]
  CORE_NOTES.md → core/ai.py
- `AI deterministic fallback guarantees` --references--> `refine()`  [EXTRACTED]
  CORE_NOTES.md → core/ai.py
- `OpenAI NVIDIA bounded candidate selection` --references--> `refine()`  [EXTRACTED]
  README.md → core/ai.py
- `Six public core API operations` --references--> `load_dataset()`  [EXTRACTED]
  CORE_NOTES.md → core/api.py
- `Internal dataset schema` --references--> `validate()`  [EXTRACTED]
  CORE_NOTES.md → core/engine.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Shared skill identifier contract** — case_case_1_career_quest_dataset_readme_employee_skills, case_case_1_career_quest_dataset_readme_required_skills, case_case_1_career_quest_dataset_readme_develops_skills, case_case_1_career_quest_dataset_readme_prerequisites, case_case_1_career_quest_dataset_readme_skill_catalog [EXTRACTED 1.00]

## Communities (13 total, 3 thin omitted)

### Community 0 - "Core Career Decisions"
Cohesion: 0.06
Nodes (48): argparse, refine(), settings(), _check(), complete_activity(), get_employee_view(), get_hr_view(), import_test_data() (+40 more)

### Community 1 - "AI Providers and Validation"
Cohesion: 0.08
Nodes (31): contextvars, copy, core, _bounded_request(), work(), Optional, bounded AI tie-breaker. Models cannot invent facts or change gains., _request(), hashlib (+23 more)

### Community 2 - "Dataset Skill Contracts"
Cohesion: 0.07
Nodes (46): activity_history.csv participation log, career_goal nullable role and grade, critical_skills promotion requirement, Career Quest synthetic dataset, develops_skills gain and max_level, Employee assessed skills, employees.json employee profiles, events.json development catalog (+38 more)

### Community 3 - "UI Integration and Tests"
Cohesion: 0.08
Nodes (9): Factual explanation and separate gain display, AdapterContractTests, AppInteractionTests, CoreIntegrationTests, CoreAdapter, _explanation_fields(), Display the engine's evidence; never ask a model or generate new reasons., _rows() (+1 more)

### Community 4 - "Streamlit Views and Components"
Cohesion: 0.25
Nodes (23): employee_view(), finish_activity(), main(), Run with: python -m streamlit run app.py, render_employee(), render_hr(), render_import(), render_recommendation() (+15 more)

### Community 5 - "Explicit Demo Modes"
Cohesion: 0.11
Nodes (17): collections, load_dataset(), complete_activity(), get_employee_view(), get_hr_view(), import_test_data(), load_dataset(), Temporary, explicitly labelled UI fixture. Never used if core/api.py exists. (+9 more)

### Community 6 - "Compatibility UI Facade"
Cohesion: 0.20
Nodes (3): dict, UIFlowTests, Engine

### Community 7 - "Skill Replay Validation"
Cohesion: 0.25
Nodes (3): current_levels(), Completion gains and assessment baseline, StarterKitTests

### Community 9 - "Core Loading and Errors"
Cohesion: 0.33
Nodes (5): Path, Required real core without silent demo, AdapterError, An actionable data/integration problem that the interface can display., ValueError

### Community 10 - "Hackathon Product Requirements"
Cohesion: 0.40
Nodes (5): LLM meaningful decision layer, Explainable decisions and uncertainty, HackAlem AI Halyk Bank challenge, Repository README reproducible solution, Voice Router alternative challenge

## Knowledge Gaps
- **7 isolated node(s):** `Skill proficiency scale 0-5`, `preferred_language kk ru en`, `manager_id department lead`, `self_paced available anytime`, `Participation completed in_progress dropped no_show declined overdue` (+2 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 97 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CoreAdapter` connect `UI Integration and Tests` to `Core Career Decisions`, `AI Providers and Validation`, `Streamlit Views and Components`, `Explicit Demo Modes`, `Compatibility UI Facade`, `Core Loading and Errors`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Why does `Engine` connect `Compatibility UI Facade` to `AI Providers and Validation`, `UI Integration and Tests`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `Career Quest Streamlit application` connect `Core Career Decisions` to `Core Loading and Errors`, `UI Integration and Tests`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `CoreAdapter` (e.g. with `Engine` and `AdapterContractTests`) actually correct?**
  _`CoreAdapter` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `Engine` (e.g. with `UIFlowTests` and `CoreAdapter`) actually correct?**
  _`Engine` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Skill proficiency scale 0-5`, `preferred_language kk ru en`, `manager_id department lead` to the rest of the system?**
  _7 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Core Career Decisions` be split into smaller, more focused modules?**
  _Cohesion score 0.06262626262626263 - nodes in this community are weakly interconnected._

## Extraction Coverage and Provenance

- `extraction.json` preserves all 531 raw edges with relative source paths before the 29 import stubs and four endpoint collapses; commit it alongside the diagnostics for reproducible integrity review.
- Ignored AppleDouble `._*` and `__MACOSX` archive metadata, virtual environments, dependency folders and generated Graphify output.
- `task.docx` office conversion dependency was unavailable. Text was recovered locally via ZIP/XML into `task_docx_extracted.txt`; semantic source provenance remains `task.docx`. Its detailed Voice Router requirements describe the alternative case.
- Documentation and missing dynamic Python call semantics were reviewed by a host-agent subagent; structural code extraction uses installed Graphify AST APIs. Portable snapshot hashes are in `source_manifest.json`.
- `activity_history.csv` has no structural extractor; its contract is represented from the dataset README.
- Token cost is unavailable, not measured as zero. Rebuilds reuse preserved semantic results without an LLM call.
- Graphify structural extraction emitted no entities for: case/case_1/career_quest_dataset/employees.json, case/case_1/career_quest_dataset/events.json, case/case_1/career_quest_dataset/skills.json. JSON schema relationships are documented by README semantics; individual data records are not graphed.
- Graph health warning: 94 dangling-endpoint edges; 4 collapsed undirected edges. See GRAPH_HEALTH.md for exact diagnostics.
- The raw dangling endpoints are import references. Graphify materialized 29 import stub nodes; the exported graph has zero dangling endpoints. Package aliases core/ui are also represented as namespace stubs.
- Dynamic Python calls missing from AST were reviewed in app.py, ui/core_adapter.py and core/api.py. Added calls describe the default non-demo CoreAdapter/core.engine path; alternate injected adapters and the explicit __demo__ branch remain separate.
- core/engine.py's module docstring says no LLM calls, but get_employee_view invokes ai.refine when use_ai=True. The graph follows the executable call.
