"""DOCUMENT-REGION-V1: precision-first document-role classification.

The governing rule is PHASE C: false suppression of real technical
content is worse than leaving some boilerplate in place. Every
adversarial phrase below LOOKS like a region label and is substantive
prose; all of them must classify BODY.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_region import (  # noqa: E402
    ROLE_BIBLIOGRAPHY,
    ROLE_BODY,
    ROLE_FRONT_MATTER,
    ROLE_INDEX,
    ROLE_MARKETING,
    ROLE_OCR_NOISE,
    ROLE_TOC,
    ROLE_UNKNOWN,
    classify_region,
    is_noisy,
)


def role(text):
    return classify_region(text)[0]


# ---------------------------------------------------- HARD NEGATIVES
# Substantive prose that merely CONTAINS region vocabulary.
HARD_NEGATIVES = [
    "References to the Windows registry are resolved at process start. "
    "An analyst inspecting a suspicious binary should confirm which "
    "registry hives the process references during execution.",

    "Introduction to References: this section explains how the tool "
    "resolves symbolic references between compiled modules at runtime.",

    "Index structures in databases determine query performance. A "
    "B-tree index reduces lookup cost from linear to logarithmic, while "
    "a hash index gives constant-time equality lookups.",

    "Appendix exploitation techniques are covered here in depth, "
    "including how an attacker chains a directory traversal with a "
    "file-upload primitive to obtain remote code execution.",

    "About privilege escalation: the analyst must distinguish vertical "
    "escalation, where a user gains higher privileges, from horizontal "
    "escalation across peer accounts.",

    "Contents of an HTTP request include the request line, headers, and "
    "an optional body. Inspecting the contents during triage reveals "
    "injected headers used for smuggling.",

    "Code signing verifies that a binary originated from a trusted "
    "publisher and has not been altered. Revoked signing certificates "
    "must be checked against the CRL.",

    "Table of routing protocols: BGP, OSPF, and EIGRP differ in "
    "convergence behaviour and in how they compute path cost across "
    "autonomous systems.",

    "Output encoding is the primary defence against cross-site "
    "scripting. Encode on output according to the context in which the "
    "untrusted value is rendered.",

    "Links between incident response phases matter: containment "
    "decisions constrain eradication options, and eradication quality "
    "determines recovery time.",

    "Authoritative DNS servers answer queries for zones they own. A "
    "responder tracing exfiltration should compare authoritative "
    "answers with resolver cache contents.",

    "Preface attacks manipulate the leading bytes of a serialized "
    "object so that a parser misinterprets the remaining structure.",

    "Bibliography management software such as reference managers can "
    "leak document metadata; analysts should treat exported libraries "
    "as sensitive.",
]


@pytest.mark.parametrize("text", HARD_NEGATIVES, ids=range(len(HARD_NEGATIVES)))
def test_hard_negatives_stay_body(text):
    """Region vocabulary inside substantive prose must NEVER suppress."""
    assert role(text) == ROLE_BODY, classify_region(text)


# ---------------------------------------------------- TRUE POSITIVES
def test_author_biography_is_front_matter():
    """The MEASURED failing case: this chunk ranked #1 for a technical
    question about exam domains."""
    text = ("Chris Crayton, MCSE, CISSP, CASP+, CySA+, A+, N+, S+, is a "
            "technical consultant, trainer, author, and industry-leading "
            "technical editor. He has worked as a computer technology and "
            "networking instructor, information security director, network "
            "administrator, network engineer, and PC specialist.")
    assert role(text) == ROLE_FRONT_MATTER


def test_about_the_author_heading_is_front_matter():
    assert role("## About the Author\n\nShe has taught security for a decade.") \
        == ROLE_FRONT_MATTER


def test_publisher_marketing_is_marketing():
    text = ("CompTIA CySA+ Practice Tests is a companion volume to the "
            "CompTIA CySA+ Study Guide. If you're just starting to prepare "
            "we highly recommend that you use the Study Guide.")
    assert role(text) == ROLE_MARKETING


def test_copyright_block_is_front_matter():
    text = ("Copyright 2023 by John Wiley & Sons. All rights reserved. "
            "No part of this publication may be reproduced, stored in a "
            "retrieval system, or transmitted in any form.")
    assert role(text) == ROLE_FRONT_MATTER


def test_dot_leader_toc_is_toc():
    text = "\n".join([
        "Chapter 1 Today's Cybersecurity Analyst ..... 3",
        "Chapter 2 System and Network Architecture ..... 37",
        "Chapter 3 Malicious Activity ..... 77",
        "Chapter 4 Threat Intelligence ..... 135",
        "Chapter 5 Reconnaissance ..... 159",
        "Chapter 6 Vulnerability Management ..... 203",
    ])
    assert role(text) == ROLE_TOC


def test_index_page_list_is_index():
    text = "\n".join([
        "access control, 12, 45-47",
        "authentication, 88, 91",
        "buffer overflow, 203",
        "cryptography, 15, 22, 40",
        "denial of service, 77",
        "encryption, 15, 60",
    ])
    assert role(text) == ROLE_INDEX


def test_reference_list_is_bibliography():
    text = "\n".join([
        "Smith, J. A. Detection engineering. In: Proceedings of SANS, 2019.",
        "Doe, R. B. Threat hunting at scale. arXiv:1904.01234",
        "Brown, C. D. Incident response metrics. doi: 10.1145/3292500",
        "Lee, K. M. Adversary emulation frameworks. In: USENIX, 2021.",
        "Patel, S. R. Log analysis techniques. In: RSA Conference, 2020.",
    ])
    assert role(text) == ROLE_BIBLIOGRAPHY


def test_ocr_placeholder_is_noise():
    assert role("## Page 12 #### OCR_FALLBACK_TEXT _[OCR could not "
                "extract text from this page]_") == ROLE_OCR_NOISE


# ------------------------------------------------- THE CRITICAL PAIR
def test_objectives_map_is_body_even_though_it_sits_in_front_matter():
    """DECISIVE. The CS0-003 objectives map lives in the SAME
    front-matter region as the author biography and even OPENS with
    marketing prose. Position-based classification would suppress the
    correct answer; content-based must not."""
    text = ("to help you prepare for the exam. By using these tools you can "
            "dramatically increase your chances of passing on your first "
            "try. Objectives Map for CompTIA CySA+ Exam CS0-003. "
            "1.0 Security Operations 1.1 Explain the importance of system "
            "and network architecture concepts in security operations "
            "1.2 Given a scenario, analyze indicators of potentially "
            "malicious activity")
    # Caught as a live false positive during corpus measurement: the
    # marketing rule DID fire on this chunk. The positive-content
    # override now takes precedence, because enumerated structure proves
    # the chunk carries content regardless of its packaging.
    assert role(text) == ROLE_BODY, classify_region(text)
    assert classify_region(text)[1] == "answer_bearing_structure_override"


def test_marketing_without_structure_is_still_demoted():
    """The override must not become a blanket amnesty: the same
    marketing prose WITHOUT enumerated content stays demoted."""
    text = ("to help you prepare for the exam. By using these tools you can "
            "dramatically increase your chances of passing on your first "
            "try. The online test bank includes over 1000 practice "
            "questions.")
    assert role(text) == ROLE_MARKETING


def test_appendix_is_not_suppressed_by_default():
    """v3.3 excluded APPENDIX. v4 does not: technical appendices in this
    corpus carry real evidence."""
    text = ("Appendix B: Port Reference. Port 22 carries SSH, port 445 "
            "carries SMB, and port 3389 carries RDP. Analysts should "
            "baseline which of these are expected on each segment.")
    assert role(text) == ROLE_BODY


# --------------------------------------------------------- semantics
def test_unknown_and_body_are_never_suppressed():
    assert not is_noisy(ROLE_BODY)
    assert not is_noisy(ROLE_UNKNOWN)
    assert not is_noisy(None), "unclassified legacy chunks must stay live"


def test_noisy_roles_are_demoted():
    for r in (ROLE_FRONT_MATTER, ROLE_MARKETING, ROLE_TOC,
              ROLE_INDEX, ROLE_BIBLIOGRAPHY, ROLE_OCR_NOISE):
        assert is_noisy(r)


def test_deterministic():
    t = "Chris Crayton, MCSE, is a technical consultant and author."
    assert classify_region(t) == classify_region(t)
