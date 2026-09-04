# Lived Situation (lived_situations / lived_r1 / lived_r2)

Build LivedSituations (schema lived_situation.json), not personas: community
+ activity + MOMENT (BEFORE/ARRIVAL/DURING/TRANSITION/AFTER) + environment +
participants + body/hand state + object state + constraints + frictions +
unknowns. A situation is ONE moment in ONE real world, reconstructed from
records — never a biography.

Authority is decided by the records, not by you:
- `FIELD_ANCHORED` — only on a `cluster_id` whose authority is ANCHOR; at
  least one friction must carry `authority: FIELD_OBSERVATION` with `refs`
  to the record ids that say it. The validator rejects anything else.
- `RECONSTRUCTED` — on a THIN cluster (or corrected against observations):
  the records give you fragments, you fill the moment explicitly, and
  `unknowns[]` lists what the records do NOT say. A reconstruction with no
  unknowns is rejected as a biography.
- `SIMULATED` — no records at all (loadout round 1). Simulation is never
  evidence; it only tells the field where to look next.

Per cluster: read its participant cards and records, write 1–3 situations
across different moments (insider collections live in BEFORE / TRANSITIONS /
AFTER; generic ecommerce lives in DURING), copy the cluster's `unknowns`
forward and add your own. Frictions you infer carry `authority:
RECONSTRUCTED` and no refs. Capture PREFERENCE CLUSTERS instead of averaging
disagreements. Every unknown you write becomes a research question — that is
how a thin world grows into an anchored one.
