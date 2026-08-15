"""Author the frozen E3 GLiNER-only ingestion qualification corpus.

Domains: cybersecurity, software/distributed systems, e-commerce,
psychology/metacognition, cinema/filmmaking, technical transcripts.
Formats: md, txt, html, docx, epub, pdf. Realistic multi-paragraph
documents of varying length (not toy sentences).

Qualification subset = the first 8 docs (gold in gold/gold.json);
operational corpus = all 16 (scale/stability only, not hand-labeled).

Idempotent: refuses to overwrite existing files.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "docs"

DOCS: dict[str, str] = {}

DOCS["cyber_zero_day.md"] = """# Zero-Day Response Handbook

A zero-day vulnerability is exploited before the vendor ships a patch. Detection depends on behavioral monitoring rather than signatures.

## Detection

Anomalous process execution and unusual network egress are the strongest early signals. The intrusion detection system correlates endpoint telemetry with threat intelligence feeds.

## Containment

Isolate the affected segment immediately. Kill persistent shells and revoke short-lived credentials. Preserve memory dumps before rebooting the host.

## Eradication

Remove implant artifacts and rotate every secret the adversary may have touched. Verify the patch actually closes the root cause before restoring service.
"""

DOCS["cyber_phishing.md"] = """# Phishing Campaign Triage

Phishing messages impersonate a trusted sender to steal credentials.

Users report suspicious mail through a dedicated abuse inbox. The triage team extracts the message headers, the landing URL, and any attachment hashes before taking down the infrastructure.

Multi-factor authentication does not prevent phishing when the attacker proxies the session token. Detection therefore focuses on impossible travel, unusual user-agent strings, and post-login automation patterns.
"""

DOCS["software_distributed_queues.md"] = """# Distributed Queue Reliability

A distributed queue decouples producers from consumers and absorbs load spikes.

At-least-once delivery requires idempotent consumers. Every mutation is keyed by a content hash, so a redelivered message cannot create a second logical result.

Backpressure propagates from the slowest consumer. When a worker pool saturates, the scheduler defers new submissions rather than growing the queue without bound. Dead-letter queues collect messages that fail repeatedly.
"""

DOCS["software_microservices.md"] = """# Microservice Contracts

A microservice owns one responsibility and exposes a versioned contract.

Breaking changes require a new contract version. Both versions run in parallel while consumers migrate, and the old version is retired only when traffic drops to zero.

Observability is part of the contract. Every request carries a trace id, and every failure carries an error code that the caller can act on.
"""

DOCS["ecommerce_checkout.md"] = """# Checkout Conversion

Checkout conversion measures how many sessions reach a completed purchase.

Friction sources include forced account creation, unexpected shipping costs, and slow payment gateways. Each friction point is measured separately with a funnel event.

Guest checkout removes the account wall. Address autofill shortens the form. The payment gateway is treated as an external dependency with its own availability budget.
"""

DOCS["ecommerce_search.md"] = """# Product Search Ranking

Product search ranks results by relevance to the query and the shopper's context.

Exact matches on product codes rank above fuzzy matches. Queries containing a size or color facet trigger a filtered search rather than a free-text interpretation.

The ranking pipeline reranks a bounded candidate set. The reranker never expands the candidate set, and every result carries the rule that produced its score.
"""

DOCS["psych_learning.md"] = """# Self-Regulated Learning

Self-regulated learning cycles through goal setting, monitoring, and strategy adjustment.

A learner who predicts performance before an attempt and compares the outcome afterward accumulates calibration signals. Repeated divergence reveals systematic overestimation or underestimation.

Monitoring consumes working memory. Under high cognitive load, fewer resources remain for evaluating whether a strategy is working, so monitoring accuracy deteriorates.
"""

DOCS["psych_monitoring.md"] = """# Metacognitive Monitoring

Metacognitive monitoring judges the current state of one's own knowledge.

Familiarity after rereading is a weak cue. Retrieval practice provides stronger evidence because it exposes what can actually be produced from memory.

Researchers distinguish monitoring from control: monitoring concerns judgments about knowledge, while control concerns the actions taken in response to those judgments.
"""

DOCS["cinema_lighting.md"] = """# Practical Lighting for Dialogue Scenes

A dialogue scene reads best when the key light motivates the blocking.

The cinematographer positions the key so the actor's eyeline crosses it. Fill light controls contrast without flattening the face. A practical lamp in frame justifies the source.

Night interiors lean on sodium and LED practicals. The colorist pushes the shadows toward the scene's temperature rather than pure black.
"""

DOCS["cinema_storyboard.md"] = """# Storyboard to Coverage

The storyboard lists the shots the edit will need before the crew arrives on set.

Each board pairs a frame with a lens and a camera move. Coverage adds safety takes, but the boards define the master sequence.

A director who shoots only coverage without the boards loses the plan. The editor reconstructs intent from the boards when the footage disagrees with them.
"""

DOCS["transcript_podcast.md"] = """# Transcript: Systems Roundtable

Host: Welcome back. Today we are talking about failure budgets.

Speaker A: A failure budget is the amount of unreliability you are allowed before changes freeze. If the budget is spent, feature work pauses.

Speaker B: Right. And the budget is measured over a rolling window, so a bad quarter ages out.

Host: Does that punish small teams?

Speaker A: No, because the budget scales with the traffic the service actually handles.
"""

DOCS["transcript_lecture.md"] = """# Transcript: Retrieval Lecture

Instructor: Retrieval systems combine several lanes. The document lane routes, the parent lane localizes, and the child lane retrieves exact passages.

Student: Which lane protects recall when routing fails?

Instructor: The global child lane. A child hit survives even when its document scores zero.

Student: And how do the lanes merge?

Instructor: Reciprocal rank fusion over the rankings, not the raw scores. The scales are not comparable, so fusion uses ranks only.
"""

# format conversion: several docs also exist in additional formats
FORMAT_CONVERSIONS = {
    "txt": ["software_distributed_queues.md", "transcript_podcast.md"],
    "html": ["cyber_phishing.md", "cinema_lighting.md"],
    "docx": ["ecommerce_checkout.md", "software_microservices.md"],
    "epub": ["psych_learning.md"],
    "pdf": ["cyber_zero_day.md", "ecommerce_search.md"],
}


def main() -> int:
    for name, text in DOCS.items():
        path = DOCS_DIR / name
        if not path.exists():
            path.write_text(text)
    for fmt, names in FORMAT_CONVERSIONS.items():
        for name in names:
            src = DOCS_DIR / name
            dst = src.with_suffix("." + fmt)
            if dst.exists():
                continue
            if fmt == "txt":
                dst.write_text(src.read_text())
            elif fmt == "html":
                subprocess.run(["pandoc", str(src), "-o", str(dst)], check=True)
            elif fmt == "docx":
                subprocess.run(["pandoc", str(src), "-o", str(dst)], check=True)
            elif fmt == "epub":
                subprocess.run(["pandoc", str(src), "-o", str(dst)], check=True)
            elif fmt == "pdf":
                tmp = src.with_suffix(".txt")
                tmp.write_text(src.read_text())
                with open(dst, "wb") as out:
                    subprocess.run(["cupsfilter", "-m", "application/pdf", str(tmp)],
                                   stdout=out, check=True)
                tmp.unlink()
            src.unlink()
    import hashlib
    lines = []
    for p in sorted(DOCS_DIR.glob("*")):
        if p.is_file():
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (ROOT / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    print(f"corpus authored: {len(lines)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
