"""Author the frozen I2 qualification corpus (30 distinct documents,
4 domains, multiple formats). Idempotent: refuses to overwrite the
frozen fixture once written (sha256 recorded in SHA256SUMS)."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DOCS: dict[str, str] = {}

DOCS["psych/metacognitive_monitoring.md"] = """# Metacognitive Monitoring

Metacognitive monitoring refers to the processes by which a learner judges the current state of their own knowledge. These judgments concern whether a concept has been understood, whether retrieval would succeed, and whether additional study is necessary.

Monitoring judgments are not always accurate. A learner can feel a strong sense of familiarity after rereading a paragraph while remaining unable to retrieve the underlying idea without cues. Researchers therefore distinguish monitoring, which concerns judgments about knowledge, from control, which concerns the actions taken in response to those judgments.

The quality of later decisions depends on how well the learner's internal judgment corresponds to actual performance. When the correspondence is poor, the system can appear organized at the behavioral level even when its internal estimate of understanding is poorly calibrated.

Accuracy of monitoring deteriorates when working memory is heavily occupied. Under high cognitive load, fewer resources remain for evaluating performance and deciding what to do next.
"""

DOCS["psych/metacognitive_control.md"] = """# Metacognitive Control

Metacognitive control concerns the actions a learner takes in response to judgments about their own knowledge. A student who judges material as weak may allocate additional study time; material judged as mastered may be dropped from the study queue.

Control depends on the representation produced by monitoring. If the learner's representation of a problem is weak or incomplete, the control process may confidently select an ineffective strategy.

Control operates at multiple timescales. Local regulation occurs during a specific task, such as slowing down after noticing uncertainty in a difficult sentence. Global regulation operates across longer periods and may involve decisions about how to distribute study time or when to switch strategies.

Effective control requires closing the loop between prediction and outcome. When the prediction and the outcome diverge, the discrepancy becomes a calibration signal that can alter future behavior.
"""

DOCS["psych/judgment_of_learning.md"] = """# Judgment of Learning

A judgment of learning (JOL) is an estimate, made after studying an item, of the likelihood that it will be remembered later. JOLs can guide study allocation: items judged weak receive additional attention, while items judged mastered may be set aside.

The difficulty is that the cues used to make these judgments are not always diagnostic. Fluency, recent exposure, and ease of processing can make an item feel available even when durable retrieval has not been established.

By contrast, an effortful attempt to recall an idea can feel less successful while producing information that is more useful for later control. Retrieval practice improves both memory and calibration because it exposes the learner to evidence about what can actually be produced from memory.

When prediction and outcome diverge repeatedly, the discrepancy becomes a calibration signal. Over time, repeated signals reveal whether a learner systematically overestimates or underestimates their own knowledge.
"""

DOCS["psych/retrieval_practice.md"] = """# Retrieval Practice and the Testing Effect

Retrieval practice is the act of attempting to recall information from memory rather than simply rereading it. The testing effect refers to the finding that retrieval attempts improve later retention more than additional study time.

An effortful recall attempt can feel less successful than rereading while producing information that is more useful for later control. Retrieval practice exposes the learner to evidence about what can actually be produced from memory rather than what merely feels familiar.

Retrieval practice improves calibration because it replaces fluency-based judgments with performance-based evidence. A learner who practices retrieval observes actual failures and successes instead of inferred competence.

Under high cognitive load, the benefits of retrieval practice interact with working memory constraints. The retrieval attempt itself consumes resources, which may leave fewer resources for monitoring the outcome.
"""

DOCS["psych/working_memory.md"] = """Working memory is the limited-capacity system that holds and manipulates information during complex cognitive activity.

Working memory is heavily involved in metacognitive monitoring because evaluating performance requires holding the task, the strategy, and the outcome in mind simultaneously. When working memory is occupied, monitoring accuracy deteriorates.

Capacity limits constrain how many pieces of information can be processed at once. A student solving a multistep statistics problem while trying to remember an unfamiliar formula may recognize that an error has occurred but fail to identify which step produced it.

The interaction between working memory and cognitive load determines how much attention remains available for monitoring and control. Tasks with high intrinsic complexity leave fewer resources for evaluating the quality of one's own performance.
"""

DOCS["psych/cognitive_load.md"] = """# Cognitive Load

Cognitive load theory distinguishes intrinsic load, which is imposed by the complexity of the material itself, from extraneous load, which is imposed by the manner in which the material is presented.

Under high cognitive load, the learner has fewer resources available for simultaneously performing a task, evaluating performance, and deciding what to do next. Monitoring accuracy deteriorates because the resource pool is shared.

Load affects metacognitive judgment in measurable ways. When a task consumes most available working memory capacity, learners may complete procedures correctly while attributing success to the wrong strategy.

