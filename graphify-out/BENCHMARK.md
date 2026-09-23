# Historical Graphify benchmark

Measured before the incoming authentication/storage merge (730 nodes). Not rerun during final delivery; current graph statistics are in VALIDATION.json.


graphify token reduction benchmark
──────────────────────────────────────────────────
  Corpus:          36,500 words → ~48,666 tokens (naive)
  Graph:           730 nodes, 1,835 edges
  Avg query cost:  ~5,756 tokens
  Reduction:       8.5x fewer tokens per query

  Per question:
    [25.7x] how does authentication work
    [11.0x] what is the main entry point
    [4.6x] how are errors handled
    [10.2x] what connects the data layer to the api
    [6.8x] what are the core abstractions


These are deterministic Graphify estimates, not measured API billing. The baseline excludes raw dataset records that have no semantic entities. Host-session token usage is unavailable.
