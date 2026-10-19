export const MARKUP_MIN = 5;
export const MARKUP_MAX = 10;
export const MARKUP_DEFAULT = 7;

export class MarkupError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MarkupError";
  }
}

export type ChargeInput = {
  code?: string | null;
  description?: string | null;
  amount?: number | null;
};

export type RatedCharge = {
  code: string;
  description: string;
  baseAmount: number;
  customerAmount: number;
};

export type MarkupResult = {
  markupPercent: number;
  baseTotal: number;
  customerTotal: number;
  markupAmount: number;
  marginPercent: number;
  charges: RatedCharge[];
};

/** Round half-up (away from zero) to the nearest cent. */
export function roundCents(amount: number): number {
  if (!Number.isFinite(amount)) {
    throw new MarkupError("Amount must be a finite number.");
  }
  const sign = amount < 0 ? -1 : 1;
  const cents = Math.round(Math.abs(amount) * 100 + 1e-8);
  return (sign * cents) / 100;
}

function roundToTenth(amount: number): number {
  const sign = amount < 0 ? -1 : 1;
  const tenths = Math.round(Math.abs(amount) * 10 + 1e-8);
  return (sign * tenths) / 10;
}

/**
 * Accept 5% through 10% inclusive. Values are stored to a tenth of a percent
 * so the slider and the server agree. Numbers outside that range are rejected.
 */
export function normalizeMarkupPercent(value: unknown): number {
  const numeric =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim() !== ""
        ? Number(value)
        : Number.NaN;

  if (!Number.isFinite(numeric)) {
    throw new MarkupError("Markup percent must be a number.");
  }
  if (numeric < MARKUP_MIN - 1e-9 || numeric > MARKUP_MAX + 1e-9) {
    throw new MarkupError(`Markup must be between ${MARKUP_MIN}% and ${MARKUP_MAX}%.`);
  }
  const rounded = roundToTenth(numeric);
  if (rounded < MARKUP_MIN || rounded > MARKUP_MAX) {
    throw new MarkupError(`Markup must be between ${MARKUP_MIN}% and ${MARKUP_MAX}%.`);
  }
  return rounded;
}

function reconcileToTotal(lines: RatedCharge[], customerTotal: number): void {
  if (lines.length === 0) return;
  const sumCents = lines.reduce((sum, line) => sum + Math.round(line.customerAmount * 100), 0);
  let diffCents = Math.round(customerTotal * 100) - sumCents;
  if (diffCents === 0) return;

  let index = 0;
  let largest = -1;
  lines.forEach((line, i) => {
    const magnitude = Math.abs(Math.round(line.baseAmount * 100));
    if (magnitude > largest) {
      largest = magnitude;
      index = i;
    }
  });
  lines[index].customerAmount = roundCents(lines[index].customerAmount + diffCents / 100);
}

/**
 * Mark up the carrier total, then scale every itemized charge by the same
 * factor. A remainder line is added when the carrier's charges do not already
 * foot to the total. Penny rounding is applied to the largest charge so the
 * lines still add up to the customer total.
 */
export function applyMarkup(
  total: number,
  charges: ChargeInput[] | null | undefined,
  markupPercentInput: unknown,
): MarkupResult {
  if (!Number.isFinite(total)) {
    throw new MarkupError("Rate total must be a finite number.");
  }

  const markupPercent = normalizeMarkupPercent(markupPercentInput);
  const factor = 1 + markupPercent / 100;
  const baseTotal = roundCents(total);
  const customerTotal = roundCents(baseTotal * factor);
  const markupAmount = roundCents(customerTotal - baseTotal);
  const marginPercent =
    customerTotal === 0 ? 0 : Math.round((markupAmount / customerTotal) * 10000) / 100;

  const normalized: RatedCharge[] = (charges ?? [])
    .filter((charge) => typeof charge?.amount === "number" && Number.isFinite(charge.amount))
    .map((charge) => ({
      code: (charge.code || "CHG").trim() || "CHG",
      description: (charge.description || "Charge").trim() || "Charge",
      baseAmount: roundCents(charge.amount as number),
      customerAmount: 0,
    }));

  if (normalized.length > 0) {
    const baseSum = roundCents(normalized.reduce((sum, line) => sum + line.baseAmount, 0));
    const remainder = roundCents(baseTotal - baseSum);
    if (remainder !== 0) {
      normalized.push({
        code: "OTHER",
        description: "Other charges",
        baseAmount: remainder,
        customerAmount: 0,
      });
    }
  }

  for (const line of normalized) {
    line.customerAmount = roundCents(line.baseAmount * factor);
  }
  reconcileToTotal(normalized, customerTotal);

  return {
    markupPercent,
    baseTotal,
    customerTotal,
    markupAmount,
    marginPercent,
    charges: normalized,
  };
}
