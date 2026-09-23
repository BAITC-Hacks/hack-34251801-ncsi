# Graphify benchmark


graphify token reduction benchmark
──────────────────────────────────────────────────
  Corpus:          20,750 words → ~27,666 tokens (naive)
  Graph:           415 nodes, 955 edges
  Avg query cost:  ~4,233 tokens
  Reduction:       6.5x fewer tokens per query

  Per question:
    [7.7x] what is the main entry point
    [4.5x] how are errors handled
    [17.7x] what connects the data layer to the api
    [4.9x] what are the core abstractions


These are deterministic Graphify estimates for built-in questions, not measured API billing. The baseline may omit raw dataset records. Host-session token usage is unavailable.
