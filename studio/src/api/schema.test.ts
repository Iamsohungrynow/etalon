// V9: schema.ts is what openapi-typescript makes of the committed openapi.json.
// @vitest-environment node
import { readFileSync } from "node:fs";
import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";
import { expect, it } from "vitest";

it("V9: src/api/schema.ts is current (run `pnpm gen:api`)", async () => {
  const spec = JSON.parse(readFileSync(new URL("./openapi.json", import.meta.url), "utf-8"));
  const generated = COMMENT_HEADER + astToString(await openapiTS(spec));
  const committed = readFileSync(new URL("./schema.ts", import.meta.url), "utf-8");
  expect(committed.replace(/\r\n/g, "\n")).toBe(generated);
});
