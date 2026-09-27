/** The one Node API the token contrast test reads (the project installs no @types/node; vitest strips `.css?raw`). */
declare module "node:fs" {
  export function readFileSync(path: URL | string, encoding: "utf8"): string;
}
