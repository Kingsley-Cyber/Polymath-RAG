import type { CiteInfo } from "./Citations";
import { SourcesByBook } from "./deep/DeepReport";
import type { ChatGapCheck, ChatSynthesis } from "../lib/contracts";
import { confidenceOf, plural } from "../lib/deep";
import "../styles/deep.css";

/** FACET-RETRIEVAL-V1 F5 / F6 (register 11.545) — under a synthesis answer: a badge per facet of the request with its
 *  confidence from the documents the answer cites for it (the deep report's §11.4 badges: strong = two or more books, single
 *  source, contested), the sources by document (the deep report's own rendering; the [S#] chips resolve through the chat
 *  receipt) and the gap check's line. Rendered only when the turn carries `meta.synthesis`; older turns render as before. */
export function SynthesisPanel({ synthesis, gap, cites }: {
  synthesis: ChatSynthesis; gap?: ChatGapCheck | null; cites: Map<string, CiteInfo>;
}) {
  const facets = (synthesis.facets ?? []).filter((f) => f && typeof f === "object" && f.id);
  const books = (synthesis.sources ?? []).filter((s) => s && typeof s === "object");
  const claims = (gap?.claims ?? []).filter((c) => c && typeof c === "object");
  const found = claims.filter((c) => (c.found ?? 0) > 0).length;
  const multi = synthesis.documents?.multi_doc_sentences ?? 0;
  return (
    <div className="sources synthesis">
      {facets.length > 0 && (
        <div className="synthesis__facets" role="list" aria-label="Facets of the request">
          {facets.map((f) => {
            const conf = confidenceOf(f.confidence);
            const n = (f.docs ?? []).length;
            const why = conf?.why || (f.covered === false ? "No passage found this turn covered this part." : "The answer cites no passage for this part.");
            return (
              <span key={f.id} role="listitem" className="facet-chip" title={why}>
                <span className="facet-chip__name">{f.name || f.id}</span>
                {conf
                  ? <span className={`conf conf--${conf.key}`}>{conf.label}</span>
                  : <span className="conf conf--other">{f.covered === false ? "Not covered" : "Uncited"}</span>}
                {n > 0 && <span className="faint">{plural(n, "book")}</span>}
              </span>
            );
          })}
        </div>
      )}
      <div className="label">
        Sources by document{books.length ? ` (${books.length})` : ""}
        {multi > 0 && <span className="faint"> · {plural(multi, "sentence")} cite{multi === 1 ? "s" : ""} two or more books</span>}
      </div>
      <SourcesByBook books={books} cites={cites} />
      {claims.length > 0 && (
        <p className="gap-check faint">
          Gap check: {plural(claims.length, "claim")} searched again, {found ? `${found} found more in the library` : "none found more"}
          {gap?.section_added ? " — see “More on this”." : "."}
        </p>
      )}
    </div>
  );
}
