"""PRODUCT SEARCH (product-search-v1, PRODUCT-SEARCH-E2E 2026-11-01): a product request in chat is answered from ANY corpus with
product hypotheses plus CJ Dropshipping finds per hypothesis, ending with an offer of the full governed research run.

  intent      PRODUCT-INTENT-V1: does the message ask to find products / suppliers (deterministic; seed, audience, geography, terms)
  hypotheses  retrieval steering toward hypothesis material, the synthesis contract, the read-back of the hypothesis block
  service     the CJ / Alibaba lookups, the product_research block, `ProductTurn` (what the chat runtime and /product/search drive)
"""
from polymath_shared.product_search.intent import CONTRACT as INTENT_CONTRACT
from polymath_shared.product_search.intent import ProductIntent, detect
from polymath_shared.product_search.service import CONTRACT, ProductTurn

__all__ = ["CONTRACT", "INTENT_CONTRACT", "ProductIntent", "ProductTurn", "detect"]
