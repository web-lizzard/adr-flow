import { describe, expect, it } from "vitest";
import { adrToolbars } from "../app/components/adr/adr-editor-toolbars";

describe("adrToolbars", () => {
  it("includes preview, table, and task", () => {
    expect(adrToolbars).toContain("preview");
    expect(adrToolbars).toContain("table");
    expect(adrToolbars).toContain("task");
  });

  it("excludes image, mermaid, katex, and fullscreen", () => {
    expect(adrToolbars).not.toContain("image");
    expect(adrToolbars).not.toContain("mermaid");
    expect(adrToolbars).not.toContain("katex");
    expect(adrToolbars).not.toContain("fullscreen");
  });
});
