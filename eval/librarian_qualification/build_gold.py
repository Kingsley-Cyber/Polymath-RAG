#!/usr/bin/env python3
"""Build the librarian qualification gold set for the `cinema` corpus (mission §12-§13).

Authors real corpus-grounded queries across every required category and resolves each query's
gold DOCUMENTS by case-insensitive source_name substring against cinema_docmap.json. Gold is the
set of documents whose content a correct retrieval MUST surface; multiple acceptable documents are
listed where a topic legitimately spans books. Unsupported queries carry no gold (the corpus does
not establish them) — the system must decline rather than fabricate.
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DOCMAP = json.loads((HERE / "cinema_docmap.json").read_text())


def resolve(*subs: str) -> list[str]:
    out = []
    for did, name in DOCMAP.items():
        low = name.lower()
        if any(s.lower() in low for s in subs):
            out.append(did)
    return sorted(set(out))


# (id, query, category, [gold source-name substrings], modes|None, unsupported)
Q = [
    # --- direct factual / definitions / exact terminology ---
    ("direct_180", "What is the 180-degree rule in filming a scene?", "direct_factual",
     ["Grammar of the Shot", "Five C's", "Grammar of the Edit", "Cinematography - Theory"], None, False),
    ("direct_thirds", "What is the rule of thirds in visual composition?", "direct_factual",
     ["Cinematography - Theory", "Five C's", "Filmmaker", "Visual Story"], None, False),
    ("direct_facs", "What is the Facial Action Coding System and what does it measure?", "definition",
     ["Facial Action Coding System", "Facial Action coding", "What the Face Reveals"], None, False),
    ("direct_actionunit", "What is an action unit in facial expression coding?", "definition",
     ["Facial Action Coding System", "Facial Action coding", "Classifying Facial Action"], None, False),
    ("direct_laban_effort", "What are the Effort qualities in Laban Movement Analysis?", "definition",
     ["Laban", "Bartenieff", "Your Move"], None, False),
    ("direct_depthoffield", "What is depth of field and what controls it?", "direct_factual",
     ["Cinematography - Theory", "Lighting for Cinematography", "Filmmaker"], None, False),
    ("direct_matchcut", "What is a match cut in film editing?", "direct_factual",
     ["Grammar of the Edit", "In the Blink of an Eye", "technique of film"], None, False),
    ("direct_chromakey", "How does chroma key green-screen compositing work?", "direct_factual",
     ["Digital Compositing", "Art and Science", "Art And Science", "VES Handbook", "Fusion"], None, False),
    ("exact_rapo", "What is RAPO retrieval-augmented prompt optimization?", "exact_terminology",
     ["Retrieval-Augmented Prompt"], None, False),
    ("exact_ves", "What does the VES Handbook cover about visual effects?", "exact_terminology",
     ["VES Handbook"], None, False),
    ("direct_storybeat", "What is the beat sheet in screenwriting?", "direct_factual",
     ["Save the Cat", "Anatomy of Story"], None, False),
    ("direct_threepoint", "What is three-point lighting and what does each light do?", "multi_evidence",
     ["Lighting for Cinematography", "Cinematography - Theory"], None, False),

    # --- paraphrased / low lexical overlap (semantic) ---
    ("para_disorient", "How do filmmakers keep viewers from getting confused about where characters are positioned relative to each other?", "paraphrase",
     ["Grammar of the Shot", "Five C's", "Grammar of the Edit"], None, False),
    ("para_sticky", "What makes an idea memorable so that people remember and repeat it?", "low_lexical",
     ["Made to Stick"], None, False),
    ("para_evenlight", "How do you illuminate a large flat backdrop evenly without hotspots?", "low_lexical",
     ["Lighting for Cinematography", "Digital Compositing", "VES Handbook"], None, False),
    ("para_bodyintent", "How does a performer's body communicate force, weight and intention to an audience?", "low_lexical",
     ["Laban", "Bartenieff", "Fight Choreography", "Acting for Animators"], None, False),
    ("para_persuade", "What techniques make written advertising copy persuasive?", "paraphrase",
     ["Ogilvy", "Breakthrough Advertising", "Whipple", "Copywriting"], None, False),

    # --- cross-document synthesis ---
    ("synth_edit_music", "How do the rhythm of film editing and the timing of music relate?", "cross_doc_synthesis",
     ["In the Blink of an Eye", "Sound Design", "Grammar of the Edit", "technique of film"], None, False),
    ("synth_light_color", "How do lighting and color grading work together to establish mood?", "cross_doc_synthesis",
     ["Lighting for Cinematography", "Cinematography - Theory", "DaVinci", "Fusion"], None, False),
    ("synth_compose_comic", "What composition principles are shared between film framing and comics?", "cross_doc_synthesis",
     ["Framed Ink", "Comics and Sequential Art", "Visual Story", "Filmmaker"], None, False),

    # --- comparison / contrast ---
    ("cmp_edit", "Compare continuity editing with montage in film.", "comparison",
     ["Grammar of the Edit", "technique of film", "In the Blink of an Eye"], None, False),
    ("cmp_advertising", "How do classic and modern advertising approaches treat long copy?", "comparison",
     ["Ogilvy", "Breakthrough Advertising", "Copywriting", "Whipple"], None, False),

    # --- relational / graph ---
    ("rel_cine_edit", "How are cinematography and film editing related in filmmaking?", "relational",
     ["Cinematography - Theory", "Grammar of the Edit", "technique of film", "Five C's"], None, False),
    ("rel_face_acting", "How does facial expression coding connect to acting and animation performance?", "relational",
     ["Facial Action Coding System", "What the Face Reveals", "Acting for Animators"], None, False),

    # --- profile-driven discovery (cross-domain) ---
    ("disc_personality", "What does the corpus say about human personality types and temperament?", "profile_discovery",
     ["Please Understand Me", "Gifts differing"], None, False),
    ("disc_motion_ml", "How is human movement modeled or generated computationally?", "profile_discovery",
     ["Laban Movement-Guided Diffusion", "Bayesian reasoning for Laban", "Making Meaning with Machines", "Affective Movement"], None, False),
    ("disc_neuroarch", "How does architecture affect the human mind and perception?", "profile_discovery",
     ["Neuroarchitecture"], None, False),

    # --- pMAP / hierarchical localization (single-doc) ---
    ("pmap_murch_blink", "In Walter Murch's book, what is the blink theory of editing?", "pmap_localization",
     ["In the Blink of an Eye"], None, False),
    ("pmap_savecat", "What are the fifteen beats in the Save the Cat story structure?", "pmap_localization",
     ["Save the Cat"], None, False),
    ("pmap_lumet", "What does Sidney Lumet say about making movies and working with actors?", "pmap_localization",
     ["Making Movies"], None, False),

    # --- relational/graph queries (bridging) ---
    ("bridge_combat_movement", "How does movement analysis inform staged fight choreography on screen?", "relational",
     ["Fight Choreography", "Stage Combat", "Screen Combat", "Laban"], None, False),

    # --- WILDCARD / non-obvious discovery ---
    ("wild_dance_film", "What non-obvious connections exist between dance notation and filmmaking?", "wildcard_discovery",
     ["Benesh", "Laban", "In the Blink of an Eye", "Your Move"], None, False),
    ("wild_ad_story", "How might advertising persuasion ideas apply to visual storytelling in film?", "wildcard_discovery",
     ["Made to Stick", "StoryBrand", "Anatomy of Story", "Ogilvy"], None, False),

    # --- multi-evidence ---
    ("multi_exposure", "What is the exposure triangle and how does aperture, shutter and ISO each affect the image?", "multi_evidence",
     ["Cinematography - Theory", "Lighting for Cinematography", "Five C's"], None, False),
    ("multi_storyarc", "What are the main stages of a dramatic story arc?", "multi_evidence",
     ["Anatomy of Story", "Save the Cat", "Directing the Story"], None, False),

    # --- distractor-heavy (polysemy) ---
    ("distract_shape", "What does 'shape' mean in Laban movement terms?", "distractor",
     ["Laban", "Bartenieff", "Your Move"], None, False),
    ("distract_weight", "What is 'weight' as a movement quality in movement analysis?", "distractor",
     ["Laban", "Bartenieff", "Your Move"], None, False),
    ("distract_frame", "What is 'framing' in cinematography composition?", "distractor",
     ["Cinematography - Theory", "Five C's", "Filmmaker", "Grammar of the Shot"], None, False),

    # --- resolution-triggering (round-1 likely partial) ---
    ("res_shutter_motion", "How does shutter angle affect motion blur when filming fast action?", "resolution_trigger",
     ["Cinematography - Theory", "Five C's", "Lighting for Cinematography"], None, False),

    # --- definitions of drawing/anatomy ---
    ("direct_gesture", "What is gesture drawing and how does it capture force and motion?", "direct_factual",
     ["Force", "Framed Ink", "Anatomy for Sculptors"], None, False),

    # --- unsupported / corpus-does-not-know (NO gold) ---
    ("unsup_nitrogen", "What is the boiling point of liquid nitrogen in kelvin?", "unsupported",
     [], None, True),
    ("unsup_taxes", "How do I file my federal income tax return?", "unsupported",
     [], None, True),
    ("unsup_chess", "What are the official rules for castling in chess?", "unsupported",
     [], None, True),
    ("unsup_python", "How do I reverse a linked list in Python?", "unsupported",
     [], None, True),
]

# --- 10 query-sensitivity pairs (§12): a controlled wording/constraint change should move retrieval predictably ---
PAIRS = [
    ("sens_light_broad", "Tell me about lighting in film.", "sensitivity_broad", ["Lighting for Cinematography", "Cinematography - Theory"]),
    ("sens_light_specific", "How do I light a face with soft key and fill for a portrait?", "sensitivity_specific", ["Lighting for Cinematography"]),
    ("sens_faceA", "What does Paul Ekman's work say about facial expressions of emotion?", "sensitivity_entityA", ["Facial Action", "What the Face Reveals"]),
    ("sens_faceB", "What does Rudolf Laban's work say about the expression of movement?", "sensitivity_entityB", ["Laban", "Your Move", "Bartenieff"]),
    ("sens_edit_direct", "What is a jump cut?", "sensitivity_direct", ["Grammar of the Edit", "technique of film", "In the Blink of an Eye"]),
    ("sens_edit_rel", "How does a jump cut relate to the viewer's sense of continuity and time?", "sensitivity_relational", ["In the Blink of an Eye", "Grammar of the Edit"]),
    ("sens_term_a", "What is a foley sound effect?", "sensitivity_termA", ["Sound Design"]),
    ("sens_term_b", "What is a sound effect created by a performer mimicking real-world noises for a film?", "sensitivity_termB", ["Sound Design"]),
    ("sens_story_broad", "How do you structure a story?", "sensitivity_broad", ["Anatomy of Story", "Save the Cat", "Directing the Story"]),
    ("sens_story_constrained", "How does the Save the Cat method structure a screenplay's second act?", "sensitivity_constrained", ["Save the Cat"]),
    ("sens_compose_broad", "How do you compose a film shot?", "sensitivity_broad", ["Cinematography - Theory", "Five C's", "Filmmaker", "Visual Story"]),
    ("sens_compose_concept", "How do leading lines guide the viewer's eye within a composition?", "sensitivity_concept", ["Framed Ink", "Cinematography - Theory", "Filmmaker"]),
    ("sens_advA", "What does David Ogilvy advise about effective advertising?", "sensitivity_entityA", ["Ogilvy"]),
    ("sens_advB", "What does Eugene Schwartz say about market sophistication and desire in advertising?", "sensitivity_entityB", ["Breakthrough Advertising"]),
    ("sens_keylight_direct", "What is a key light?", "sensitivity_direct", ["Lighting for Cinematography", "Cinematography - Theory"]),
    ("sens_keylight_rel", "How does the key-to-fill lighting ratio shape the mood on a face?", "sensitivity_relational", ["Lighting for Cinematography"]),
    ("sens_storyboard_term", "What is a storyboard?", "sensitivity_termA", ["Framed Ink", "Directing the Story", "Cinematic Motion", "Directing - Film Techniques"]),
    ("sens_storyboard_para", "What is a shot-by-shot drawn plan of a film's visuals before shooting?", "sensitivity_termB", ["Framed Ink", "Directing the Story", "Cinematic Motion", "Directing - Film Techniques"]),
    ("sens_vfx_broad", "What is visual effects compositing?", "sensitivity_broad", ["Digital Compositing", "Art and Science", "Art And Science", "VES Handbook"]),
    ("sens_vfx_specific", "How do you composite a CG element over a live-action plate with correct edge blending and color match?", "sensitivity_specific", ["Digital Compositing", "Art and Science", "Art And Science", "VES Handbook", "Fusion"]),
]


def build() -> dict:
    queries = []
    for qid, text, cat, subs, modes, unsup in Q:
        gold = resolve(*subs) if subs else []
        queries.append({"id": qid, "query": text, "category": cat,
                        "gold_source_substrings": subs, "gold_doc_ids": gold,
                        "modes": modes, "unsupported": unsup})
    pairs_meta = []
    for qid, text, cat, subs in PAIRS:
        gold = resolve(*subs)
        queries.append({"id": qid, "query": text, "category": cat,
                        "gold_source_substrings": subs, "gold_doc_ids": gold,
                        "modes": None, "unsupported": False})
        pairs_meta.append(qid)
    sensitivity_pairs = [[PAIRS[i][0], PAIRS[i + 1][0]] for i in range(0, len(PAIRS), 2)]
    return {"corpus": "cinema", "n_queries": len(queries),
            "sensitivity_pairs": sensitivity_pairs, "queries": queries}


if __name__ == "__main__":
    g = build()
    out = HERE / "gold_queries.json"
    out.write_text(json.dumps(g, indent=1))
    # report gold coverage
    empty = [q["id"] for q in g["queries"] if not q["gold_doc_ids"] and not q["unsupported"]]
    print(f"wrote {g['n_queries']} queries -> {out}")
    print(f"sensitivity pairs: {len(g['sensitivity_pairs'])}")
    print(f"unsupported (no gold): {sum(1 for q in g['queries'] if q['unsupported'])}")
    if empty:
        print(f"WARNING — supported queries with NO resolved gold (fix substrings): {empty}")
    else:
        print("all supported queries resolved gold documents OK")
