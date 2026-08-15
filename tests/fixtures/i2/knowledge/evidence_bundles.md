# Evidence Bundles

An evidence bundle assembles the support for an answer from typed lanes. Graph evidence carries compiler facts; text evidence carries summaries and retrieved passages.

Either lane may support an answer independently. Graph evidence augments textual retrieval, but it never gates it, and answers abstain only when both lanes are empty.

Every claim in a bundle is traceable to fact and entity identifiers, the source document, the exact evidence span, and the retrieval lane that produced it.

Citations reference bundle items rather than merely documents. A grounded answer can always point at the passage or fact that supports it.