Instructional design can reduce extraneous load by presenting information in formats that minimize unnecessary processing. The goal is to reserve capacity for the monitoring and control processes that support learning.
"""

DOCS["psych/source_monitoring.md"] = """# Source Monitoring

Source monitoring refers to the processes involved in attributing remembered information to its origin. A learner may remember a fact while being confused about whether it came from a lecture, a textbook, or their own inference.

Repeated difficulty with source monitoring can reveal systematic patterns. A learner who discovers that information is remembered while its origin is confused may adopt a broader strategy such as recording the source of each claim during note taking.

Source monitoring errors are a known contributor to misattribution in academic settings. The representation of a claim includes both its content and its provenance, and either can degrade independently.

Repeated local errors contribute evidence to a more stable control policy. Observations from specific episodes accumulate into a representation that can alter future study behavior.
"""

DOCS["psych/self_regulated_learning.md"] = """# Self-Regulated Learning

Self-regulated learning describes the cyclical processes by which learners set goals, monitor progress, and adapt their strategies. Effective self-regulated learning depends on closing the loop between prediction, performance, and outcome.

A practical sequence is to make an initial prediction, attempt retrieval or performance, compare the result with the prediction, and then update the next action. The discrepancy between prediction and outcome becomes a calibration signal.

Confidence must not substitute for evidence. A learner who trusts a feeling of familiarity rather than observed performance may systematically overestimate knowledge.

The realistic objective is not perfect introspection. Human monitoring is inherently limited, and some mental processes remain inaccessible to conscious report. The goal is a control process that responds to observable evidence: successful recall, specific errors, response latency, and changes across repeated attempts.
"""

DOCS["systems/worker_pools.md"] = """# Worker Pools and Task Queues

A worker pool is a fixed set of processes that consume tasks from a shared queue. Each worker owns one durable stage of processing; the system as a whole moves documents through a sequence of stages.

Backpressure matters when the queue grows faster than workers drain it. The system must bound how quickly work is submitted so that no single component is overwhelmed.

Workers poll the queue for undelivered events and mark each event as delivered when claimed. If a worker fails before completing its stage, the event can be redelivered because the idempotency key makes repeated processing safe.

The model treats every mutation as content-addressed. Replaying identical input must not create a second logical result, so every stage commits through receipts that record what was written.
"""

DOCS["systems/retrieval_pipelines.md"] = """# Retrieval Pipelines

A retrieval pipeline combines several lanes: a document router, a parent summary lane, and a global child lane. Document routing is never a recall gate: a child hit survives even when its document scores zero.

The pipeline fuses per-lane rankings with reciprocal-rank fusion. Each hit carries the representation kind and contract that produced it, so provenance is auditable at every stage.

A retrieval pipeline must descend deterministically from a routed document to its parent and child evidence. Document identity, parent identity, and chunk identity are linked by stable identifiers rather than filename guessing.

The pipeline serves answers through evidence bundles. Graph evidence augments textual retrieval; textual passages answer independently when the graph has nothing to contribute.
"""

DOCS["systems/vector_indexes.md"] = """# Vector Indexes and Dense Search

A vector index stores dense embeddings of document chunks and supports approximate nearest-neighbor search. Each point carries payload fields that identify the corpus, document, parent, and chunk.

Embedding contracts are versioned by content hash. A contract bump creates a new index version rather than mutating the existing collection, because different contracts have different dimensions.

The index is a disposable projection. The authoritative store retains the chunk text and identity; the index can be deleted and reconstructed exactly from that authority.

Search across collections must respect the active contract. Collections from other contract versions must never be queried with the wrong vectors, and corpus scoping filters targets to the requested corpus.
"""

DOCS["systems/verification_loops.md"] = """# Verification Loops

A verification loop reconciles projected state against authoritative state. It compares desired artifacts with store contents and classifies differences as missing or orphaned.

When the store lost an artifact, the verification loop clears the corresponding receipt so the scheduler can re-drive the projector. When the store holds an orphan artifact, the loop deletes it.

Receipts are the commit point for projections. A crash between a graph write and its receipt leaves an orphan that verification detects; silence is never acceptance.

The loop must distinguish intentional absence from loss. Facts whose endpoints never earned durable identity are parked in the authoritative store and are not projection failures.
"""

DOCS["systems/document_ingestion.md"] = """# Document Ingestion and Chunking

Document ingestion converts source files into normalized text, then chunks the text into parent and child chunks. Parents hold section summaries; children hold retrievable passages.

Every document receives a content-derived identity. Identical bytes produce the same document identity regardless of filename or upload time, and a manifest may declare what should be ingested without duplicating it.

Native formats are materialized deterministically. A PDF, EPUB, or DOCX produces normalized text plus a structural source map that records page or chapter lineage.

Chunking parameters are frozen. Changing them would change child identities and invalidate projections, so the chunker contract is versioned and stable.
"""

DOCS["systems/platform_services.md"] = """# Platform Services and Contracts

