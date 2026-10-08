import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { brand } from "./brand";

describe("the product name", () => {
  it("is Cynergi, with the lowercase wordmark", () => {
    expect(brand.name).toBe("Cynergi");
    expect(brand.displayName).toBe("Cynergi");
    expect(brand.wordmark).toBe("cynergi");
  });

  it("appears nowhere in the web app under its old name (comments aside)", () => {
    const oldName = /Skill ?Buddy|skill-buddy|skillbuddy/i;
    const hits: string[] = [];
    function scan(dir: string) {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const path = join(dir, entry.name);
        if (entry.isDirectory()) scan(path);
        else if (/\.(tsx?|css|svg)$/.test(entry.name) && !entry.name.includes(".test.")) {
          const code = readFileSync(path, "utf8")
            .replace(/\/\*[\s\S]*?\*\//g, "")
            .replace(/^\s*\/\/.*$/gm, "");
          if (oldName.test(code)) hits.push(path);
        }
      }
    }
    for (const dir of ["app", "components", "lib"]) scan(resolve(process.cwd(), dir));
    expect(hits).toEqual([]);
  });
});
