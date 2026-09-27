import { useId, useState } from "react";
import type { RetrievalReceipt } from "../lib/contracts";
import type { DeepAnswer } from "../lib/chat";
import { chunkIdOf } from "../lib/chunkid";

/** FRONTEND-REFRESH-V1 U4b — citation markers in an answer ([S1] from chat, [c1] from deep research) become focusable
 *  chips with a hover card: the source title, where in it, and the passage. No markdown package is added: a tiny remark
 *  step splits the markers out of text nodes. */

export interface CiteInfo { title: string; where: string; text: string }

const MARKER = /\[((?:S|c)\d{1,3})\]/g;

function str(v: unknown): string { return typeof v === "string" ? v : ""; }

/** tag → source, from a chat receipt's legend (tag → chunk id) and chunks (id → title, place, preview). */
export function chatCitations(receipt: RetrievalReceipt | null): Map<string, CiteInfo> {
  const out = new Map<string, CiteInfo>();
  if (!receipt) return out;
  const chunks = new Map<string, Record<string, unknown>>();
  for (const c of (receipt.chunks ?? []) as Record<string, unknown>[]) {
    const id = chunkIdOf(c);
    if (id) chunks.set(id, c);
  }
  for (const l of (receipt.legend ?? []) as Record<string, unknown>[]) {
    const tag = str(l.tag);
    const id = chunkIdOf(l);
    if (!tag) continue;
    const c = (id && chunks.get(id)) || {};
    out.set(tag, { title: str(c.title) || str(c.source_name) || id || tag,
                   where: str(l.breadcrumb) || str(c.heading_path) || str(c.human_locator) || str(l.locator),
                   text: str(c.preview) });
  }
  return out;
}

/** cid → source, from a deep research answer's resolved citations. */
export function deepCitations(deep: DeepAnswer | null | undefined): Map<string, CiteInfo> {
  const out = new Map<string, CiteInfo>();
  for (const c of deep?.citations ?? []) out.set(c.cid, { title: c.title || c.id || c.cid, where: c.source ?? "", text: c.text ?? "" });
  return out;
}

interface MdNode { type: string; value?: string; children?: MdNode[]; data?: Record<string, unknown> }

/** remark step: "…fact [S1]." → text, a cite-ref element, text. Code and links are left alone. */
export function remarkCitations() {
  const walk = (node: MdNode): void => {
    if (!node.children || node.type === "code" || node.type === "inlineCode" || node.type === "link") return;
    const next: MdNode[] = [];
    for (const child of node.children) {
      if (child.type !== "text" || !child.value || !MARKER.test(child.value)) {
        walk(child);
        next.push(child);
        continue;
      }
      MARKER.lastIndex = 0;
      let last = 0;
      for (const m of child.value.matchAll(MARKER)) {
        if (m.index! > last) next.push({ type: "text", value: child.value.slice(last, m.index) });
        next.push({ type: "citeRef", data: { hName: "cite-ref", hProperties: { tag: m[1] } }, children: [{ type: "text", value: m[1] ?? "" }] });
        last = m.index! + m[0].length;
      }
      if (last < child.value.length) next.push({ type: "text", value: child.value.slice(last) });
    }
    node.children = next;
  };
  return (tree: MdNode) => { walk(tree); };
}

export function CiteRef({ tag, info }: { tag: string; info: CiteInfo | undefined }) {
  const [pinned, setPinned] = useState(false);
  const id = useId();
  const label = info ? `Source ${tag}: ${info.title}` : `Source ${tag}`;
  return (
    <span className={`cite${pinned ? " cite--open" : ""}`}>
      <button type="button" className="cite__btn" aria-label={label} aria-describedby={info ? id : undefined}
              aria-expanded={pinned} onClick={() => setPinned((p) => !p)}>
        [{tag}]
      </button>
      {info && (
        <span className="cite__card" role="tooltip" id={id}>
          <strong>{info.title}</strong>
          {info.where && <span className="faint">{info.where}</span>}
          {info.text && <span className="cite__text">{info.text.length > 420 ? `${info.text.slice(0, 419)}…` : info.text}</span>}
        </span>
      )}
    </span>
  );
}
