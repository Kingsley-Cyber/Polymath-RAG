// 0001_uniqueness.cypher
// Uniqueness constraints make MERGE atomic and idempotent under
// parallelism (docx §17, ADR-0002). Without these, concurrent MERGEs
// can both miss and double-create nodes.
//
// Applied automatically by the Neo4j projector at startup; this file is
// the declarative authority for what the projector asserts.

CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

CREATE CONSTRAINT fact_id_unique IF NOT EXISTS
FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;

CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;

CREATE CONSTRAINT doc_id_unique IF NOT EXISTS
FOR (d:Document) REQUIRE d.doc_id IS UNIQUE;
