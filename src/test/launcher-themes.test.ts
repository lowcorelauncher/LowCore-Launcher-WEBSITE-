import { describe, expect, it } from "vitest";

import { DEFAULT_LAUNCHER_THEME, LAUNCHER_THEMES } from "@/lib/launcher-themes";

describe("launcher theme preview presets", () => {
  it("includes the 14 built-in themes requested for the preview", () => {
    expect(LAUNCHER_THEMES.map((theme) => theme.name)).toEqual([
      "OLED Black",
      "Dark Mode",
      "Light Mode",
      "Catppuccin Mocha",
      "Catppuccin Macchiato",
      "Catppuccin Latte",
      "Rose Pine",
      "Rose Pine Dawn",
      "Tokyo Night",
      "Dracula",
      "Nord",
      "Gruvbox Dark",
      "Solarized Dark",
      "Solarized Light",
    ]);
  });

  it("defaults to Dark Mode", () => {
    expect(DEFAULT_LAUNCHER_THEME.name).toBe("Dark Mode");
  });

  it("uses true black for OLED Black", () => {
    expect(LAUNCHER_THEMES[0]?.background).toBe("#000000");
  });
});