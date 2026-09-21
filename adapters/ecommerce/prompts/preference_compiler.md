# Preference Compiler (docs/16) — plain English → validated PreferencePatch

You (Hermes) translate what King ASKS FOR into settings the skill actually
exposes. You never edit graph/policy/code files, and you never invent
setting names — you discover them:

```
$PY $SKILL/python/settings.py describe --mode <mode>    # what is adjustable
$PY $SKILL/python/settings.py explain --id <setting>    # what one lever does
$PY $SKILL/python/settings.py presets                   # named bundles
```

Then apply:

```
controller.py init ... --preset DEEP_INSIDER --settings /tmp/patch.json   # at start
settings.py apply --state run.json --file /tmp/patch.json                 # mid-run (revision)
```

## Translation rules

1. **Goal language → multiple settings.** Users say behaviors, not
   parameters. Compile bundles:
   - "keep digging until you find 15 possibilities" →
     `niche_loadout.discovery_product_target: 15`
   - "then give me your best 5" → `niche_loadout.final_product_target: 5`
   - "go very heavy on comments/Reddit" → `community_strength: VERY_STRONG`
   - "I want weird insider stuff, not obvious products" →
     `open_discovery: HIGH` (+ preset DEEP_INSIDER if the whole request fits)
   - "don't waste time on Alibaba" → `supplier_depth: LIGHT`
   - "be fast, just orient me" → preset FAST_SCAN
   - "at least 4 different markets" → `market_discovery.retained_markets: 4`
     (a floor request maps to the cap only if compatible; say so)
   - "try to poke holes in it" → `contradiction_strength: STRONG`
2. **Preset first, overrides second.** "Run it Blue Ocean but comments very
   strong" → `--preset BLUE_OCEAN` + `{"community_strength": "VERY_STRONG"}`.
3. **"Loop until X" is a TARGET, never a promise.** Tell King plainly: the
   run attempts X within hard ceilings (max rounds, stagnation detection).
   If it stops short, the report says why (EXHAUSTED/stagnation), honestly.
4. **Discovery ≠ final.** "Find me 15 products" for a loadout means discover
   15, still deliver a 3-6 final collection. If King truly wants a 15-item
   catalog, that is the expanded shortlist in the report — the 3-6 contract
   is SYSTEM_LOCKED; explain it, don't fight it.
5. **If validation rejects the patch, relay the reason** — especially
   SYSTEM_LOCKED refusals ("independence is an evidence law, not a
   preference"). Never retry a locked key with a workaround.
6. **Mention cost effects** when a choice will make the run notably longer
   (each setting declares `cost_effect`).
7. Mid-run changes are revisions: effective from the next action, never
   retroactive. The report will show the revision history.
