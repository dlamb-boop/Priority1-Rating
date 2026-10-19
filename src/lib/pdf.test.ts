import { describe, expect, it } from "vitest";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";
import { buildCustomerQuote } from "@/lib/customer-quote";
import { renderCustomerPdf } from "@/lib/pdf";
import { quoteLtl } from "@/lib/quote-service";
import type { ShipmentSummary } from "@/lib/types";

async function pdfText(bytes: Buffer): Promise<{ text: string; pages: string[]; info: Record<string, unknown> }> {
  const doc = await getDocument({
    data: new Uint8Array(bytes),
    isEvalSupported: false,
    useSystemFonts: true,
  }).promise;
  const pages: string[] = [];
  for (let pageNumber = 1; pageNumber <= doc.numPages; pageNumber += 1) {
    const page = await doc.getPage(pageNumber);
    const content = await page.getTextContent();
    pages.push(content.items.map((item) => ("str" in item ? item.str : "")).join(" "));
  }
  const metadata = await doc.getMetadata();
  return { text: pages.join("\n"), pages, info: (metadata.info ?? {}) as Record<string, unknown> };
}

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
  accessorials: [{ code: "LGPU", description: "Lift Gate Pickup" }],
};

describe("customer PDF", () => {
  it("shows the sell price and hides buy rate, markup, and upstream ids", async () => {
    const document = buildCustomerQuote({
      customerName: "Alex Chen",
      company: "Northwind Goods",
      quoteDate: "2026-10-19",
      showPriority1: false,
      shipment,
      options: [
        {
          optionId: "ltl-1",
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
          baseCost: 235.89,
          carrierQuoteNumber: "Q1234",
        } as never,
      ],
    });
    const bytes = await renderCustomerPdf(document);
    const { text, pages, info } = await pdfText(bytes);
    const haystack = `${text}\n${JSON.stringify(info)}`.toLowerCase();
    expect(text).toContain("Alex Chen");
    expect(text).toContain("Northwind Goods");
    expect(text).toContain("Southeastern Freight");
    expect(text).toContain("SEFL");
    expect(text).toContain("$252.40");
    expect(text).toContain("Dawson Lamb");
    expect(text).toContain("Director of Supply Chain Solutions and Partnerships");
    for (const pageText of pages) {
      expect(pageText).toContain("Dawson Lamb");
    }
    for (const token of ["markup", "base cost", "basecost", "margin", "235.89", "196.43", "16.51", "21108", "q1234", "priority1"]) {
      expect(haystack).not.toContain(token);
    }
    expect(String(info.Title)).toBe("EasyPost Freight Quote");
    expect(String(info.Author)).toContain("Dawson Lamb");
  });

  it("mentions the capacity partner only when the desk asks for it", async () => {
    const quote = await quoteLtl({
      markupPercent: 10,
      originZipCode: "90221",
      originCity: "Los Angeles",
      originStateAbbreviation: "CA",
      destinationZipCode: "72205",
      destinationCity: "Little Rock",
      destinationStateAbbreviation: "AR",
      pickupDate: "2026-10-21",
      items: [
        {
          freightClass: "70",
          packagingType: "Pallet",
          units: 2,
          totalWeight: 800,
          length: 48,
          width: 40,
          height: 40,
        },
      ],
    });
    const hidden = buildCustomerQuote({
      company: "Northwind Goods",
      quoteDate: "2026-10-19",
      shipment: quote.shipment,
      options: [quote.rates[0]],
    });
    const shown = buildCustomerQuote({
      company: "Northwind Goods",
      quoteDate: "2026-10-19",
      showPriority1: true,
      shipment: quote.shipment,
      options: [quote.rates[0]],
    });
    const hiddenText = (await pdfText(await renderCustomerPdf(hidden))).text;
    const shownText = (await pdfText(await renderCustomerPdf(shown))).text;
    expect(hiddenText.toLowerCase()).not.toContain("priority1");
    expect(shownText).toContain("Priority1");
    expect(hiddenText).not.toContain(quote.rates[0].internal.baseTotal.toFixed(2));
    expect(hiddenText).toContain("Northwind Goods");
  });
});
