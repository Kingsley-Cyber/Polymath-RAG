---
title: "WORK LOG — B3 CORPUS-SHAPE proposal: where the owner's handbook should live, and how books stop competing with it"
change_id: CORPUS-SHAPE-PROPOSAL
date: 2026-09-06
owner: governance (owner backlog B3, released 2026-09-06 as a proposal — "implement only what the owner picks")
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.119
package: docs only (this proposal); no code
architecture_impact: "None until the owner picks. Three shapes are costed against one day of receipts: (A) the handbook in its own corpus (chat scope = books OR handbook; both when asked); (B) a document-kind tag (book / paper / manual / handbook) on the document profile with a scope filter in the UI; (C) leave as is and rely on document-fair judging (B11) plus the ADJACENT aspect (B9)."
---

# WORK LOG — B3 CORPUS-SHAPE proposal

## Contract

The owner chooses with the numbers in front of them; nothing moves in the corpus until then.

## Changes

None — this is a proposal; the corpus and the code are untouched until the owner picks a shape.

## Proof

### The competition, measured

514 cinema chat turns on 2026-09-06 (every UI turn with a funnel receipt: the owner's tests, the probes, the baselines). Counts are candidates, not turns; survival = final ÷ union; cited share = cited ÷ final.

| document | sections | union candidates | judged | final | cited | survival union → final | cited share of final |
|---|---|---|---|---|---|---|---|
| Digital Compositing for Film and Video.md | 540 | 6863 | 1792 | 1182 | 891 | 0.172 | 0.754 |
| VES Handbook of Visual Effects.md | 1322 | 3232 | 863 | 568 | 346 | 0.176 | 0.609 |
| The Art and Science of Digital Compositing.m | 389 | 3221 | 1029 | 704 | 546 | 0.219 | 0.776 |
| handbook.html | 802 | 3127 | 797 | 465 | 257 | 0.149 | 0.553 |
| Grammar of the Edit.md | 209 | 1782 | 692 | 298 | 147 | 0.167 | 0.493 |
| Scoppettuolo & Saccone - The Definitive Guid | 221 | 1735 | 439 | 245 | 170 | 0.141 | 0.694 |
| Paul Ekman - Facial Action Coding System Man | 323 | 1574 | 296 | 194 | 16 | 0.123 | 0.082 |
| Facial Action Coding System_ Facial action c | 331 | 1459 | 241 | 130 | 22 | 0.089 | 0.169 |
| Hey Whipple Squeeze This.md | 469 | 1387 | 397 | 287 | 201 | 0.207 | 0.7 |
| Ken Dancyger - The technique of film & video | 431 | 1292 | 326 | 161 | 129 | 0.125 | 0.801 |
| Bruce Block - The Visual Story (2007).md | 303 | 1226 | 415 | 236 | 171 | 0.192 | 0.725 |
| Michael Rabiger, Mick Hurbis-Cherrier - Dire | 670 | 1190 | 343 | 206 | 102 | 0.173 | 0.495 |
| Blain Brown - Cinematography - Theory and Pr | 264 | 1071 | 320 | 168 | 75 | 0.157 | 0.446 |
| Myers, Isabel Briggs_Myers, Peter B - Gifts  | 136 | 887 | 259 | 189 | 92 | 0.213 | 0.487 |
| Fight Choreography The Art of Non-Verbal Dia | 423 | 884 | 182 | 130 | 56 | 0.147 | 0.431 |
| The Screen Combat Handbook A Practical Guide | 258 | 831 | 235 | 144 | 75 | 0.173 | 0.521 |

Reading: the handbook is the fourth-largest source of union candidates (3,127) and the model cites its final rows less often than the books' (0.55 vs 0.60–0.80): it reaches the prompt a lot and earns less. The two FACS manuals reach the final set often and are almost never cited (0.08 / 0.17): they fit few questions as evidence. Size drives union presence (the VES Handbook's 1,322 sections vs a book's ~250) but not survival: survival is flat at 0.12–0.22 across sizes, which is the judge doing its job.

### The three shapes

**A. The handbook in its own corpus.** One API call per document move (or delete + re-ingest into `handbook`). "What do the books say" then means books; handbook questions go to the handbook corpus; a question that wants both needs a two-corpus scope (the chat UI selects one corpus today; `/chat` accepts several for HYBRID, so the UI is the only gap). Cost: a small UI change for multi-select, or two chats. Effect on today's numbers: the handbook's 3,127 union candidates and 465 final rows leave the books' turns entirely.

**B. A document-kind tag with a scope filter.** `documents.profile.kind ∈ {book, paper, manual, handbook}` set once per document (the list the owner already wrote by hand is the seed), a `kinds` filter in the retrieval scope and a chip in the UI (books only / everything / handbook only). Cost: a profile field + a filter in the candidate lanes + a chip; no re-ingest. Effect: books-only by default for "the books" questions; the FACS manuals and the papers stay reachable when asked (the movement and face questions need them).

**C. Leave the corpus as is.** Rely on document-fair judging (B11) and the ADJACENT aspect (B9) to keep the handbook from crowding, and read the handbook's rows as what they are. Cost: nothing. Effect: today's picture continues — the handbook wins 15 % of union candidates on fight questions and its rows are cited 55 % of the time.

### Recommendation

**B is the durable answer** and is what the owner asked for in words ("increase breadth at the document level in a fair manner"): kind is metadata the owner already knows for every document, the filter is a retrieval-scope change (not ingestion), and it also resolves the manuals-and-papers question the owner raised. **A is the quick win** if the owner wants the books clean today; it needs the multi-corpus scope in the UI to keep "both" possible. C is the status quo, now measured. Implementation of B: profile field + backfill from the owner's list, `kinds` in the scope resolver and the lane filters, receipts, a UI chip; gate = the same 10-question probe books-only vs everything with no citation-precision change.

## Rejected claims

- "Delete the handbook from cinema" — rejected: it is the owner's own synthesis of the books and the thing several questions are about; the question is scope, not existence.

## Open contract gaps

- Multi-corpus scope in the chat UI is single-select today; option A needs a "books + handbook" scope or two chats.
