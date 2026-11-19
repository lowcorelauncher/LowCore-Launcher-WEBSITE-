import { describe, expect, it } from "vitest";

import { PERFORMANCE_STATS, SITE_PRODUCT_NAME } from "@/routes/index";

describe("LowCore Client homepage claims", () => {
  it("uses LowCore Client as the product name", () => {
    expect(SITE_PRODUCT_NAME).toBe("LowCore Client");
  });

  it("shows the confirmed footprint and memory figures", () => {
    expect(PERFORMANCE_STATS.map(({ value, label }) => [value, label])).toEqual([
      ["100 MB", "Client footprint"],
      ["~0.5 MB", "RAM at idle"],
      ["15–20 MB", "RAM in use"],
    ]);
  });
});