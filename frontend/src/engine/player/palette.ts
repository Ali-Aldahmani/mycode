/**
 * Identity palettes. Green, red, yellow and gray are reserved for meaning
 * (kept / removed / changed / NaN), so identity colours avoid them.
 */
export const ROW_COLORS = [
  "#60a5fa", // blue
  "#c084fc", // purple
  "#f472b6", // pink
  "#22d3ee", // cyan
  "#fb923c", // orange
  "#818cf8", // indigo
  "#e879f9", // fuchsia
  "#38bdf8", // sky
  "#a78bfa", // violet
  "#f9a8d4", // light pink
  "#7dd3fc", // light sky
  "#fdba74", // light orange
];

export const COL_COLORS = [
  "#7dd3fc",
  "#c4b5fd",
  "#f0abfc",
  "#67e8f9",
  "#fdba74",
  "#a5b4fc",
  "#f9a8d4",
  "#93c5fd",
  "#d8b4fe",
];

export const rowColor = (i: number) => ROW_COLORS[((i % ROW_COLORS.length) + ROW_COLORS.length) % ROW_COLORS.length];
export const colColor = (i: number) => COL_COLORS[((i % COL_COLORS.length) + COL_COLORS.length) % COL_COLORS.length];
export const groupColor = (g: number) => rowColor(g * 3 + 1);
