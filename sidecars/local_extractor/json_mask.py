"""JSON-grammar logits masking for the local extraction lane.

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
    S_DONE: re.compile(r"[\s,}\]]*$"),
}
_FREE_STATES = (S_STR_BODY, S_KEY_BODY, S_STR_ESC, S_KEY_ESC)


class JsonGrammarMask:
    def __init__(self, tokenizer) -> None:
        self.tok = tokenizer
        self._cache: dict[tuple[int, int], np.ndarray] = {}
        # token_context includes the PROMPT; the grammar applies only to
        # the generated suffix. First processor call per sequence happens
        # at prefill (0 generated) — capture that length as the prompt
        # length, keyed by the sequence's first tokens.
        self._prompt_lens: dict[tuple, int] = {}
        self._allowed_masks = self._compile()

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
        return masks

    # -- prefix -> state -------------------------------------------------

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

    def processor(self, tokens, logits):
        """mlx_lm logits_processor signature: (mx tokens, mx logits) -> logits."""
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
        if not gen:
            state_allowed = self._allowed_masks.get(S_START)
            width = logits.shape[-1]
            m = ~state_allowed
            if width != len(m):
                pad = np.ones(width, dtype=bool)
                pad[:len(m)] = m
                m = pad
            import mlx.core as mx
            if isinstance(logits, mx.array):
                mx_m = mx.array(m)
                neg = mx.full(logits.shape, float("-inf"))
                if logits.ndim == 2:
                    mx_m = mx_m[None, :]
                return mx.where(mx_m, neg, logits)
            logits[m] = float("-inf")
            return logits
        prefix = self.tok.decode(gen, skip_special_tokens=True)
        state = self._state_for(prefix)
        allowed = self._allowed_masks.get(state)
        if allowed is None or bool(allowed.all()):
            return logits
        width = logits.shape[-1]
        key = (state, width)
        m = self._cache.get(key)
        if m is None:
            m = ~allowed
            if width != len(m):
                # the model pads its vocab (measured 248077 -> 248320);
                # padded ids are never legal
                pad = np.ones(width, dtype=bool)
                pad[:len(m)] = m
                m = pad
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
