import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FE_ROOT = join(__dirname, "../..");

function stripTsComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

function walkTs(dir: string, acc: string[]): void {
  for (const name of readdirSync(dir)) {
    if (name === "__tests__" || name.startsWith(".")) {
      continue;
    }
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) {
      walkTs(p, acc);
    } else if (name.endsWith(".tsx") || (name.endsWith(".ts") && !name.endsWith(".d.ts"))) {
      acc.push(p);
    }
  }
}

/** User-visible copy must not regress to internal "definition(s)" wording (C12: paths/types unchanged). */
const DISALLOWED_SUBSTRINGS = [
  "Agent definitions",
  "Your definitions",
  "Create definition",
  "Definition created",
  "No definitions yet",
  "← Definitions",
] as const;

describe("user-facing agent labels (dashboard + components)", () => {
  it("has no forbidden definition wording in UI source trees", () => {
    const dirs = [join(FE_ROOT, "app/dashboard"), join(FE_ROOT, "components")];
    const files: string[] = [];
    for (const d of dirs) {
      walkTs(d, files);
    }
    expect(files.length).toBeGreaterThan(5);

    for (const file of files) {
      const raw = readFileSync(file, "utf8");
      const src = stripTsComments(raw);
      for (const bad of DISALLOWED_SUBSTRINGS) {
        expect(
          src.includes(bad),
          `${file.replace(FE_ROOT + "/", "")} must not contain user-facing phrase: ${bad}`,
        ).toBe(false);
      }
    }
  });

  it("keeps positive Agents copy on key surfaces", () => {
    const sidebar = readFileSync(join(FE_ROOT, "components/command-center/sidebar.tsx"), "utf8");
    expect(sidebar).toMatch(/\bAgents\b/);
    const listPage = readFileSync(
      join(FE_ROOT, "app/dashboard/projects/[projectId]/agent-definitions/page.tsx"),
      "utf8",
    );
    expect(listPage).toContain("Your agents");
  });
});
