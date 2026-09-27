"""TRAIL-EXT-BUGHUNT-V1 B-10 — the ecommerce engine's price parser reads a price as USD only when it IS USD.

`executors._parse_price` feeds the supplier leads (`supply.leads` -> T_leads) and the receipt builder's USD metric. A dollar-family
foreign currency (HK$, NZ$, A$, CA$, SG$, NT$, R$ …) used to pass as USD because its `$` looked like a bare dollar sign, and a
mixed string read its FIRST number. The engine is run out of process (its flat module names never enter this interpreter).
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ENGINE = pathlib.Path(__file__).resolve().parents[2] / "adapters" / "ecommerce"

CASES = [
    # plain USD: unchanged
    ("$4.20", (4.2, 4.2)), ("US$4.20-5.10", (4.2, 5.1)), ("US $12.50 - 18.00", (12.5, 18.0)), ("USD 1,200.50", (1200.5, 1200.5)),
    ("US$1.20-1.80 / piece", (1.2, 1.8)), ("4.20 USD", (4.2, 4.2)), ("$3.20 - $4.10", (3.2, 4.1)), ("US $3.20 - US $4.10", (3.2, 4.1)),
    ("U$4.20", (4.2, 4.2)), ("USD$4.20", (4.2, 4.2)), ("2 pcs US$4.20", (4.2, 4.2)),
    # dollar-family foreign currencies are not dollars
    ("HK$25.00", (None, None)), ("NZ$9.90", (None, None)), ("A$12.50 - A$14.00", (None, None)), ("CA$12.00", (None, None)),
    ("AU$12.00", (None, None)), ("S$9.90", (None, None)), ("SG$9.90", (None, None)), ("NT$300", (None, None)), ("R$50", (None, None)),
    ("C$12", (None, None)),
    # other currencies still refuse; a stated USD amount is read WHERE IT STANDS, whatever else the string quotes
    ("€12.00", (None, None)), ("¥25", (None, None)), ("EUR 12", (None, None)), ("CNY 18.50", (None, None)),
    ("¥18.50 (≈ US$2.60)", (2.6, 2.6)), ("HK$25 (USD 3.20)", (3.2, 3.2)), ("¥18.50 ($2.60)", (None, None)),
    ("", (None, None)), ("price on request", (None, None)),
]


def test_parse_price_reads_usd_only():
    code = ("import json, sys; sys.path.insert(0, 'python'); import executors; "
            "print(json.dumps([executors._parse_price(s) for s in json.loads(sys.argv[1])]))")
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, "-c", code, json.dumps([raw for raw, _ in CASES])], cwd=ENGINE, env=env, capture_output=True, text=True, check=False, timeout=60)
    assert proc.returncode == 0, proc.stderr[-800:]
    got = [tuple(x) for x in json.loads(proc.stdout)]
    wrong = [(raw, want, have) for (raw, want), have in zip(CASES, got) if want != have]
    assert not wrong, wrong


@pytest.mark.parametrize("raw", ["HK$25.00", "A$12.50 - A$14.00"])
def test_a_foreign_dollar_listing_is_not_a_usd_metric_in_the_receipt(raw):
    code = ("import json, sys; sys.path.insert(0, 'python'); import adapter_receipt as AR; "
            "print(json.dumps(AR._supplier_items([{'id': 'sc1', 'product_name': 'synthetic clip', 'supplier_name': 'Example Co', "
            "'price_raw': sys.argv[1], 'moq_raw': '100 pcs', 'url': 'https://www.alibaba.com/product-detail/x.html'}])))")
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, "-c", code, raw], cwd=ENGINE, env=env, capture_output=True, text=True, check=False, timeout=60)
    assert proc.returncode == 0, proc.stderr[-800:]
    items = json.loads(proc.stdout)
    assert not any((i.get("metric") or {}).get("unit") == "USD" for i in items) and [i["id"] for i in items] == ["sc1:moq"]
