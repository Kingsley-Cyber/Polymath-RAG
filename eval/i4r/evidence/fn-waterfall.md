# I4R combined — remaining-FN waterfall (14 FN, frozen I4, final config)

Attribution per the staged-I4R STOP directive (mechanism → measurement →
attribution → next mechanism). Sources: fn_details (frozen gold),
mentions (raw_label/pass_kind), merged compiler audit, emitted facts.

## A. Frozen-threshold rescue/boundary refusals — 5/14 (dominant)

GLiNER refuses the NP (or the expanded span) at identity labels + 0.5,
so the argument stays contracted/unbound or surface-variant:
1. developed Crestline Automation → Cobalt assembly cell (emitted as
   "crestline" — surface variant; boundary rescue refused)
2. depends_on Mentor assessment engine → QBank (emitted as
   "mentor engine" — surface variant)
3. part_of Nimbus billing service → Nimbus Cloud platform (both
   endpoints refused)
4. located_in Crestline plant → Toledo (rescue refused)
5. created engineering group → load-testing harness (rescue refused)
Lever: GLINER-QUERY-VOCAB-v2 (versioned alias policy — probe evidence:
"Crestline Automation" accepts under "Company" at 0.821, refuses under
"Organization"; experiment 0005). The temporal architecture exists for
exactly this. No evaluator change.

## B. Markdown header-merged sentences — 4/14

"### Title: Subtitle Body-first-sentence." merges the heading into the
first body sentence (sentence slicer keeps the "###" line), breaking
trigger localization/pairing:
6. uses Northvale → CareChart EMR (system emitted a different true
   fact: depends_on careconnect → carechart)
7. uses Nimbus Cloud → Kubernetes (no fact)
8. uses Brightpath → Mentor assessment engine (system emitted
   depends_on mentor engine → qbank instead)
9. located_in Brightpath → Raleigh (no fact)
Lever: sentence slicing drops heading lines (general pre-extraction
cleanup; the I4R-A audit already flagged "### Brightpath Learning"
residue in NPs).

## C. Raw GLiNER discovery misses — 3/14

No proposal and no successful rescue for the endpoint:
10. part_of radiology review board → Lakeshore General
11. created analytics team → shift scheduling model
12. associated_with vision system → quality database
Lever: none inside the current frozen posture (new model/labels need
qualification evidence — separate gate).

## D. Binding / scope — 2/14

13. associated_with QuickScale → FreightNet:
    binding:trigger_outside_endpoint_span
14. acquired Brightpath → Coachlight: scope_gate:negated (the compiler
    read the sentence as negated; gold lists it supported — a
    gold/text tension worth an I5 authoring note, NOT an evaluator edit)

## Implication

Recall bar needs ~19/26 TP (R >= 0.70); current 12. Fixing A+B
generalistically would recover up to 9 (ceiling ~0.81). C requires a
model/vocabulary gate; D needs binding-rule work or gold authoring
review. Frame arbitration (D-sub-gate) cannot move recall — confirmed.
