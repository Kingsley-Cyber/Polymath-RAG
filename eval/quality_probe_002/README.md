# QUALITY-PROBE-002 — probe rerun in FULL trace mode (same semantic config)

Run: run_efea51cb4dfc35694f53ab8d7ac3aa536314e347d8c1e77be63dcadd98a51233,
corpus quality-probe-002, 159 trace events (extraction-observability-v1).

AUTOMATIC EXPLANATION (from runtime traces, no source archaeology):

"A robust implementation uses bounded leases, deterministic stage
contracts, and transactional claim operations." (sentence 8c57fbc:19)

- trigger 'uses' FIRED (plus nominal 'implementation')
- binding: left_candidates=0, right_candidates=1
- FIRST LOSS: argument_binding / SUBJECT_ENDPOINT_UNAVAILABLE
- CAUSE (joined with the rule pack): "robust implementation" was
  proposed by GLiNER as Technology (0.773) and admitted CORPUS_SCOPED,
  but no uses-signature accepts a Technology subject
  (subject_core = Person/Organization/Method/Process/Product) — the
  slot-compatibility filter excluded it from the subject slot.
- objects: "bounded leases" (Technology) is a legal uses-object;
  "deterministic stage contracts" (Document) and "transactional claim
  operations" (Process) are not in any object_core for the class.

The ten probe surfaces are traceable via
`python scripts/trace_report.py surface <run_id> "<surface>"`.
