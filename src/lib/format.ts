export function formatMoney(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatPercent(amount: number): string {
  return `${new Intl.NumberFormat("en-US", {
    minimumFractionDigits: Number.isInteger(amount) ? 0 : 1,
    maximumFractionDigits: 2,
  }).format(amount)}%`;
}

/** Calendar date from a YYYY-MM-DD or date-time string, without timezone shift. */
export function formatLongDate(value: string | null | undefined): string {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatTransitDays(days: number | null | undefined): string {
  if (days === null || days === undefined || !Number.isFinite(days)) return "—";
  if (days === 1) return "1 day";
  return `${days} days`;
}

export function formatServiceLevel(code: string | null | undefined, description?: string | null): string {
  const readable = description?.trim();
  if (readable) return readable;
  const raw = (code || "").trim();
  if (!raw) return "Standard";
  if (/^[A-Z0-9 ]+$/.test(raw) && /[A-Z]/.test(raw)) {
    return raw
      .toLowerCase()
      .replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
  }
  return raw.replaceAll("_", " ");
}

export function todayIsoDate(now = new Date()): string {
  const copy = new Date(now);
  const month = String(copy.getMonth() + 1).padStart(2, "0");
  const day = String(copy.getDate()).padStart(2, "0");
  return `${copy.getFullYear()}-${month}-${day}`;
}

export function nextBusinessDay(now = new Date()): string {
  const copy = new Date(now);
  copy.setDate(copy.getDate() + 1);
  while (copy.getDay() === 0 || copy.getDay() === 6) {
    copy.setDate(copy.getDate() + 1);
  }
  return todayIsoDate(copy);
}

export function customerPdfFilename(quoteDate: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(quoteDate);
  const stamp = match?.[1] ?? "quote";
  return `EasyPost-Freight-Quote-${stamp}.pdf`;
}

export function formatWeight(pounds: number): string {
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(pounds)} lb`;
}

export function formatDimensions(length: number, width: number, height: number): string {
  const n = (value: number) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
  return `${n(length)} × ${n(width)} × ${n(height)} in`;
}
