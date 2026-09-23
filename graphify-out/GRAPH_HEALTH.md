[graphify] MultiDiGraph edge-collapse diagnostic
input: <in-memory>
input_stage: provided JSON (normal graph.json is post-build)
effective_directed: <direct-call>
nodes: 376
unverified_code_nodes: 0
raw_edges: 968
valid_candidate_edges: 803
missing_endpoint_edges: 0
dangling_endpoint_edges: 165
external_reference_edges: 0
self_loop_edges: 0
exact_duplicate_edges: 0
directed_unique_endpoint_pairs: 790
directed_same_endpoint_collapsed_edges: 13
undirected_unique_endpoint_pairs: 790
undirected_same_endpoint_collapsed_edges: 13
same_endpoint_group_count: 13
relation_variant_groups: 13
source_file_variant_groups: 0
source_location_variant_groups: 0
context_variant_groups: 0
post_build_graph_type: Graph
post_build_edges: 955
producer_suppression_sites: 12
producer_suppression_examples:
  - L1349 seen_ids arity=unknown
  - L1882 seen_ids arity=unknown
  - L1884 seen_doc_refs arity=unknown
  - L2254 seen_ids arity=unknown
  - L2401 seen_ids arity=unknown
  - L3127 seen_keys arity=unknown
  - L3296 seen_keys arity=unknown
  - L5370 seen_ids arity=unknown
examples:
  - app_render_employee -> app_render_employee_complete_map_step edges=2 relations=['contains', 'indirect_call'] locations=['L115', 'L121'] contexts=['', 'argument']
  - core_ai_bounded_request -> core_ai_bounded_request_work edges=2 relations=['contains', 'indirect_call'] locations=['L56', 'L63'] contexts=['', 'argument']
  - core_growth_ai_limits -> core_growth_ai_limits_amount edges=2 relations=['calls', 'contains'] locations=['L32', 'L40'] contexts=['', 'call']
  - core_growth_ai_schema -> core_growth_ai_schema_obj edges=2 relations=['calls', 'contains'] locations=['L54', 'L57'] contexts=['', 'call']
  - core_growth_ai_bounded_http -> core_growth_ai_bounded_http_worker edges=2 relations=['contains', 'indirect_call'] locations=['L109', 'L116'] contexts=['', 'argument']
note: normal graph.json is post-build; raw producer loss must be measured earlier.

Final graph:
[graphify] MultiDiGraph edge-collapse diagnostic
input: <in-memory>
input_stage: provided JSON (normal graph.json is post-build)
effective_directed: <direct-call>
nodes: 415
unverified_code_nodes: 0
raw_edges: 955
valid_candidate_edges: 955
missing_endpoint_edges: 0
dangling_endpoint_edges: 0
external_reference_edges: 0
self_loop_edges: 0
exact_duplicate_edges: 0
directed_unique_endpoint_pairs: 955
directed_same_endpoint_collapsed_edges: 0
undirected_unique_endpoint_pairs: 955
undirected_same_endpoint_collapsed_edges: 0
same_endpoint_group_count: 0
relation_variant_groups: 0
source_file_variant_groups: 0
source_location_variant_groups: 0
context_variant_groups: 0
post_build_graph_type: Graph
post_build_edges: 955
producer_suppression_sites: 12
producer_suppression_examples:
  - L1349 seen_ids arity=unknown
  - L1882 seen_ids arity=unknown
  - L1884 seen_doc_refs arity=unknown
  - L2254 seen_ids arity=unknown
  - L2401 seen_ids arity=unknown
  - L3127 seen_keys arity=unknown
  - L3296 seen_keys arity=unknown
  - L5370 seen_ids arity=unknown
note: normal graph.json is post-build; raw producer loss must be measured earlier.
Import stub names: argparse, collections, concurrent_futures, contextlib, contextvars, copy, core, csv, datetime, decimal, hashlib, html, importlib, io, json, logging, math, os, pathlib, playwright_sync_api, queue, re, socket, sqlite3, streamlit, streamlit_testing_v1, subprocess, sys, tempfile, textwrap, threading, time, types, ui, unittest, unittest_mock, urllib_parse, urllib_request, uuid
