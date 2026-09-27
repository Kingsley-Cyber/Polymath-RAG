/** The Node APIs the source-reading tests use (the project installs no @types/node; vitest stubs `.css?raw`). */
declare module "node:fs" {
  export function readFileSync(path: URL | string, encoding: "utf8"): string;
  export function readdirSync(path: URL | string, options: { recursive: true }): string[];
}
