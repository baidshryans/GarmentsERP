import { describe, it, expect } from "vitest";
import { makeCanAccess, filterNavItems } from "./permissions";

describe("makeCanAccess", () => {
  it("superuser can access anything", () => {
    const can = makeCanAccess({ loaded: true, is_superuser: true, modules: {} });
    expect(can("sales.salesvou", "post")).toBe(true);
    expect(can("anything.atall", "delete")).toBe(true);
  });

  it("not-loaded is permissive (no flash-hide)", () => {
    const can = makeCanAccess({ loaded: false, is_superuser: false, modules: {} });
    expect(can("sales.salesvou", "list")).toBe(true);
  });

  it("grants only the verbs present in the map", () => {
    const can = makeCanAccess({
      loaded: true,
      is_superuser: false,
      modules: { "sales.salesvou": { list: true, post: false } },
    });
    expect(can("sales.salesvou", "list")).toBe(true);
    expect(can("sales.salesvou", "post")).toBe(false);
    expect(can("inventory.barcodemain", "list")).toBe(false);
  });

  it("defaults the verb to list", () => {
    const can = makeCanAccess({
      loaded: true,
      is_superuser: false,
      modules: { "inventory.barcodemain": { list: true } },
    });
    expect(can("inventory.barcodemain")).toBe(true);
  });
});

describe("filterNavItems", () => {
  const can = makeCanAccess({
    loaded: true,
    is_superuser: false,
    modules: { "sales.salesvou": { list: true, post: true } },
  });

  it("keeps untagged items", () => {
    const items = [{ title: "Plain", url: "/x" }];
    expect(filterNavItems(items, can)).toHaveLength(1);
  });

  it("drops a tagged leaf the user lacks", () => {
    const items = [
      { title: "Sales", url: "/s", module: "sales.salesvou", perm: "list" },
      { title: "Stock", url: "/k", module: "inventory.barcodemain", perm: "list" },
    ];
    const out = filterNavItems(items, can);
    expect(out.map((i) => i.title)).toEqual(["Sales"]);
  });

  it("filters children and drops a now-empty parent group", () => {
    const items = [
      {
        title: "Group",
        url: "#",
        items: [
          { title: "Allowed", url: "/a", module: "sales.salesvou" },
          { title: "Denied", url: "/d", module: "inventory.barcodemain" },
        ],
      },
      {
        title: "EmptyGroup",
        url: "#",
        items: [{ title: "Denied2", url: "/d2", module: "inventory.barcodemain" }],
      },
    ];
    const out = filterNavItems(items, can);
    expect(out).toHaveLength(1);
    expect(out[0].title).toBe("Group");
    expect(out[0].items.map((i) => i.title)).toEqual(["Allowed"]);
  });
});
