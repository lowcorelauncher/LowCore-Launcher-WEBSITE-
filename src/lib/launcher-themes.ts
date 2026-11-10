export type LauncherTheme = {
  name: string;
  background: string;
  surface: string;
  panel: string;
  border: string;
  text: string;
  muted: string;
  accent: string;
  accentText: string;
  success: string;
};

export const DEFAULT_LAUNCHER_THEME: LauncherTheme = {
  name: "Dark Mode",
  background: "#101114",
  surface: "#17191E",
  panel: "#1D2026",
  border: "#2B2E36",
  text: "#F2F3F5",
  muted: "#A8ABB4",
  accent: "#EA5B53",
  accentText: "#FFFFFF",
  success: "#70D6A5",
};

export const LAUNCHER_THEMES: LauncherTheme[] = [
  {
    name: "OLED Black",
    background: "#000000",
    surface: "#080808",
    panel: "#0D0D0D",
    border: "#252525",
    text: "#F5F5F5",
    muted: "#A3A3A3",
    accent: "#E85A52",
    accentText: "#FFFFFF",
    success: "#72D5A5",
  },
  DEFAULT_LAUNCHER_THEME,
  {
    name: "Light Mode",
    background: "#F1F2F4",
    surface: "#FFFFFF",
    panel: "#F8F8F9",
    border: "#D8DBE0",
    text: "#23252A",
    muted: "#626771",
    accent: "#D6453E",
    accentText: "#FFFFFF",
    success: "#25845A",
  },
  { name: "Catppuccin Mocha", background: "#1E1E2E", surface: "#181825", panel: "#242436", border: "#45475A", text: "#CDD6F4", muted: "#A6ADC8", accent: "#CBA6F7", accentText: "#1E1E2E", success: "#A6E3A1" },
  { name: "Catppuccin Macchiato", background: "#24273A", surface: "#1E2030", panel: "#2A2D42", border: "#494D64", text: "#CAD3F5", muted: "#A5ADCB", accent: "#C6A0F6", accentText: "#24273A", success: "#A6DA95" },
  { name: "Catppuccin Latte", background: "#EFF1F5", surface: "#E6E9EF", panel: "#F7F8FA", border: "#CCD0DA", text: "#4C4F69", muted: "#6C6F85", accent: "#8839EF", accentText: "#FFFFFF", success: "#40A02B" },
  { name: "Rose Pine", background: "#191724", surface: "#1F1D2E", panel: "#26233A", border: "#403D52", text: "#E0DEF4", muted: "#908CAA", accent: "#EB6F92", accentText: "#191724", success: "#9CCFD8" },
  { name: "Rose Pine Dawn", background: "#FAF4ED", surface: "#F2E9E1", panel: "#FFFAF3", border: "#DFDAD9", text: "#575279", muted: "#797593", accent: "#D7827E", accentText: "#FFFFFF", success: "#56949F" },
  { name: "Tokyo Night", background: "#1A1B26", surface: "#16161E", panel: "#24283B", border: "#414868", text: "#C0CAF5", muted: "#A9B1D6", accent: "#7AA2F7", accentText: "#1A1B26", success: "#9ECE6A" },
  { name: "Dracula", background: "#282A36", surface: "#21222C", panel: "#343746", border: "#44475A", text: "#F8F8F2", muted: "#BFBFBF", accent: "#BD93F9", accentText: "#282A36", success: "#50FA7B" },
  { name: "Nord", background: "#2E3440", surface: "#272C36", panel: "#3B4252", border: "#4C566A", text: "#ECEFF4", muted: "#D8DEE9", accent: "#88C0D0", accentText: "#2E3440", success: "#A3BE8C" },
  { name: "Gruvbox Dark", background: "#282828", surface: "#1D2021", panel: "#3C3836", border: "#504945", text: "#EBDBB2", muted: "#BDAE93", accent: "#FE8019", accentText: "#282828", success: "#B8BB26" },
  { name: "Solarized Dark", background: "#002B36", surface: "#073642", panel: "#0C3A46", border: "#586E75", text: "#FDF6E3", muted: "#93A1A1", accent: "#268BD2", accentText: "#FDF6E3", success: "#859900" },
  { name: "Solarized Light", background: "#FDF6E3", surface: "#EEE8D5", panel: "#FFFBF0", border: "#D3CBB7", text: "#586E75", muted: "#657B83", accent: "#268BD2", accentText: "#FFFFFF", success: "#859900" },
];