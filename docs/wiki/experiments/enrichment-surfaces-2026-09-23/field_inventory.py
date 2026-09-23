"""ENRICHMENT-SURFACES-AUDIT addendum (2026-09-23) — every field the document profile and the pMAP hold for one corpus,
with item totals. Read-only, $0. Which code reads each field is recorded in the report §8 (anchors); this script only
counts what is stored.

usage: set -a; . ./.env; set +a
       .venv/bin/python docs/wiki/experiments/enrichment-surfaces-2026-09-23/field_inventory.py [corpus] [out.json]
"""
import collections
import datetime
import json
import os
import sys

import psycopg

PROFILE_VERSION = "doc-profile-v3.2"
IDENTIFIER_SHAPE = r"^[A-Z]{1,4}[0-9]{1,5}$"   # the A1 / A445 / ADR12 shape the resolution lift picked in every replay


def main():
    corpus = sys.argv[1] if len(sys.argv) > 1 else "cinema"
    with psycopg.connect(os.environ["POLYMATH_PG_DSN"]) as conn, conn.cursor() as c:
        c.execute("""SELECT DISTINCT ON (a.payload->'doc_profile'->>'doc_id') a.payload->'doc_profile'->'compiled'
                       FROM artifacts a JOIN documents d ON d.doc_id = (a.payload->'doc_profile'->>'doc_id')
                      WHERE a.stage = 'doc_profile' AND d.corpus_id = %s AND a.payload->'doc_profile'->>'prompt_version' = %s
                      ORDER BY a.payload->'doc_profile'->>'doc_id', a.created_at DESC""", (corpus, PROFILE_VERSION))
        profiles = [r[0] or {} for r in c.fetchall()]
        c.execute("select count(*) from documents where corpus_id = %s", (corpus,))
        docs = c.fetchone()[0]
        c.execute("""select count(*), coalesce(sum(jsonb_array_length(semantic_hooks)), 0),
                            coalesce(sum(jsonb_array_length(exact_identifiers)), 0),
                            count(*) filter (where exists (select 1 from jsonb_array_elements_text(exact_identifiers) e
                                                           where e ~ %s))
                       from document_parent_maps where corpus_id = %s and active""", (IDENTIFIER_SHAPE, corpus))
        maps, hooks, identifiers, maps_with_id_shape = c.fetchone()
    fields = collections.Counter()
    items = collections.Counter()
    for comp in profiles:
        for k, v in comp.items():
            fields[k] += 1
            if isinstance(v, list):
                items[k] += len(v)
    out = {"generated_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"), "corpus": corpus,
           "documents": docs, "profiles_v3_2": len(profiles),
           "profile_fields_present": dict(sorted(fields.items())),
           "profile_list_items_total": dict(sorted(items.items())), "profile_list_items_all": sum(items.values()),
           "pmap": {"active_maps": maps, "semantic_hooks_total": int(hooks), "exact_identifiers_total": int(identifiers),
                    "maps_with_identifier_shaped_id": maps_with_id_shape, "identifier_shape": IDENTIFIER_SHAPE}}
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
