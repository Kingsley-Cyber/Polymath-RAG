# Vector Indexes and Dense Search

A vector index stores dense embeddings of document chunks and supports approximate nearest-neighbor search. Each point carries payload fields that identify the corpus, document, parent, and chunk.

Embedding contracts are versioned by content hash. A contract bump creates a new index version rather than mutating the existing collection, because different contracts have different dimensions.

The index is a disposable projection. The authoritative store retains the chunk text and identity; the index can be deleted and reconstructed exactly from that authority.

Search across collections must respect the active contract. Collections from other contract versions must never be queried with the wrong vectors, and corpus scoping filters targets to the requested corpus.
