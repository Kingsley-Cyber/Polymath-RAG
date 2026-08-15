# Document Ingestion and Chunking

Document ingestion converts source files into normalized text, then chunks the text into parent and child chunks. Parents hold section summaries; children hold retrievable passages.

Every document receives a content-derived identity. Identical bytes produce the same document identity regardless of filename or upload time, and a manifest may declare what should be ingested without duplicating it.

Native formats are materialized deterministically. A PDF, EPUB, or DOCX produces normalized text plus a structural source map that records page or chapter lineage.

Chunking parameters are frozen. Changing them would change child identities and invalidate projections, so the chunker contract is versioned and stable.
