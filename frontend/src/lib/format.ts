// ─── Number formatters used across the dashboard ───
export const fmtUSD = (n: number, compact = true) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(n);

export const fmtNum = (n: number, compact = false) =>
  new Intl.NumberFormat("en-US", {
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(n);

export const fmtPct = (n: number, digits = 1) =>
  `${(n * 100).toFixed(digits)}%`;

export const fmtPctRaw = (n: number, digits = 1) =>
  `${n.toFixed(digits)}%`;

export const fmtCoord = (n: number) => n.toFixed(4);
