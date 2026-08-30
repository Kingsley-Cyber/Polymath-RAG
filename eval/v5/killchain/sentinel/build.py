"""SEMANTIC-SENTINEL-V1 source generator.

A sealed, deterministic, SYNTHETIC corpus (no copyrighted text) whose
expected outputs are explicit. Exercises the same mechanisms the real
books do, so a dead lane cannot hide behind "no opportunity".
"""
import os, sys
D = os.path.dirname(os.path.abspath(__file__))

DOCS = {}

# ---- doc A: facts (clean / passive / negated / hedged) + a concept
DOCS["sentinel_facts.md"] = """# Network Defence Notes

## Scanning Tools

Nessus scans network hosts for known vulnerabilities. Nessus was
developed by Tenable. The scanner produces a report for each host.

Nmap discovers open ports on a target host. Nmap uses TCP SYN probes to
determine port state.

## Statements That Must Not Become Facts

Nessus does not replace penetration testing. It is sometimes claimed
that Nessus exploits vulnerabilities, but that is incorrect. Some
analysts believe Nmap may eventually include exploitation features.

## Definition

A vulnerability scanner is a tool that inspects hosts for known weaknesses
and reports them without exploiting them. Port scanning is the technique
of probing a host to determine which services are listening.
"""

# ---- doc B: two distinct procedures in one section + one spanning a boundary
DOCS["sentinel_procedures.md"] = """# Operations Runbook

## Two Separate Tasks In One Section

To rotate an API credential, open the credential console. Select the key
you intend to replace. Generate a replacement key. Update the dependent
service configuration. Revoke the previous key.

To restore a host from backup, identify the last known good snapshot.
Detach the compromised volume. Attach the snapshot volume. Boot the host
in isolation. Verify integrity before returning it to the network.

## A Long Task

Begin the containment workflow by isolating the affected host. Capture a
memory image before powering down. Collect the relevant log bundles.
Record the responder actions in the case file. Notify the incident
commander. Preserve the disk image for later analysis. Document the
containment decision. Hand the case to the eradication team. Confirm the
handoff was acknowledged. Close the containment phase.
"""

# ---- doc C: transcript (H33) + ambiguous acronym + exact identifiers
DOCS["sentinel_transcript.md"] = """# Session Transcript

## Recorded Discussion

ANALYST: So the alert fired on host WEB-04 at 09:14 UTC.

LEAD: Right, and the signature was CVE-2023-38831. That is the WinRAR
issue. Did you confirm the file hash?

ANALYST: I did. It matched. I mean, it matched the known sample, sorry.

LEAD: Good. IR means incident response here, not information retrieval,
so page the on-call responder. Use the 802.11 wireless segment map to
find the host location.

ANALYST: Understood. The endpoint agent reported the process tree.

## Structured Reference

| Port | Service | Notes |
|------|---------|-------|
| 22   | SSH     | admin |
| 445  | SMB     | file  |

```python
def isolate(host):
    firewall.block(host)
    return True
```
"""

# ---- doc D: boilerplate negative (must NOT become knowledge)
DOCS["sentinel_boilerplate.md"] = """# About This Guide

## About the Author

Dana Reyes, CISSP, MCSE, is a technical consultant, trainer, and author.
Dana has served as technical editor on numerous titles.

## Copyright

Copyright 2026 Example Press. All rights reserved. No part of this
publication may be reproduced or transmitted in any form.

## Register Your Book

We highly recommend that you use the companion volume. Register your book
to download the example code bundle.
"""

for name, body in DOCS.items():
    open(os.path.join(D, name), "w").write(body)
    print(f"{name:<28}{len(body):>6} bytes")
