"""JSON-grammar logits masking for the local extraction lane.

STATUS (2026-08-30, end of session): EXPERIMENTAL — env-gated OFF
(POLYMATH_JSON_MASK=off in the sidecar env). Proven working: incremental
O(1) tracker (parity 0 fails), predicate enum trie with the on-trie rule
(emitted CONSTRAINED_BY under hard constraint), EOS gating (legal only at
S_DONE — everywhere-exempt let the model stop mid-object; never-exempt
made it flood '}'). Remaining failure class that parked it: the 4B emits
shape-legal-but-schema-illegal JSON the permissive grammar cannot see
(measured: relations:[[ {...},] ] — nested array + trailing comma). The
fix is SCHEMA-aware masking (typed arrays per key), which is a compiled
grammar's job (xgrammar in an isolated venv) or a schema-specialized
state machine — not more permissive-grammar patches. Quality today rides
on prompts + gate (cloud fallbacks 0.7%).

A permissive-JSON state machine (the extraction grammar's structure:
objects, arrays, strings, numbers, literals — string CONTENTS stay free)
compiled to per-state token bitmasks over each token's DECODED TEXT.
At each decode step the generated prefix is parsed to its state and
logits for clearly-illegal tokens are set to -inf.

Bias: PERMISSIVE. Ambiguous tokens stay allowed; only clearly illegal
continuations are masked. The sanitize->validate gate still enforces the
full contract after generation. (First-char checks on raw BPE pieces
over-masked — pieces carry space glyphs — and drove the model into
degeneration; measured 2026-08-30.)

Usage (batch_generate):
    mask = make_json_mask(tokenizer)
    processors = make_logits_processors(...) + [mask]
"""
from __future__ import annotations

import re

import numpy as np

S_START, S_OBJ, S_KEY, S_COLON, S_VALUE, S_ARR, S_STR_BODY, S_STR_ESC = range(8)
S_KEY_BODY, S_KEY_ESC, S_NUM, S_LIT, S_DONE = range(8, 13)

_WS = r"\s*"
_PATTERNS: dict[int, re.Pattern] = {
    S_START: re.compile(_WS + r"\{"),
    S_KEY: re.compile(_WS + r'["}]'),
    S_COLON: re.compile(_WS + r":"),
    S_VALUE: re.compile(_WS + r'[\{"\[0-9\-tfn]'),
    S_OBJ: re.compile(_WS + r"[,}]"),
    S_ARR: re.compile(_WS + r"[,\]]"),
    S_NUM: re.compile(r"[0-9eE+\-.\s,}\]]*$"),
    S_LIT: re.compile(r"[a-z\s,}\]]*$"),
    S_DONE: re.compile(r"\s*$"),
}
_FREE_STATES = (S_STR_BODY, S_KEY_BODY, S_STR_ESC, S_KEY_ESC)


# Enum trie: tokens that are PREFIXES of legal enum ids (the predicate
# field may only continue toward one of the 18 ids — anything else is
# masked while the state machine is inside the predicate string).
from polymath_shared.llm_extraction.ontology import RELATION_ONTOLOGY  # noqa: E402


