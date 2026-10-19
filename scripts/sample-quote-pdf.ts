import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { buildCustomerQuote, customerQuoteFilename } from "../src/lib/customer-quote";
import { renderCustomerPdf } from "../src/lib/pdf";
import { quoteLtl } from "../src/lib/quote-service";

async function main() {
  const quote = await quoteLtl({
    markupPercent: 7,
    originZipCode: "72205",
    originCity: "Little Rock",
    originStateAbbreviation: "AR",
    destinationZipCode: "60606",
    destinationCity: "Chicago",
    destinationStateAbbreviation: "IL",
    pickupDate: "2026-10-20",
    accessorialServices: ["LGPU", "APPT"],
    items: [
      {
        freightClass: "70",
        packagingType: "Pallet",
        units: 1,
        pieces: 1,
        totalWeight: 500,
        length: 48,
        width: 40,
        height: 48,
        description: "Packaged hardware",
        isStackable: false,
        isHazardous: false,
        isUsed: false,
        isMachinery: false,
      },
    ],
  });

  const document = buildCustomerQuote({
    customerName: "Alex Chen",
    company: "Northwind Goods",
    quoteDate: "2026-10-19",
    showPriority1: false,
    shipment: quote.shipment,
    options: quote.rates.slice(0, 3),
  });
  const bytes = await renderCustomerPdf(document);
  const filename = customerQuoteFilename(document);
  const destinations = [
    path.resolve(process.cwd(), "samples", filename),
    "/opt/cursor/artifacts/sample_freight_quote.pdf",
  ];
  for (const destination of destinations) {
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, bytes);
    console.log(destination);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
