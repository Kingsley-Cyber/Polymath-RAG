# unit: orchestrator/orchestrator/api/reasoning.py
anchor: orchestrator/orchestrator/api/reasoning.py:1-169

## purpose
Chat-layer reasoning-mode prompt prefixer for the polymath v4 orchestrator API. Verbatim prompt-only port of v3.3 `backend/services/reasoning.py` (Phase 15, ported 2026-08-27): each mode maps to a text template prepended to the generation prompt (reasoning.py:1-8, 153-169). Does not mutate the contract-frozen v4 retrieval pipeline (reasoning.py:5-8). Imported by `orchestrator/orchestrator/api/ui.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `ReasoningMode` | class (`str, Enum`) | 13 members: `NONE`, `STEP_BY_STEP`, `BRANCHING`, `CREATIVE`, `ANALYTICAL`, `SELF_CORRECT`, `ATOMIC`, `PLANNING`, `GRAPH_REASON`, `DEBATE`, `DEEP_RESEARCH`, `CONCISE`, `META` | reasoning.py:14-27 | orchestrator/orchestrator/api/ui.py (module import) |
| `REASONING_TEMPLATES` | constant | `dict[str, str]` — 1 `"none"` + 11 curated + 40 raw keys | reasoning.py:30-146 | — |
| `CURATED_MODES` | constant | `list[str]` = `[m.value for m in ReasoningMode]` (v3.3 primary dropdown set) | reasoning.py:149-150 | — |
| `apply_reasoning` | def | `(prompt: str, mode: str | None = "none", blend: list[str] | None = None) -> str` | reasoning.py:153-169 | orchestrator/orchestrator/api/ui.py (module import) |

## contracts
`apply_reasoning` (reasoning.py:153-169)
- in: `prompt: str`; `mode` default `"none"`; `blend` default `None` (reasoning.py:153-154).
- pre: none enforced. Unknown mode/blend keys are legal — resolved via `REASONING_TEMPLATES.get(key, "")` (reasoning.py:160, 164).
- post: returns `"".join(parts) + prompt`; `parts` = templates of `blend` in list order, then template of `mode` if `mode` is truthy and `!= "none"` (reasoning.py:157-166, 169).
- post: if `parts` is empty (all keys unknown / `"none"` / `None` mode), returns `prompt` unchanged (reasoning.py:167-168).
- ordering is declared "verbatim v3.3 semantics": blend parts first, then main mode, then prompt (reasoning.py:155-158).

`ReasoningMode` (reasoning.py:14-27)
- str-Enum; each `.value` is a key into `REASONING_TEMPLATES`; `CURATED_MODES` is derived, not hand-listed (reasoning.py:150).

## effect surface
None. `tables_read`/`tables_written` are empty (FACTS); no files, network, subprocess, or env flags appear anywhere in the unit — pure in-process string construction (reasoning.py:153-169).

## invariants
INVARIANT: len(CURATED_MODES) = 13 = len(ReasoningMode members) — reasoning.py:14-27, 150 [DERIVED]
  fails-if: adding an enum member auto-extends the UI dropdown; without a matching template key the new mode is a silent no-op (see flags).
INVARIANT: non-`"none"` ReasoningMode values (12) − curated template keys (11) = {"atomic"} — reasoning.py:15-27 vs 31-95 [DERIVED]
  fails-if: selecting `ATOMIC` in the dropdown prepends nothing.
INVARIANT: raw template keys = 40 = comment "40 raw modes (power-user blend pool)" — reasoning.py:96-146 [DERIVED]
  fails-if: comment/pool drift misleads blend users about available keys.
INVARIANT: every non-empty template value ends `"\n\n"` (blank line before user prompt) — reasoning.py:31-146 [DERIVED]
  fails-if: concatenated prompt loses separation from the user's text.

## determinism & idempotency
determinism: DETERMINISTIC (pure dict lookups + string concatenation, reasoning.py:157-169; no clock/random/uuid/network/db/env reads in the file)
idempotency: SAFE — no side effects, pure function (reasoning.py:153-169). Not repetition-safe as a text transform: feeding its output back as `prompt` prepends templates again [INFERRED — same code path re-runs].

## failure behaviour
No exceptions raised. Unknown mode or blend keys silently resolve to `""` via `REASONING_TEMPLATES.get(key, "")` (reasoning.py:160, 164) and are dropped; if nothing matches, the caller receives `prompt` unchanged (reasoning.py:167-168). No FACTS fallbacks.

## dumb-code flags
- `ReasoningMode.ATOMIC = "atomic"` (reasoning.py:21) has no `"atomic"` key in `REASONING_TEMPLATES` — closest raw key is `"atomic_thoughts"` (reasoning.py:102). `apply_reasoning(p, "atomic")` returns `p` unchanged (get→`""` at reasoning.py:164, empty `parts` at reasoning.py:167). Contradicts the module docstring claiming v3.3's `atomic` mode "act[s] as prompt-only templates here" (reasoning.py:6-7).
- Comment says "12 curated modes" (reasoning.py:32) but only 11 curated (non-`"none"`, non-raw) template keys exist — the 12th (`atomic`) is enum-only (reasoning.py:31-95 vs 15-27).
- Mode-name strings duplicated between enum values (reasoning.py:15-27) and dict keys (reasoning.py:31-95); no cross-check — renaming one side silently yields empty templates via the `.get` default.
- Silent-ignore defaults: `.get(key, "")` at reasoning.py:160 and 164 make any typo'd blend/mode key a no-op with no signal to the caller.

## refactor notes
- Importer blast radius: `orchestrator/orchestrator/api/ui.py` imports this module (FACTS.importers); renaming `apply_reasoning`, `ReasoningMode`, `CURATED_MODES`, or `REASONING_TEMPLATES` breaks it.
- Output ordering (blend → mode → prompt) is declared verbatim v3.3 semantics (reasoning.py:155-158, 157-169); reordering changes every generated prompt.
- Prompt-only contract: v4's retrieval pipeline is contract-frozen and must not be mutated by this chat-layer flag (reasoning.py:5-8).
- Any template text edit (reasoning.py:30-146) changes the system-level prompt reaching the model for every ui.py user.
- Adding an enum member without a template key produces a silently dead mode — pair every new `ReasoningMode` value with a `REASONING_TEMPLATES` key (reasoning.py:14-27, 30-146).

## VERIFY
```verify
grep -Fq 'class ReasoningMode(str, Enum):' orchestrator/orchestrator/api/reasoning.py
grep -Fq 'def apply_reasoning(prompt: str, mode: str | None = "none",' orchestrator/orchestrator/api/reasoning.py
grep -Fq 'CURATED_MODES = [m.value for m in ReasoningMode]' orchestrator/orchestrator/api/reasoning.py
grep -Fq 'return "".join(parts) + prompt' orchestrator/orchestrator/api/reasoning.py
! grep -Fq '"atomic":' orchestrator/orchestrator/api/reasoning.py
test "$(grep -c -F 'ReasoningMode' orchestrator/orchestrator/api/reasoning.py)" -ge 2
```
