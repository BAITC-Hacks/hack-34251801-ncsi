# HR growth integration query

Question: How do HR approval, XP, persistent records and explicit AI research
connect, and can viewing a profile trigger paid research?

Expanded from actual graph vocabulary: `certificate`, `snapshot`, `recommend`,
`budget`, `reservations`, `baseline`, `managed`.

The CLI traversal in `integration_query_raw.txt` is budget-limited. The four
critical paths below were also validated against every edge of the full graph.

## Profile views use the deterministic baseline

```text
app.employee_view
  → CoreAdapter.get_employee_view
  → GrowthService.baseline_view
  → engine.get_employee_view(use_ai=False)
```

`app.main` sets `adapter.managed_ai=True`. The adapter's managed branch uses the
growth service's deterministic baseline. The graph also contains the preserved
legacy `core.api → core.engine → core.ai.refine` source path; that possible call
does not mean it executes during managed UI navigation.

Sources: `app.py` / `main`, `employee_view`; `ui/core_adapter.py` /
`CoreAdapter.get_employee_view / managed_ai branch`; `core/growth.py` /
`GrowthService.baseline_view / engine.get_employee_view(use_ai=False)`.

## Research requires the explicit button

```text
ui.growth_views.render_tracks
  → GrowthService.recommend
  → GrowthAdvisor.recommend
  → _bounded_http
  → worker (thread callback)
  → _http
```

The first call uses `generate=False`, returning a valid cached plan or a ready
state. The research button passes `generate=True`. Missing configuration returns
an unavailable state; it does not invent courses. Before network access the
advisor checks the request bound, starts a SQLite transaction, checks shared
spending and reserves the entire request cap in `ai_calls`.

The implemented caps are $5 per application database and $0.10 per request,
with environment overrides permitted only downward. One web search and at most
3,000 output tokens are requested; the caller waits at most 28 seconds. Usage
is charged conservatively and unknown cost retains the reservation. These are
implementation facts, not a claim about an OpenAI account's actual balance or
an independent verification of current provider tariffs.

Source: `ui/growth_views.py` / `render_tracks`; `core/growth.py` /
`GrowthService.recommend`; `core/growth_ai.py` / `GrowthAdvisor.recommend`,
`limits`, `request_payload`, `_bounded_http`.

Returned course URLs must match a returned search source and an allowed provider
domain. Portfolio fingerprints and a seven-day cache determine whether a plan
can be reused; `request_training` rejects stale or mismatched plans. The graph
does not establish live API availability: no external API was called here.

Source: `core/growth_ai.py` / `validate_response`, `fingerprint`;
`core/growth.py` / `GrowthService.request_training`.

## HR approval changes the confirmed portfolio

```text
render_hr_requests
  → GrowthService.review_certificate
  → certificates SQLite table
  → GrowthService.snapshot
```

Submission creates a pending certificate without skill awards or learning XP.
An HR approval records selected 0–1 skill awards. `snapshot` applies approved
awards, caps levels at 5, and computes 100 learning XP per approved certificate
plus 10 tenure XP per full day. The game level is `1 + xp // 1000`; it is separate
from job grade. A reviewed certificate cannot be reviewed again, and course
fingerprints prevent another credit for the same employee/course.

Sources: `core/growth.py` / `submit_certificate`, `review_certificate`,
`snapshot`; `README.md` / `Сценарий сотрудника и HR`.

Training-request approval is a separate HR decision. It performs no purchase
and adds neither completion nor XP. Profile, certificate, plan, request and
spending tables are represented from SQL declarations only. Runtime SQLite
records were excluded from detection and never read.

Source: `core/growth.py` / `GrowthStore.__init__`, `request_training`,
`decide_training`.

## Starter-kit simulation stays outside approved learning

```text
CoreAdapter.complete_activity
  → GrowthService.preserve_baseline_before_simulation
  → session dataset _growth_baselines
```

The legacy engine can mutate assessed skills when assessment and snapshot dates
coincide. The managed adapter preserves initial skills before that mutation.
The growth snapshot uses the saved baseline and excludes `UI_` history rows,
so a simulated route completion cannot become an HR-approved certificate gain.
The legacy route itself continues to update the session dataset.

Sources: `ui/core_adapter.py` / `CoreAdapter.complete_activity`;
`core/growth.py` / `preserve_baseline_before_simulation`, `snapshot`.

## Coverage and limitations

Graphify AST does not resolve all injected adapter/property calls. Those edges
were source-reviewed and marked `EXTRACTED`, confidence 1.0, with their branch
conditions. Ordinary undirected export collapses some relationships sharing
endpoints; `extraction.json` retains every raw edge and `GRAPH_HEALTH.md` shows
both raw and final diagnostics. Import stubs are namespace references, not
runtime call evidence. JSON/CSV dataset records are not individual graph nodes;
their schema is represented from reviewed READMEs. Actual Graphify host-session
token usage is unavailable. No runtime DB, environment files, secrets, paid API
calls, application edits or Git mutations were part of this graph update.