Platform services expose versioned contracts over the network. Every cross-process payload conforms to a schema, and private package imports never cross process boundaries.

A service owns one responsibility. One process owns user intake and reads; another owns scheduling; workers own single durable stages; stores own persistence engines.

Contracts change through versioning, not mutation. A contract bump is a new version with explicit compatibility, and every reverse dependent is verified before the new version activates.

The platform keeps model processes host-native. Models never run inside containers, and one sidecar process loads one model release.
"""

DOCS["systems/fault_tolerance.md"] = """# Fault Tolerance and Recovery

Fault tolerance begins with idempotent processing. Every durable mutation uses canonical content identity, so replaying identical input cannot create a second logical result.

Stage artifacts, receipts, status transitions, and outbox events commit in one transaction. A crash cannot leave a partial stage recorded as complete.

Recovery is driven by a census that compares desired state with observed state. Missing receipts re-arm their stage; failed stages retry up to a bound; orphans are removed deterministically.

Degraded states are observable, not hidden. A run that has not converged remains visible to the operator, and no false completion state exists.
"""

DOCS["cyber/zero_trust.md"] = """# Zero Trust Architecture

Zero trust abandons the assumption that anything inside the network perimeter is trusted. Every request is authenticated and authorized independently, regardless of its origin.

Identity is the primary perimeter. Each principal carries a verifiable identity, and access decisions evaluate the request, the resource, and the context together.

Network segmentation shrinks the blast radius of compromise. Lateral movement becomes harder when services cannot reach each other by default.

Zero trust also applies to data. Encrypting data at rest and in transit reduces the value of a successful breach, and audit logs make unauthorized access observable.
"""

DOCS["cyber/incident_response.md"] = """# Incident Response

Incident response proceeds through phases: preparation, detection, containment, eradication, and recovery. Each phase has defined outputs that feed the next.

Detection relies on monitoring. Logs from endpoints, network devices, and services feed a detection system that alerts on anomalies.

Containment limits the spread of a compromise. Isolating affected systems and revoking credentials stops lateral movement while investigators preserve evidence.

The response process itself must be practiced. Tabletop exercises reveal gaps in the plan, and post-incident reviews turn failures into durable improvements.
"""

DOCS["cyber/encryption_basics.md"] = """# Encryption Basics

Encryption protects data confidentiality at rest and in transit. Data at rest is encrypted on disk; data in transit is encrypted by transport protocols such as TLS.

Keys must be managed separately from the data they protect. A system that stores the key next to the ciphertext gains little from encryption.

Authenticated encryption binds confidentiality and integrity. The receiver can verify that the ciphertext was not modified, which prevents a class of tampering attacks.

Encryption does not remove the need for access control. Authorized users can still mishandle plaintext, and monitoring remains necessary to detect misuse.
"""

DOCS["cyber/authentication.md"] = """# Authentication and Sessions

Authentication establishes who a user is; authorization decides what they may do. Multi-factor authentication combines something the user knows with something they have or are.

Sessions must be bounded. Expiring tokens, revocation lists, and refresh mechanisms limit the damage of a stolen credential.

Credential storage must resist offline attacks. Passwords are stored as salted hashes with a slow key-derivation function, never in plaintext.

Authentication events feed the monitoring system. Unusual login patterns are among the earliest observable signals of account compromise.
"""

DOCS["cyber/threat_modeling.md"] = """# Threat Modeling

Threat modeling identifies what an adversary might do before the adversary does it. The process enumerates assets, entry points, and trust boundaries, then reasons about attack paths.

A structured approach such as STRIDE organizes threats into spoofing, tampering, repudiation, information disclosure, denial of service, and elevation of privilege.

The output of threat modeling is a prioritized list of mitigations. Each mitigation is traceable to a specific threat, and unmitigated risks are recorded as accepted risk rather than ignored.

Threat models decay as the system changes. A new feature changes the attack surface, so the model must be revisited whenever the architecture changes.
"""

DOCS["cyber/security_monitoring.md"] = """# Security Monitoring

Security monitoring collects logs from endpoints, services, and network devices, then correlates them into alerts. The value of monitoring depends on what is logged and how long it is retained.

Alerts must be actionable. An alert that fires constantly without consequence trains responders to ignore the system.

The monitoring system itself is a target. An adversary who deletes logs erases the evidence of their activity, so log integrity and off-system storage matter.

Baselines make anomalies visible. Knowing what normal looks like is a prerequisite for noticing what abnormal looks like.
"""

DOCS["knowledge/knowledge_graphs.md"] = """# Knowledge Graphs

A knowledge graph represents entities and relations as nodes and edges. Compiler facts are extracted deterministically from evidence, and each fact carries its evidence provenance.

