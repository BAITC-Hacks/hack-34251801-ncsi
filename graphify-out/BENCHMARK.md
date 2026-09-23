# Graphify benchmark

Installed Graphify 0.9.66 reports the following estimates for this build:

```text
Corpus:          13,750 words → ~18,333 tokens (naive)
Graph:           275 nodes, 527 edges
Avg query cost:  ~3,504 tokens
Reduction:       5.2x fewer tokens per query

Per question:
  [4.3x] what is the main entry point
  [5.4x] how are errors handled
  [14.3x] what connects the data layer to the api
  [3.6x] what are the core abstractions
```

Graphify's 13,750-word benchmark baseline differs from the detected corpus of
35,712 words including dataset JSON. These are estimates for built-in questions,
not measured model billing or proven savings for every question. Actual host
model token usage is unavailable.
