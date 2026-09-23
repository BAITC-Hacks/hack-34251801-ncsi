# Localized raw extraction

[graphify] MultiDiGraph edge-collapse diagnostic
input: <in-memory>
input_stage: provided JSON (normal graph.json is post-build)
effective_directed: <direct-call>
nodes: 161
unverified_code_nodes: 0
raw_edges: 492
valid_candidate_edges: 369
missing_endpoint_edges: 0
dangling_endpoint_edges: 123
external_reference_edges: 0
self_loop_edges: 0
exact_duplicate_edges: 0
directed_unique_endpoint_pairs: 363
directed_same_endpoint_collapsed_edges: 6
undirected_unique_endpoint_pairs: 363
undirected_same_endpoint_collapsed_edges: 6
same_endpoint_group_count: 6
relation_variant_groups: 6
source_file_variant_groups: 0
source_location_variant_groups: 0
context_variant_groups: 0
post_build_graph_type: Graph
post_build_edges: 421
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
  - app_import_data -> app_import_data_save edges=2 relations=['contains', 'indirect_call'] locations=['L223', 'L237'] contexts=['', 'argument']
  - auth_checks_test_service_authservicetests_test_automatic_login_returns_latest_role_changed_while_hashing -> auth_checks_test_service_authservicetests_test_automatic_login_returns_latest_role_changed_while_hashing_hash_then_change_role edges=2 relations=['contains', 'indirect_call'] locations=['L112', 'L117'] contexts=['', 'argument']
  - auth_checks_test_service_authservicetests_test_concurrent_duplicate_signup_creates_exactly_one_account -> auth_checks_test_service_authservicetests_test_concurrent_duplicate_signup_creates_exactly_one_account_attempt edges=2 relations=['contains', 'indirect_call'] locations=['L229', 'L235'] contexts=['', 'argument']
  - app_main -> auth_service_authservice edges=2 relations=['calls', 'uses'] locations=['L317'] contexts=['', 'call']
  - auth_ui_render_auth -> auth_service_authservice edges=2 relations=['calls', 'uses'] locations=['L95'] contexts=['', 'call']
note: normal graph.json is post-build; raw producer loss must be measured earlier.

# Final merged graph

[graphify] MultiDiGraph edge-collapse diagnostic
input: <in-memory>
input_stage: provided JSON (normal graph.json is post-build)
effective_directed: <direct-call>
nodes: 970
unverified_code_nodes: 0
raw_edges: 2532
valid_candidate_edges: 2532
missing_endpoint_edges: 0
dangling_endpoint_edges: 0
external_reference_edges: 0
self_loop_edges: 0
exact_duplicate_edges: 0
directed_unique_endpoint_pairs: 2532
directed_same_endpoint_collapsed_edges: 0
undirected_unique_endpoint_pairs: 2532
undirected_same_endpoint_collapsed_edges: 0
same_endpoint_group_count: 0
relation_variant_groups: 0
source_file_variant_groups: 0
source_location_variant_groups: 0
context_variant_groups: 0
post_build_graph_type: Graph
post_build_edges: 2532
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
Raw references may point to unchanged nodes; final endpoints and hyperedge members all resolve.