Canonicalization merges duplicate entity surfaces within a corpus into canonical identities. Membership records preserve which local entities contributed to each canonical entity.

Graph expansion is bounded and policy-driven. Traversal follows directed relations from authorized seeds, never inventing orientation or exceeding hop limits.

The graph is a disposable projection of the authoritative store. It can be deleted and reconstructed exactly, because every node and edge carries the authoritative identity.
"""

DOCS["knowledge/embedding_models.md"] = """# Embedding Models

Embedding models map text into dense vectors such that similar meanings land near each other. Query vectors are embedded with the same model and compared with stored document vectors.

Model releases are pinned. A projection records which model produced its vectors, and switching models is a contract bump rather than an in-place change.

Embedding quality interacts with chunking. A chunk that mixes topics produces a vector that represents none of them well, which is why parent and child chunks carry separate summaries and vectors.

Similarity search is only as good as its corpus scope. Searching across the wrong corpus yields results that look relevant but carry the wrong provenance.
"""

DOCS["knowledge/reranking.md"] = """# Reranking and Fusion

Reranking reorders candidate results using a cross-representation model that reads the query and candidate together. The fused candidate set is reranked, but per-lane ablations stay untouched.

Reciprocal-rank fusion combines lanes before reranking. Each lane contributes its ranking, and the fusion favors items that multiple lanes agree on.

Rerankers fail loudly. If the reranker is unavailable, the request fails with an explicit error rather than silently falling back to unfiltered candidates.

Reranking improves precision without changing recall: the candidate set is fixed before reranking, and only the ordering changes.
"""

DOCS["knowledge/retrieval_evaluation.md"] = """# Retrieval Evaluation

Retrieval evaluation measures whether the right evidence surfaces for a query. Precision and recall are computed against annotated relevance judgments.

A benchmark stops being held out after its results influence implementation. Frozen fixtures, answer keys, and scorers are hashed, and their exposure history is recorded.

Evaluation must distinguish development-set regressions from independent qualification. Reusing the same set for tuning and final judgment inflates the result.

Per-lane ablations reveal where quality comes from. Document routing, dense search, lexical search, and graph expansion are measured separately before fusion is judged.
"""

DOCS["knowledge/corpus_management.md"] = """# Corpus Management

Corpus management controls what enters a corpus and how it is tracked. A manifest declares the sources to ingest; the control plane decides what remains to be done.

Content identity, not modification time, is the authority. A changed file is a new content version, and the old version remains historically attributable through its document row.

A manifest is an ingestion declaration, not a destructive reconciliation. Documents absent from a later manifest are not deleted without an explicit deletion design.

Bulk ingestion submits ordinary intake work. The same pipeline that ingests one document ingests a thousand, with no second implementation.
"""

DOCS["knowledge/evidence_bundles.md"] = """# Evidence Bundles

An evidence bundle assembles the support for an answer from typed lanes. Graph evidence carries compiler facts; text evidence carries summaries and retrieved passages.

Either lane may support an answer independently. Graph evidence augments textual retrieval, but it never gates it, and answers abstain only when both lanes are empty.

Every claim in a bundle is traceable to fact and entity identifiers, the source document, the exact evidence span, and the retrieval lane that produced it.

Citations reference bundle items rather than merely documents. A grounded answer can always point at the passage or fact that supports it.
"""

DOCS["knowledge/graph_traversal.md"] = """# Graph Traversal Policy

Graph traversal policy bounds how graph evidence is gathered. Expansion starts from authorized seeds and follows a directed relation set with a fixed hop limit.

Seed authorization is corpus-scoped. Seeds resolve from entities attached to evidence within the active corpus, never from raw surface matching against the unrestricted graph.

Directed expansion preserves stored orientation. An incoming edge only makes the existing fact eligible; it never reverses or invents a relation.

Traversal policy is frozen until measured qualification demonstrates a defect. Hop limits and predicate allowlists change only with evidence.
"""

FORMAT_CONVERSIONS = {
    "txt": ["psych/working_memory.md", "cyber/authentication.md", "knowledge/corpus_management.md"],
    "html": ["systems/fault_tolerance.md", "cyber/threat_modeling.md"],
    "docx": ["cyber/zero_trust.md", "knowledge/embedding_models.md"],
    "epub": ["psych/judgment_of_learning.md", "knowledge/knowledge_graphs.md"],
    "pdf": ["systems/retrieval_pipelines.md", "cyber/incident_response.md"],
}


def main() -> int:
    for rel, text in DOCS.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            continue
        path.write_text(text)

    for fmt, rels in FORMAT_CONVERSIONS.items():
        for rel in rels:
            src = ROOT / rel
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
                    subprocess.run(
                        ["cupsfilter", "-m", "application/pdf", str(tmp)],
                        stdout=out, check=True,
                    )
                tmp.unlink()
            src.unlink()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
