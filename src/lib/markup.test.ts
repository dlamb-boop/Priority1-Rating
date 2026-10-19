import { describe, expect, it } from "vitest";
import { applyMarkup, MarkupError, normalizeMarkupPercent, roundCents } from "@/lib/markup";

describe("roundCents", () => {
  it("rounds half-up to the nearest cent, including tricky decimals", () => {
    expect(roundCents(1.004)).toBe(1);
    expect(roundCents(1.005)).toBe(1.01);
    expect(roundCents(1.015)).toBe(1.02);
    expect(roundCents(-1.005)).toBe(-1.01);
    expect(roundCents(252.4023)).toBe(252.4);
    expect(roundCents(302.2322)).toBe(302.23);
    expect(roundCents(10.005)).toBe(10.01);
  });
});

describe("normalizeMarkupPercent", () => {
  it("accepts the inclusive bounds and the default", () => {
    expect(normalizeMarkupPercent(5)).toBe(5);
    expect(normalizeMarkupPercent(10)).toBe(10);
    expect(normalizeMarkupPercent("7")).toBe(7);
    expect(normalizeMarkupPercent(7.04)).toBe(7);
    expect(normalizeMarkupPercent(6.96)).toBe(7);
  });

  it("rejects anything outside 5% to 10%", () => {
    for (const value of [4.99, 0, 10.01, 15, -7, Number.NaN, "nope", null, undefined]) {
      expect(() => normalizeMarkupPercent(value)).toThrow(MarkupError);
    }
  });
});

describe("applyMarkup", () => {
  it("marks up the spec sample total by 7% and keeps charges in balance", () => {
    const result = applyMarkup(
      235.89,
      [
        { code: "FSC", description: "Fuel Surcharge", amount: 39.46 },
        { code: "GFC", description: "Gross Freight Charge", amount: 196.43 },
      ],
      7,
    );
    expect(result.baseTotal).toBe(235.89);
    expect(result.customerTotal).toBe(252.4);
    expect(result.markupAmount).toBe(16.51);
    expect(result.charges.map((charge) => charge.customerAmount)).toEqual([42.22, 210.18]);
    const sum = roundCents(result.charges.reduce((total, charge) => total + charge.customerAmount, 0));
    expect(sum).toBe(result.customerTotal);
  });

  it("scales a discount and still foots to the marked-up total", () => {
    const result = applyMarkup(
      100,
      [
        { code: "ITEM", description: "Item Charge", amount: 150 },
        { code: "DSC", description: "Discount", amount: -50 },
      ],
      10,
    );
    expect(result.customerTotal).toBe(110);
    expect(result.charges.map((charge) => charge.customerAmount)).toEqual([165, -55]);
    expect(roundCents(result.charges.reduce((total, charge) => total + charge.customerAmount, 0))).toBe(110);
  });

  it("absorbs a rounding penny so lines match the customer total", () => {
    const result = applyMarkup(
      10,
      [
        { code: "A", description: "A", amount: 3.33 },
        { code: "B", description: "B", amount: 3.33 },
        { code: "C", description: "C", amount: 3.34 },
      ],
      5,
    );
    expect(result.customerTotal).toBe(10.5);
    expect(roundCents(result.charges.reduce((total, charge) => total + charge.customerAmount, 0))).toBe(10.5);
  });

  it("adds a remainder line when carrier charges do not foot to the total", () => {
    const result = applyMarkup(
      282.46,
      [
        { code: "FSC", description: "Fuel Surcharge", amount: 42.96 },
        { code: "HCSER", description: "High Cost Service Area Surcharge", amount: 60 },
        { code: "ITEM", description: "Item Charge", amount: 440.98 },
        { code: "DSC", description: "Discount", amount: -187.56 },
      ],
      7,
    );
    expect(result.customerTotal).toBe(302.23);
    expect(result.charges.some((charge) => charge.code === "OTHER")).toBe(true);
    expect(roundCents(result.charges.reduce((total, charge) => total + charge.customerAmount, 0))).toBe(302.23);
    expect(roundCents(result.charges.reduce((total, charge) => total + charge.baseAmount, 0))).toBe(282.46);
  });

  it("marks up a total that has no itemized charges", () => {
    const result = applyMarkup(80, [], 5);
    expect(result.customerTotal).toBe(84);
    expect(result.charges).toEqual([]);
  });
});
