import { PREPARED_BY } from "@/lib/constants";
import { customerPdfFilename, todayIsoDate } from "@/lib/format";
import type { CustomerQuoteDocument, CustomerRate, DeskRate, QuoteDeskResponse } from "@/lib/types";

export function toCustomerRate(rate: DeskRate): CustomerRate {
  return {
    optionId: rate.optionId,
    carrierName: rate.carrierName,
    scac: rate.scac,
    serviceLevel: rate.serviceLevel,
    serviceLevelDescription: rate.serviceLevelDescription,
    laneType: rate.laneType,
    transitDays: rate.transitDays,
    deliveryDate: rate.deliveryDate,
    expirationDate: rate.expirationDate,
    customerTotal: rate.customerTotal,
    currency: rate.currency,
    charges: rate.charges.map((charge) => ({
      code: charge.code,
      description: charge.description,
      amount: charge.amount,
    })),
  };
}

const FORBIDDEN = [
  "markup",
  "basecost",
  "base cost",
  "base total",
  "margin",
  "carrierquotenumber",
  "quoteid",
  "rateid",
  "priority1",
];

export type PdfRequest = {
  customerName?: string | null;
  company?: string | null;
  quoteDate?: string | null;
  showPriority1?: boolean;
  shipment?: QuoteDeskResponse["shipment"] | null;
  options?: Array<DeskRate | CustomerRate | Record<string, unknown>> | null;
};

function cleanText(value: unknown, max = 120): string {
  if (typeof value !== "string") return "";
  return value.replace(/\s+/g, " ").trim().slice(0, max);
}

function money(value: unknown): number | null {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.round(numeric * 100) / 100;
}

function placeLabel(city: string | null, state: string | null, zip: string): string {
  const place = [city, state].filter(Boolean).join(", ");
  return place ? `${place} ${zip}` : zip;
}

function earliestDate(values: Array<string | null>): string | null {
  const stamps = values
    .map((value) => value?.slice(0, 10))
    .filter((value): value is string => Boolean(value && /^\d{4}-\d{2}-\d{2}$/.test(value)))
    .sort();
  return stamps[0] ?? null;
}

function addDays(isoDate: string, days: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  if (!match) return isoDate;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  date.setUTCDate(date.getUTCDate() + days);
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${date.getUTCFullYear()}-${month}-${day}`;
}

function referenceFor(quoteDate: string, origin: string, destination: string): string {
  const seed = `${quoteDate}|${origin}|${destination}`;
  let hash = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    hash ^= seed.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return `EPQ-${(hash >>> 0).toString(16).slice(0, 6).toUpperCase()}`;
}

function customerCharges(raw: unknown): CustomerQuoteDocument["options"][number]["charges"] {
  if (!Array.isArray(raw)) return [];
  const charges: CustomerQuoteDocument["options"][number]["charges"] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const record = entry as Record<string, unknown>;
    const amount = money(record.amount ?? record.customerAmount);
    if (amount === null) continue;
    charges.push({
      code: cleanText(record.code, 20) || "CHG",
      description: cleanText(record.description, 80) || "Charge",
      amount,
    });
  }
  return charges;
}

/**
 * Allow-list the fields a customer is allowed to see. Internal economics,
 * carrier quote numbers, and upstream ids are dropped even if the caller
 * included them.
 */
export function buildCustomerQuote(input: PdfRequest): CustomerQuoteDocument {
  const shipment = input.shipment;
  if (!shipment) {
    throw new Error("A shipment summary is required.");
  }
  const selected = (input.options ?? []).slice(0, 12);
  if (selected.length === 0) {
    throw new Error("Choose at least one carrier option for the quote.");
  }

  const quoteDate = /^\d{4}-\d{2}-\d{2}/.test(input.quoteDate || "")
    ? (input.quoteDate as string).slice(0, 10)
    : todayIsoDate();

  const options = selected.map((option) => {
    const record = option as Record<string, unknown>;
    const price = money(record.customerTotal ?? record.price);
    if (price === null) {
      throw new Error("Each selected option needs a customer price.");
    }
    const charges = customerCharges(record.charges);
    return {
      carrierName: cleanText(record.carrierName, 80) || "Carrier option",
      scac: cleanText(record.scac, 8).toUpperCase(),
      serviceLevel: cleanText(record.serviceLevelDescription, 80) || cleanText(record.serviceLevel, 40) || "Standard",
      laneType: cleanText(record.laneType, 20) || null,
      transitDays: typeof record.transitDays === "number" ? record.transitDays : null,
      deliveryDate: cleanText(record.deliveryDate, 40) || null,
      expirationDate: cleanText(record.expirationDate, 40) || null,
      price,
      currency: cleanText(record.currency, 3) || "USD",
      charges,
    };
  });

  const validThrough =
    earliestDate(options.map((option) => option.expirationDate)) || addDays(quoteDate, 7);

  const originZip = cleanText(shipment.originZipCode, 12);
  const destinationZip = cleanText(shipment.destinationZipCode, 12);

  return {
    customerName: cleanText(input.customerName, 80),
    company: cleanText(input.company, 80),
    quoteDate,
    validThrough,
    reference: referenceFor(quoteDate, originZip, destinationZip),
    mentionCapacityPartner: input.showPriority1 === true,
    shipment: {
      originLabel: placeLabel(cleanText(shipment.originCity, 60) || null, cleanText(shipment.originState, 8) || null, originZip),
      destinationLabel: placeLabel(
        cleanText(shipment.destinationCity, 60) || null,
        cleanText(shipment.destinationState, 8) || null,
        destinationZip,
      ),
      pickupDate: cleanText(shipment.pickupDate, 40).slice(0, 10),
      distanceMiles: typeof shipment.distanceMiles === "number" ? Math.round(shipment.distanceMiles) : null,
      totalWeight: typeof shipment.totalWeight === "number" ? shipment.totalWeight : null,
      items: (shipment.items ?? []).map((item) => ({
        freightClass: cleanText(item.freightClass, 8),
        packagingType: cleanText(item.packagingType, 20),
        units: Number(item.units) || 0,
        pieces: item.pieces ?? null,
        totalWeight: Number(item.totalWeight) || 0,
        length: Number(item.length) || 0,
        width: Number(item.width) || 0,
        height: Number(item.height) || 0,
        description: cleanText(item.description, 120) || null,
        isHazardous: Boolean(item.isHazardous),
        isStackable: Boolean(item.isStackable),
      })),
      accessorials: (shipment.accessorials ?? [])
        .map((item) => cleanText(typeof item === "string" ? item : item.description, 80))
        .filter(Boolean),
    },
    options,
  };
}

export function customerQuoteFilename(document: CustomerQuoteDocument): string {
  return customerPdfFilename(document.quoteDate);
}

export function preparedByLine(): string {
  return PREPARED_BY;
}

/**
 * Walks every string in the customer document. Used by tests and as a last
 * check before a PDF is written.
 */
export function assertCustomerSafe(document: CustomerQuoteDocument, rawBaseAmounts: string[] = []): void {
  const serialized = JSON.stringify(document).toLowerCase();
  const forbidden = document.mentionCapacityPartner ? FORBIDDEN.filter((word) => word !== "priority1") : FORBIDDEN;
  for (const word of forbidden) {
    if (serialized.includes(word)) {
      throw new Error(`Customer quote includes restricted text (${word}).`);
    }
  }
  for (const amount of rawBaseAmounts) {
    if (amount && serialized.includes(amount.toLowerCase())) {
      throw new Error("Customer quote includes a pre-markup amount.");
    }
  }
}
