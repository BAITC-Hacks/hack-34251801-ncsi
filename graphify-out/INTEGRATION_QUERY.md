# UI → core → AI integration query

Question: How does an employee view reach optional AI, and which operations
preserve deterministic facts?

Query vocabulary is selected from the graph's labels: `adapter`, `api`,
`engine`, `refine`, `request`.

The broad CLI traversal is budget-limited in `integration_query_raw.txt`.
The complete call path below was separately checked against every edge in the
saved graph, including nodes omitted from that truncated CLI display.

## Confirmed normal-mode call path

```text
app.employee_view
  → CoreAdapter.get_employee_view
  → core.api.get_employee_view
  → core.engine.get_employee_view
  → core.ai.refine
  → core.ai._bounded_request
  → work (thread callback)
  → core.ai._request
```

The engine → `ai.refine` and internal AI call relationships come from Graphify
AST extraction. The app's injected adapter calls, `self.api` dispatch, and
conditional API → engine dispatch were verified in source and added as semantic
`calls` edges with **EXTRACTED, confidence 1.0**. They describe `CoreAdapter`
loading `core.api` and non-demo datasets. `__demo__` and test-injected modules are
alternative branches. The thread callback is AST `indirect_call`.

Sources/locations in the graph: `app.py` / `employee_view`; `ui/core_adapter.py` /
`CoreAdapter.get_employee_view / self.api.get_employee_view`; `core/api.py` /
`get_employee_view / engine branch when dataset is not __demo__`;
`core/engine.py` / `L181`; `core/ai.py` / `L94`, `L63`, `L58`.

## What remains deterministic

The core computes eligibility, score, skill gains, grade requirements and
progress before optional AI. AI may select within three near-tied candidates
and reorder existing reason indices. It cannot invent new reason text, scores,
skills or gains; invalid outputs return the baseline list.

Sources: `CORE_NOTES.md` / `Формулы и соглашения`, `LLM`;
`core/engine.py` / `get_employee_view`;
`core/ai.py` / `refine`.

The UI reads engine output and AI status, formats labels and explanation fields,
and performs no provider HTTP request itself. Provider requests remain in
`core.ai._request`. Provider availability is not demonstrated by a source graph;
README/CORE_NOTES explicitly report mocked verification and untested live APIs.

## Mutation and HR boundaries

`CoreAdapter.complete_activity` copies the dataset, calls the public completion
API, then re-queries the employee view before adopting the result. The engine's
completion uses `use_ai=False`; the UI's subsequent view refresh may reach
optional AI. Therefore “completion does not call AI” is true of the engine
mutation itself, not necessarily the complete UI interaction.

Sources: `ui/core_adapter.py` / `CoreAdapter.complete_activity`;
`core/engine.py` / `complete_activity`.

`CoreAdapter.import_test_data` stages uploads in a temporary directory, invokes
the public import API on a copy and checks employee enumeration before returning
new data. `core.engine.import_test_data` validates the combined profiles/history.

Sources: `ui/core_adapter.py` / `CoreAdapter.import_test_data`;
`core/engine.py` / `import_test_data`, `validate`.

HR invokes `core.engine.get_hr_view`; per-employee views inside HR use
`use_ai=False`, so bulk HR aggregation does not issue AI requests.

Sources: `core/api.py` / `get_hr_view`; `core/engine.py` / `get_hr_view`.

## Graph limitations

Graphify AST does not extract individual JSON dataset entities or CSV records;
those contracts are represented from reviewed dataset READMEs. Dynamic method
dispatch requires reviewed semantic bridges. Import targets are represented by
typed namespace stubs; raw extraction warnings and final graph integrity are
reported separately in `GRAPH_HEALTH.md`. Ordinary undirected export collapses
some multiple relationships on identical endpoints; exact details remain in
`diagnostics.json` and portable `extraction.json` (246 nodes, 531 raw edges before
import stubs and endpoint collapse). The source graph describes
possible calls, not runtime execution coverage. Host model token usage is
unavailable and is never reported as measured zero.
