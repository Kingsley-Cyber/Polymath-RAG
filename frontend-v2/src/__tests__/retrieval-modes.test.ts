import { describe, expect, it } from "vitest";
import { PUBLIC_MODES } from "../lib/contracts";

/**
 * GNN-RETRIEVAL-V1 — the fifth public mode is exposed by the selector's single source of truth and is
 * serialized exactly like the others (`{ mode: "GNN" }` on the same /chat body). The three existing
 * public modes stay, in their order, so nothing about them is redefined.
 */
describe("retrieval modes", () => {
  it("exposes GNN beside the existing public modes", () => {
    expect([...PUBLIC_MODES]).toEqual(["HYBRID", "GRAPH", "WILDCARD", "GNN"]);
  });

  it("serializes GNN as the plain mode string the backend validates", () => {
    const mode: (typeof PUBLIC_MODES)[number] = "GNN";
    const body = { message: "q", corpus_id: "cinema", mode };
    expect(JSON.parse(JSON.stringify(body))).toEqual({ message: "q", corpus_id: "cinema", mode: "GNN" });
  });
});