class JsonGrammarMask:
    def __init__(self, tokenizer) -> None:
        self.tok = tokenizer
        self._cache: dict[tuple[int, int], np.ndarray] = {}
        # token_context includes the PROMPT; the grammar applies only to
        # the generated suffix. First processor call per sequence happens
        # at prefill (0 generated) — capture that length as the prompt
        # length, keyed by the sequence's first tokens.
        self._prompt_lens: dict[tuple, int] = {}
        # INCREMENTAL STATE (2026-08-30 perf fix): per-sequence grammar
        # state + buffer, advanced by only the NEWLY SAMPLED token each
        # step — O(1) per step instead of re-parsing the prefix (the
        # re-parse was quadratic at batch scale: 15-min batches).
        self._seq_state: dict[tuple, list] = {}   # key -> [state, buf]
        self._allowed_masks = self._compile()
        self._stop = self._stop_ids()
        self._enum_mask_cache: dict[int, np.ndarray] = {}

    # -- compile per-state allowed-token bitmasks once -------------------

    def _compile(self) -> dict[int, np.ndarray]:
        try:
            vocab_size = len(self.tok)
        except TypeError:
            vocab_size = len(self.tok.get_vocab())
        ids = list(range(vocab_size))
        texts: list[str] = []
        CH = 4096
        for i in range(0, len(ids), CH):
            texts.extend(self.tok.batch_decode(
                [[j] for j in ids[i:i + CH]], skip_special_tokens=False))
        masks: dict[int, np.ndarray] = {}
        for state, pat in _PATTERNS.items():
            allowed = np.zeros(vocab_size, dtype=bool)
            free = state in _FREE_STATES
            for idx, text in enumerate(texts):
                if not text:
                    continue
                if free or pat.match(text):
                    allowed[idx] = True
            masks[state] = allowed
        self._texts = texts
        self._tok_vocab = len(self.tok.get_vocab())
        self._enum_ids = sorted(set(list(RELATION_ONTOLOGY)
                                    + [p.lower() for p in RELATION_ONTOLOGY]))
        return masks

    def _stop_ids(self) -> list[int]:
        """EOS/stop token ids — NEVER masked (measured 2026-08-30: masking
        them made stopping impossible; '}' soup buried valid JSON)."""
        ids: list[int] = []
        v = getattr(self.tok, "eos_token_ids", None)
        if v:
            ids.extend(int(x) for x in v)
        if not ids:
            v = getattr(self.tok, "eos_token_id", None)
            if v is not None:
                ids.append(int(v))
        return ids

    # -- incremental char feeder (O(1) per token) -------------------------
    # The state machine as a class: feed chars as they are sampled, no
    # re-parsing. `_state_for` is retained for tests/offline use.

    class _Tracker:
        __slots__ = ("state", "stack", "in_str", "in_key", "esc",
                     "last_key", "pred_open", "pred_buf")

        def __init__(self) -> None:
            self.state = S_START
            self.stack: list[tuple[str, str]] = []
            self.in_str = False
            self.in_key = False
            self.esc = False
            self.last_key = ""
            self.pred_open = False   # inside a STRING that is a predicate value
            self.pred_buf = ""       # body chars of the current predicate string

        def feed(self, ch: str) -> None:
            st = self.state
            if self.in_str:
                if self.esc:            # escaped char: part of the body
                    self.esc = False
                    if self.in_key:
                        self.last_key += ch
                    return
                if ch == "\\":         # escape marker: not body
                    self.esc = True
                    return
                if self.pred_open:
                    self.pred_buf += ch
                if ch != '"' and self.in_key:   # quote handled below
                    self.last_key += ch
                if ch == '"':
                    self.in_str = False
                    self.pred_open = False
                    if self.in_key:
                        self.last_key = self.last_key.strip()
                        if self.stack:
                            self.stack[-1] = (self.stack[-1][0], "colon")
                        self.state = S_COLON
                    else:
                        if self.stack:
                            self.stack[-1] = (self.stack[-1][0], "after")
                        self.state = (S_ARR if self.stack
                                      and self.stack[-1][0] == "[" else S_OBJ)
                        self.in_key = False
                    return
                return  # string body: no state change
            if ch == '"':
                self.in_str = True
                self.in_key = bool(self.stack) and self.stack[-1][0] == "{" \
                    and self.stack[-1][1] == "key"
                if self.in_key:
                    self.last_key = ""
                if not self.in_key:
                    # a VALUE string — predicate only if the last key was
                    # exactly "predicate"
                    self.pred_open = self.last_key == "predicate"
                    self.pred_buf = ""
                self.state = S_KEY_BODY if self.in_key else S_STR_BODY
                return
            if ch in "{[":
                self.stack.append((ch, "key" if ch == "{" else "value"))
                self.state = S_KEY if ch == "{" else S_VALUE
                return
            if ch in "}]":
                if self.stack:
                    self.stack.pop()
                if not self.stack:
                    self.state = S_DONE
                elif self.stack[-1][1] in ("after", "value"):
                    self.state = S_ARR if self.stack[-1][0] == "[" else S_OBJ
                else:
                    self.state = S_KEY
                return
            if ch == ":":
                if self.stack:
                    self.stack[-1] = (self.stack[-1][0], "value")
                self.state = S_VALUE
                return
            if ch == ",":
                if self.stack:
                    self.stack[-1] = (self.stack[-1][0],
                                      "key" if self.stack[-1][0] == "{" else "value")
                self.state = S_KEY if (self.stack and self.stack[-1][0] == "{") else S_ARR
                return
            if ch.isdigit() or ch == "-" or (ch in ".eE+-" and st == S_NUM):
                self.state = S_NUM
                if self.stack:
                    self.stack[-1] = (self.stack[-1][0], "after")
                return
            if ch.isalpha():
                self.state = S_LIT
                if self.stack:
                    self.stack[-1] = (self.stack[-1][0], "after")
                return

    @staticmethod
    def _state_for(prefix: str) -> int:
        """Parse a partial-JSON prefix to its grammar state. The stack
        carries (container, phase): phase in key | colon | value | after."""
        stack: list[tuple[str, str]] = []
        in_str = in_key = esc = False
        state = S_START
        for ch in prefix:
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                    if in_key:
                        stack[-1] = (stack[-1][0], "colon")
                        state = S_COLON
                    else:
                        if stack:
                            stack[-1] = (stack[-1][0], "after")
                        state = S_ARR if stack and stack[-1][0] == "[" else S_OBJ
                continue
            if ch == '"':
                in_str = True
                in_key = bool(stack) and stack[-1][0] == "{" and stack[-1][1] == "key"
                state = S_KEY_BODY if in_key else S_STR_BODY
                continue
            if ch in "{[":
                stack.append((ch, "key" if ch == "{" else "value"))
                state = S_KEY if ch == "{" else S_VALUE
                continue
            if ch in "}]":
                if stack:
                    stack.pop()
                if not stack:
                    state = S_DONE
                elif stack[-1][1] in ("after", "value"):
                    state = S_ARR if stack[-1][0] == "[" else S_OBJ
                else:
                    state = S_KEY
                continue
            if ch == ":":
                if stack:
                    stack[-1] = (stack[-1][0], "value")
                state = S_VALUE
                continue
            if ch == ",":
                if stack:
                    stack[-1] = (stack[-1][0],
                                 "key" if stack[-1][0] == "{" else "value")
                state = S_KEY if (stack and stack[-1][0] == "{") else S_ARR
                continue
            if ch.isdigit() or ch == "-" or (ch in ".eE+-" and state == S_NUM):
                state = S_NUM
                if stack:
                    stack[-1] = (stack[-1][0], "after")
                continue
            if ch.isalpha():
                state = S_LIT
                if stack:
                    stack[-1] = (stack[-1][0], "after")
                continue
        if in_str:
            return S_KEY_BODY if in_key else S_STR_BODY
        return state

    # -- the logits processor --------------------------------------------

    def _enum_allowed_cont(self, buf: str, width: int) -> np.ndarray:
        """Tokens legal to continue a predicate string whose body so far
        is `buf` (an on-trie prefix): next-char prefixes of the remaining
        ids, the closing quote when buf IS a complete id, nothing else."""
        key = (buf, width)
        m = self._enum_mask_cache.get(key)
        if m is not None:
            return m
        allowed = np.zeros(width, dtype=bool)
        conts: set[str] = set()
        for e in self._enum_ids:
            if e.startswith(buf) and len(e) > len(buf):
                conts.add(e[len(buf):len(buf) + 8])   # any continuation
        # token-level: decode text must extend toward some id
        for idx, text in enumerate(self._texts):
            if not text:
                continue
            if any(e.startswith(buf + text) for e in self._enum_ids):
                allowed[idx] = True
        if buf in self._enum_ids:
            # the string may close now
            for idx, text in enumerate(self._texts):
                if text.startswith('"'):
                    allowed[idx] = True
                    break
        self._enum_mask_cache[key] = allowed
        return allowed

    def processor(self, tokens, logits):
        """mlx_lm logits_processor signature: (mx tokens, mx logits) -> logits.
        INCREMENTAL: advance the per-sequence tracker by only the NEW
        token (O(1)); mask structurally-illegal tokens, and inside a
        predicate string mask to the enum trie."""
        import mlx.core as mx
        is_mx = isinstance(logits, mx.array)
        ids = tokens.tolist() if hasattr(tokens, "tolist") else [int(t) for t in tokens]
        key = tuple(ids[:16])
        pl = self._prompt_lens.get(key)
        if pl is None or len(ids) < pl:
            pl = len(ids)
            self._prompt_lens[key] = pl
            if len(self._prompt_lens) > 8192:
                self._prompt_lens.clear()
        gen = ids[pl:]
        seq = self._seq_state.get(key)
        if seq is None:
            seq = [JsonGrammarMask._Tracker(), 0]   # [tracker, consumed]
            self._seq_state[key] = seq
            if len(self._seq_state) > 8192:
                self._seq_state.clear()
                seq = [JsonGrammarMask._Tracker(), 0]
                self._seq_state[key] = seq
        tracker, consumed = seq
        if len(gen) > consumed:
            # advance by decoding ONLY the new tokens (O(1) per step)
            chunk = self.tok.decode(gen[consumed:], skip_special_tokens=True)
            for ch in chunk:
                tracker.feed(ch)
            seq[1] = len(gen)
        state = tracker.state
        # PREDICATE ENUM enforcement with the ON-TRIE rule (measured
        # 2026-08-30): constrain ONLY while the predicate-so-far is a
        # legal prefix of some enum id. A model that drifted off-trie
        # before the mask engaged would otherwise be boxed into a
        # near-empty legal set and degenerate (whitespace/letter soup);
        # off-trie strings complete freely and the gate normalizes them,
        # exactly as before the mask existed.
        if tracker.in_str and tracker.pred_open:
            enum_ids = self._enum_ids
            buf = tracker.pred_buf
            on_trie = any(e.startswith(buf) for e in enum_ids)
            if on_trie:
                allowed = self._enum_allowed_cont(buf, logits.shape[-1])
                return self._apply(allowed, logits, is_mx)
            return logits  # drifted: free completion, gate handles
        allowed = self._allowed_masks.get(state)
        if allowed is None or bool(allowed.all()):
            return logits
        return self._apply(allowed, logits, is_mx, state)

    def _apply(self, allowed, logits, is_mx, state: int | None = None) -> None:
        import mlx.core as mx
        width = logits.shape[-1]
        key = (id(allowed), width, state)
        m = self._cache.get(key)
        if m is None:
            m = ~allowed
            if width != len(m):
                pad = np.ones(width, dtype=bool)
                pad[:len(m)] = m
                m = pad
            # EOS legal ONLY at grammar-accepting states: everywhere-exempt
            # let the model stop mid-object (measured); never-exempt made
            # it flood '}' soup. At S_DONE the mask is whitespace+EOS only.
            if state == S_DONE:
                m[self._stop] = False
            self._cache[key] = m
        if is_mx:
            mx_m = mx.array(m)
            neg = mx.full(logits.shape, float("-inf"))
            if logits.ndim == 2:
                mx_m = mx_m[None, :]
            return mx.where(mx_m, neg, logits)
        logits[m] = float("-inf")
        return logits


def make_json_mask(tokenizer):
    """Compile the grammar mask; returns the processor or None on any
    failure (fail-open: prompt + gate enforcement still apply)."""
    try:
        return JsonGrammarMask(tokenizer).processor
    except Exception:
        return None
