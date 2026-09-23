[graphify] MultiDiGraph edge-collapse diagnostic
input: <in-memory>
input_stage: provided JSON (normal graph.json is post-build)
effective_directed: <direct-call>
nodes: 246
unverified_code_nodes: 0
raw_edges: 531
valid_candidate_edges: 437
missing_endpoint_edges: 0
dangling_endpoint_edges: 94
external_reference_edges: 0
self_loop_edges: 0
exact_duplicate_edges: 0
directed_unique_endpoint_pairs: 433
directed_same_endpoint_collapsed_edges: 4
undirected_unique_endpoint_pairs: 433
undirected_same_endpoint_collapsed_edges: 4
same_endpoint_group_count: 4
relation_variant_groups: 4
source_file_variant_groups: 0
source_location_variant_groups: 0
context_variant_groups: 0
post_build_graph_type: Graph
post_build_edges: 527
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
  - core_ai_bounded_request -> core_ai_bounded_request_work edges=2 relations=['contains', 'indirect_call'] locations=['L56', 'L63'] contexts=['', 'argument']
  - ui_checks_test_core_integration_coreintegrationtests_test_successful_ai_selection_keeps_facts_and_labels_its_actual_role -> ui_checks_test_core_integration_coreintegrationtests_test_successful_ai_selection_keeps_facts_and_labels_its_actual_role_response edges=2 relations=['contains', 'indirect_call'] locations=['L59', 'L63'] contexts=['', 'argument']
  - ui_demo_adapter_load_dataset -> ui_demo_adapter_load_dataset_read edges=2 relations=['calls', 'contains'] locations=['L21', 'L23'] contexts=['', 'call']
  - app_main -> ui_core_adapter_coreadapter edges=2 relations=['calls', 'uses'] locations=['L215'] contexts=['', 'call']
note: normal graph.json is post-build; raw producer loss must be measured earlier.

Final graph:
[graphify] MultiDiGraph edge-collapse diagnostic
input: <in-memory>
input_stage: provided JSON (normal graph.json is post-build)
effective_directed: <direct-call>
nodes: 275
unverified_code_nodes: 0
raw_edges: 527
valid_candidate_edges: 527
missing_endpoint_edges: 0
dangling_endpoint_edges: 0
external_reference_edges: 0
self_loop_edges: 0
exact_duplicate_edges: 0
directed_unique_endpoint_pairs: 527
directed_same_endpoint_collapsed_edges: 0
undirected_unique_endpoint_pairs: 527
undirected_same_endpoint_collapsed_edges: 0
same_endpoint_group_count: 0
relation_variant_groups: 0
source_file_variant_groups: 0
source_location_variant_groups: 0
context_variant_groups: 0
post_build_graph_type: Graph
post_build_edges: 527
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
Import stub names: argparse, collections, contextvars, copy, core, csv, datetime, hashlib, html, importlib, io, json, logging, os, pathlib, playwright_sync_api, queue, re, streamlit, streamlit_testing_v1, tempfile, threading, time, types, ui, unittest, unittest_mock, urllib_request, uuid
