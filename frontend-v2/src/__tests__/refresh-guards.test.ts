import { readdirSync, readFileSync } from "node:fs";
import { expect, it } from "vitest";

/** FRONTEND-REFRESH-V1 U6 — the refresh's fixes stay fixed: no browser pop-ups, no retired color names, no hard-coded colors
 *  outside tokens.css, no fonts fetched from Google. Reads every source file under src/. */

const SRC = new URL("../", import.meta.url);
const files = readdirSync(SRC, { recursive: true })
  .filter((f) => /\.(tsx?|css)$/.test(f) && !f.includes("__tests__"))
  .map((f) => ({ name: f, text: readFileSync(new URL(f, SRC), "utf8") }));

function offenders(re: RegExp, skip: (name: string) => boolean = () => false): string[] {
  return files.filter((f) => !skip(f.name) && re.test(f.text)).map((f) => f.name);
}

it("reads the sources (a broken walk cannot pass silently)", () => {
  expect(files.length).toBeGreaterThan(20);
  expect(files.some((f) => f.name.endsWith("App.tsx"))).toBe(true);
});

it("uses dialogs, never window.prompt / confirm / alert", () => {
  expect(offenders(/window\.(prompt|confirm|alert)\s*\(/)).toEqual([]);
});

it("uses only the token names (the pre-refresh aliases are gone)", () => {
  expect(offenders(/var\(--(fg|fg-dim|fg-faint|bg-raised|bg-sunken|line|line-soft|accent-dim|ok-bg|warn-bg|bad-bg|unknown|unknown-bg|mono|sans|prose|r)\)/)).toEqual([]);
});

it("keeps every hex color in tokens.css", () => {
  expect(offenders(/#[0-9a-fA-F]{3,8}\b/, (n) => n.endsWith("styles/tokens.css"))).toEqual([]);
});

it("loads no font from Google", () => {
  expect(offenders(/fonts\.googleapis\.com|fonts\.gstatic\.com/)).toEqual([]);
});
