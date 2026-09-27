import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

/** FRONTEND-REFRESH-V1 U1 — the gate on the design tokens: every text color is readable (WCAG 4.5:1) on every surface it
 *  sits on, and control edges are visible (3:1), in light AND dark, for every accent. Parses src/styles/tokens.css itself. */

type Palette = Record<string, string>;
const CSS = readFileSync(new URL("../styles/tokens.css", import.meta.url), "utf8");
const MODES = ["light", "dark"] as const;
const ACCENTS = ["indigo", "teal", "amber", "rose"] as const;

function blocks(): { selector: string; decls: Palette }[] {
  const out: { selector: string; decls: Palette }[] = [];
  const body = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [, selector = "", inner = ""] of body.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const decls: Palette = {};
    for (const [, name, value] of inner.matchAll(/(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;/g)) if (name && value) decls[name] = value;
    out.push({ selector: selector.trim(), decls });
  }
  return out;
}

function palette(mode: (typeof MODES)[number], accent: (typeof ACCENTS)[number]): Palette {
  const all = blocks();
  const base = all.find((b) => b.selector.includes(`[data-mode="${mode}"]`) && !b.selector.includes("data-accent"));
  const acc = all.find((b) => b.selector === `:root[data-mode="${mode}"][data-accent="${accent}"]`);
  expect(base, `base ${mode}`).toBeDefined();
  if (accent !== "indigo") expect(acc, `${mode} ${accent}`).toBeDefined();
  return { ...base!.decls, ...(acc?.decls ?? {}) };
}

function luminance(hex: string): number {
  const [r = 0, g = 0, b = 0] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const la = luminance(a), lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

function tok(p: Palette, name: string): string {
  const v = p[name];
  if (!v) throw new Error(`token ${name} missing`);
  return v;
}

const TEXT_ON: [string, string[]][] = [
  ["--text", ["--bg", "--surface", "--surface-2"]],
  ["--text-2", ["--bg", "--surface", "--surface-2", "--neutral-soft"]],
  ["--text-3", ["--bg", "--surface", "--surface-2"]],
  ["--accent", ["--bg", "--surface", "--accent-soft"]],
  ["--on-accent", ["--accent"]],
  ["--ok", ["--surface", "--ok-soft"]],
  ["--warn", ["--surface", "--warn-soft"]],
  ["--bad", ["--surface", "--bad-soft"]],
];
const EDGES_ON: [string, string[]][] = [["--border-control", ["--bg", "--surface", "--surface-2"]]];

describe.each(MODES)("%s mode", (mode) => {
  it.each(ACCENTS)("every text pair is at least 4.5:1 and every control edge 3:1 with %s", (accent) => {
    const p = palette(mode, accent);
    const failures: string[] = [];
    for (const [fg, bgs] of TEXT_ON) {
      for (const bg of bgs) {
        const r = contrast(tok(p, fg), tok(p, bg));
        if (r < 4.5) failures.push(`${fg} on ${bg}: ${r.toFixed(2)}`);
      }
    }
    for (const [fg, bgs] of EDGES_ON) {
      for (const bg of bgs) {
        const r = contrast(tok(p, fg), tok(p, bg));
        if (r < 3) failures.push(`${fg} on ${bg}: ${r.toFixed(2)}`);
      }
    }
    expect(failures).toEqual([]);
  });
});

it("the parser sees every color token in both modes (a renamed token cannot silently skip the gate)", () => {
  for (const mode of MODES) {
    const p = palette(mode, "indigo");
    for (const t of ["--bg", "--surface", "--surface-2", "--text", "--text-2", "--text-3", "--accent", "--accent-soft",
      "--on-accent", "--ok", "--ok-soft", "--warn", "--warn-soft", "--bad", "--bad-soft", "--border-control", "--neutral-soft"]) {
      expect(p[t], `${mode} ${t}`).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  }
});

it("the computation matches known WCAG values", () => {
  expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
  expect(contrast("#777777", "#FFFFFF")).toBeCloseTo(4.48, 1);
});
