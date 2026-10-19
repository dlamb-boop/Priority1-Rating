import { describe, expect, it } from "vitest";
import { assertCustomerSafe, buildCustomerQuote, customerQuoteFilename, toCustomerRate } from "@/lib/customer-quote";
import { quoteLtl } from "@/lib/quote-service";
import type { DeskRate, ShipmentSummary } from "@/lib/types";

const shipment: ShipmentSummary = {
  originZipCode: "72205",
  originCity: "Little Rock",
  originState: "AR",
  destinationZipCode: "60606",
  destinationCity: "Chicago",
  destinationState: "IL",
  pickupDate: "2026-10-20",
  distanceMiles: 644,
  totalWeight: 275,
  linearFeet: 2,
  items: [
    {
      freightClass: "150",
      packagingType: "Pallet",
      units: 1,
      pieces: 1,
      totalWeight: 275,
      length: 48,
      width: 40,
      height: 40,
      description: "Hardware",
      isHazardous: false,
      isStackable: false,
    },
  ],
  accessorials: [
    { code: "LGPU", description: "Lift Gate Pickup" },
    { code: "APPT", description: "Delivery Appointment" },
  ],
};

function pollutedRate(): DeskRate & Record<string, unknown> {
  return {
    optionId: "ltl-1-sefl-standard",
    carrierName: "Southeastern Freight",
    scac: "SEFL",
    serviceLevel: "STANDARD",
    serviceLevelDescription: "Standard",
    laneType: "DIRECT",
    transitDays: 4,
    deliveryDate: "2026-10-23T16:00:00",
    expirationDate: "2026-10-26T16:00:00",
    customerTotal: 252.4,
    currency: "USD",
    charges: [
      { code: "FSC", description: "Fuel Surcharge", amount: 42.22 },
      { code: "GFC", description: "Gross Freight Charge", amount: 210.18 },
    ],
    internal: {
      baseTotal: 235.89,
      carrierBaseCost: 196.43,
      markupPercent: 7,
      markupAmount: 16.51,
      marginPercent: 6.54,
      carrierQuoteNumber: "Q1234",
      charges: [],
    },
    id: 21108,
    quoteId: 21108,
    rateId: 21108,
    baseCost: 196.43,
    baseTotal: 235.89,
    markupPercent: 7,
    carrierQuoteNumber: "Q1234",
    priority1QuoteId: 123456,
  };
}

describe("customer payload", () => {
  it("drops base cost, markup, margin, and upstream quote ids", () => {
    const rate = pollutedRate();
    const customer = toCustomerRate(rate);
    const document = buildCustomerQuote({
      customerName: "Alex Chen",
      company: "Northwind Goods",
      quoteDate: "2026-10-19",
      showPriority1: false,
      shipment,
      options: [rate],
    });
    assertCustomerSafe(document, ["235.89", "196.43", "16.51", "6.54", "21108", "123456", "Q1234"]);

    const blob = JSON.stringify({ customer, document }).toLowerCase();
    for (const token of ["markup", "basecost", "base cost", "margin", "235.89", "196.43", "21108", "123456", "q1234", "priority1"]) {
      expect(blob).not.toContain(token);
    }
    expect(blob).toContain("252.4");
    expect(blob).toContain("southeastern freight");
    expect(customerQuoteFilename(document)).toBe("EasyPost-Freight-Quote-2026-10-19.pdf");
    expect(customerQuoteFilename(document).toLowerCase()).not.toContain("markup");
    expect(customerQuoteFilename(document)).not.toContain("21108");
  });

  it("keeps a live mock quote's customer projection free of buy-rate figures", async () => {
    const quote = await quoteLtl({
      markupPercent: 7,
      originZipCode: "72205",
      destinationZipCode: "60606",
      pickupDate: "2026-10-20",
      accessorialServices: ["LGPU"],
      items: [
        {
          freightClass: "70",
          packagingType: "Pallet",
          units: 1,
          totalWeight: 500,
          length: 48,
          width: 40,
          height: 48,
        },
      ],
    });
    const bases = quote.rates.map((rate) => rate.internal.baseTotal.toFixed(2));
    const document = buildCustomerQuote({
      customerName: "Alex Chen",
      company: "Northwind Goods",
      quoteDate: "2026-10-19",
      shipment: quote.shipment,
      options: quote.rates,
    });
    assertCustomerSafe(document, bases);
    const raw = JSON.stringify(quote);
    expect(raw).not.toContain("rateQuoteDetail");
    expect(raw).not.toContain("424242");
    expect(raw).not.toContain("\"id\":900000");
    expect(quote.rates[0].customerTotal).toBeGreaterThan(quote.rates[0].internal.baseTotal);
    expect(quote.rates.map((rate) => rate.customerTotal)).toEqual(
      [...quote.rates].sort((a, b) => a.customerTotal - b.customerTotal).map((rate) => rate.customerTotal),
    );
  });
});
