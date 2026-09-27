import type { Sentence } from "../../lib/deep";

/** DEEP-RESEARCH-MODE-V1 §11.2 part 3 (DR7d) — the audit's marks in the rendered prose. A remark step that runs BEFORE
 *  remarkCitations, while text nodes still carry their source offsets: each uncited sentence (a [start, end) range of the whole
 *  report) is wrapped, piece by piece, in an `uncited-mark` element (the dotted underline), and an `uncited-note` element
 *  ("no citation") follows the sentence's last piece. `base` is where this Markdown part starts in the whole prose (the TL;DR
 *  box renders a slice of it). A text node whose source is not its literal text (escapes, entities) is marked whole when the
 *  sentence covers most of it. Code, links' insides and headings are never marked. */

interface MdNode {
  type: string; value?: string; children?: MdNode[]; data?: Record<string, unknown>;
  position?: { start?: { offset?: number }; end?: { offset?: number } };
}

const text = (value: string): MdNode => ({ type: "text", value });
const mark = (value: string): MdNode => ({ type: "uncitedMark", data: { hName: "uncited-mark" }, children: [text(value)] });
const note = (): MdNode => ({ type: "uncitedNote", data: { hName: "uncited-note" }, children: [text("no citation")] });

export function uncitedMarks(ranges: Sentence[], base: number, whole: string) {
  return () => (tree: MdNode) => {
    if (!ranges.length) return;
    const hits: { node: MdNode; s: number; e: number }[] = [];
    const walk = (n: MdNode): void => {
      for (const c of n.children ?? []) {
        if (["code", "inlineCode", "heading", "html", "link"].includes(c.type)) continue;
        const s = c.position?.start?.offset;
        const e = c.position?.end?.offset;
        if (c.type === "text") { if (typeof s === "number" && typeof e === "number") hits.push({ node: c, s: base + s, e: base + e }); }
        else walk(c);
      }
    };
    walk(tree);
    const notes = new Map<MdNode, Set<number>>();         // the last piece of each sentence carries its note
    ranges.forEach((r, k) => {
      const last = hits.filter((h) => h.s < r.end && h.e > r.start).pop();
      if (last) notes.set(last.node, (notes.get(last.node) ?? new Set()).add(k));
    });
    const replaced = new Map<MdNode, MdNode[]>();
    for (const h of hits) {
      const over = ranges.map((r, k) => ({ r, k })).filter(({ r }) => h.s < r.end && h.e > r.start);
      if (!over.length) continue;
      const out: MdNode[] = [];
      if (whole.slice(h.s, h.e) === (h.node.value ?? "")) {
        let at = h.s;
        for (const { r, k } of over) {
          const s = Math.max(r.start, h.s);
          const e = Math.min(r.end, h.e);
          if (s > at) out.push(text(whole.slice(at, s)));
          out.push(mark(whole.slice(s, e)));
          if (notes.get(h.node)?.has(k)) out.push(note());
          at = e;
        }
        if (at < h.e) out.push(text(whole.slice(at, h.e)));
      } else {
        const inside = over.reduce((n, { r }) => n + Math.min(r.end, h.e) - Math.max(r.start, h.s), 0);
        out.push(inside * 2 >= h.e - h.s ? mark(h.node.value ?? "") : text(h.node.value ?? ""));
        over.forEach(({ k }) => { if (notes.get(h.node)?.has(k)) out.push(note()); });
      }
      replaced.set(h.node, out);
    }
    const rebuild = (n: MdNode): void => {
      if (!n.children) return;
      n.children = n.children.flatMap((c) => {
        const r = replaced.get(c);
        if (r) return r;
        rebuild(c);
        return [c];
      });
    };
    rebuild(tree);
  };
}
