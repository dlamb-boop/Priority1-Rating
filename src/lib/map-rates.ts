import { accessorialDescriptions } from "@/lib/validation";
import { applyMarkup } from "@/lib/markup";
import type { DeskRate, FailedCarrier, QuoteDeskResponse, ShipmentSummary } from "@/lib/types";
import type { LtlQuoteInput, TlQuoteInput } from "@/lib/types";
import { zipHint } from "@/lib/zip-hints";

type RawCharge = { code?: string | null; description?: string | null; amount?: number | null };

type RawLtlRate = {
  id?: number | string | null;
  carrierName?: string | null;
  carrierCode?: string | null;
  serviceLevel?: string | null;
  serviceLevelDescription?: string | null;
  transitDays?: number | null;
  laneType?: string | null;
  deliveryDate?: string | null;
  expirationDate?: string | null;
  carrierQuoteNumber?: string | null;
  rateQuoteDetail?: {
    total?: number | null;
    baseCost?: number | null;
    charges?: RawCharge[] | null;
  } | null;
};

type RawLtlResponse = {
  id?: number | string | null;
  rateQuotes?: RawLtlRate[] | null;
  invalidRateQuotes?: Array<{
    carrierCode?: string | null;
    carrierName?: string | null;
    errorMessages?: Array<{ text?: string | null }> | null;
  }> | null;
  rateQuoteRequestDetail?: {
    originZipCode?: string | null;
    originCity?: string | null;
    originStateAbbreviation?: string | null;
    destinationZipCode?: string | null;
    destinationCity?: string | null;
    destinationStateAbbreviation?: string | null;
    pickupDate?: string | null;
    linearFeet?: number | null;
    distance?: number | null;
    totalWeight?: number | null;
  } | null;
  messages?: Array<{ text?: string | null }> | null;
};

type RawTlRate = {
  rateId?: number | string | null;
  currencyTypeId?: string | null;
  total?: number | null;
  truckloadRateQuoteDetail?: {
    total?: number | null;
    charges?: RawCharge[] | null;
  } | null;
  expirationDate?: string | null;
  pickupDate?: string | null;
  deliveryDate?: string | null;
  transitDays?: number | null;
};

type RawTlResponse = {
  id?: number | string | null;
  rates?: RawTlRate[] | null;
  truckloadRateQuoteResponseDetail?: {
    originZipCode?: string | null;
    destinationZipCode?: string | null;
    pickupDate?: string | null;
    linearFeet?: number | null;
    distance?: number | null;
    totalWeight?: number | null;
  } | null;
  additionalInformation?: string | null;
};

function text(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

function shipmentFromLtl(input: LtlQuoteInput, raw: RawLtlResponse): ShipmentSummary {
  const detail = raw.rateQuoteRequestDetail;
  const originHint = zipHint(input.originZipCode);
  const destinationHint = zipHint(input.destinationZipCode);
  return {
    originZipCode: text(detail?.originZipCode) || input.originZipCode,
    originCity: text(detail?.originCity) || text(input.originCity) || originHint?.city || null,
    originState: text(detail?.originStateAbbreviation) || text(input.originStateAbbreviation) || originHint?.state || null,
    destinationZipCode: text(detail?.destinationZipCode) || input.destinationZipCode,
    destinationCity: text(detail?.destinationCity) || text(input.destinationCity) || destinationHint?.city || null,
    destinationState:
      text(detail?.destinationStateAbbreviation) ||
      text(input.destinationStateAbbreviation) ||
      destinationHint?.state ||
      null,
    pickupDate: (text(detail?.pickupDate) || input.pickupDate).slice(0, 10),
    distanceMiles: typeof detail?.distance === "number" ? Math.round(detail.distance) : null,
    totalWeight: typeof detail?.totalWeight === "number" ? detail.totalWeight : sumWeight(input),
    linearFeet: typeof detail?.linearFeet === "number" ? detail.linearFeet : null,
    items: input.items.map((item) => ({
      freightClass: String(item.freightClass),
      packagingType: String(item.packagingType),
      units: item.units,
      pieces: item.pieces ?? null,
      totalWeight: item.totalWeight,
      length: item.length,
      width: item.width,
      height: item.height,
      description: text(item.description),
      isHazardous: Boolean(item.isHazardous),
      isStackable: Boolean(item.isStackable),
    })),
    accessorials: accessorialDescriptions(input.accessorialServices ?? []),
  };
}

function sumWeight(input: LtlQuoteInput): number {
  return input.items.reduce((sum, item) => sum + item.totalWeight, 0);
}

export function mapLtlResponse(
  raw: RawLtlResponse,
  input: LtlQuoteInput,
  meta: { mode: QuoteDeskResponse["mode"]; environment: QuoteDeskResponse["environment"]; modeLabel: string },
): QuoteDeskResponse {
  const rates: DeskRate[] = (raw.rateQuotes ?? [])
    .filter((rate) => typeof rate.rateQuoteDetail?.total === "number")
    .map((rate, index) => {
      const detail = rate.rateQuoteDetail!;
      const priced = applyMarkup(detail.total as number, detail.charges ?? [], input.markupPercent);
      const scac = text(rate.carrierCode) || "";
      const serviceLevel = text(rate.serviceLevel) || "STANDARD";
      return {
        optionId: `ltl-${index + 1}-${scac || "carrier"}-${serviceLevel}`.toLowerCase(),
        carrierName: text(rate.carrierName) || "Carrier",
        scac,
        serviceLevel,
        serviceLevelDescription: text(rate.serviceLevelDescription),
        laneType: text(rate.laneType),
        transitDays: typeof rate.transitDays === "number" ? rate.transitDays : null,
        deliveryDate: text(rate.deliveryDate),
        expirationDate: text(rate.expirationDate),
        customerTotal: priced.customerTotal,
        currency: "USD",
        charges: priced.charges.map((charge) => ({
          code: charge.code,
          description: charge.description,
          amount: charge.customerAmount,
        })),
        internal: {
          baseTotal: priced.baseTotal,
          carrierBaseCost: typeof detail.baseCost === "number" ? detail.baseCost : null,
          markupPercent: priced.markupPercent,
          markupAmount: priced.markupAmount,
          marginPercent: priced.marginPercent,
          carrierQuoteNumber: text(rate.carrierQuoteNumber),
          charges: priced.charges,
        },
      };
    })
    .sort((a, b) => a.customerTotal - b.customerTotal || (a.transitDays ?? 99) - (b.transitDays ?? 99));

  const failedCarriers: FailedCarrier[] = (raw.invalidRateQuotes ?? []).map((failed) => ({
    carrierName: text(failed.carrierName) || "Carrier",
    scac: text(failed.carrierCode) || "",
    message: text(failed.errorMessages?.find((message) => message.text)?.text) || "This carrier did not return a rate.",
  }));

  const warnings = (raw.messages ?? [])
    .map((message) => text(message.text))
    .filter((message): message is string => Boolean(message));

  return {
    mode: meta.mode,
    environment: meta.environment,
    modeLabel: meta.modeLabel,
    product: "ltl",
    markupPercent: rates[0]?.internal.markupPercent ?? input.markupPercent,
    shipment: shipmentFromLtl(input, raw),
    rates,
    failedCarriers,
    warnings,
  };
}

export function mapTlResponse(
  raw: RawTlResponse,
  input: TlQuoteInput,
  meta: { mode: QuoteDeskResponse["mode"]; environment: QuoteDeskResponse["environment"]; modeLabel: string },
): QuoteDeskResponse {
  const originHint = zipHint(input.originZipCode);
  const destinationHint = zipHint(input.destinationZipCode);
  const detail = raw.truckloadRateQuoteResponseDetail;

  const rates: DeskRate[] = (raw.rates ?? [])
    .filter((rate) => typeof rate.total === "number" || typeof rate.truckloadRateQuoteDetail?.total === "number")
    .map((rate, index) => {
      const total = (typeof rate.total === "number" ? rate.total : rate.truckloadRateQuoteDetail?.total) as number;
      const priced = applyMarkup(total, rate.truckloadRateQuoteDetail?.charges ?? [], input.markupPercent);
      const currency = text(rate.currencyTypeId) || "USD";
      return {
        optionId: `tl-${index + 1}`,
        carrierName: `Truckload option ${index + 1}`,
        scac: "",
        serviceLevel: String(input.truckloadQuoteServiceTypeId || "Full"),
        serviceLevelDescription: null,
        laneType: null,
        transitDays: typeof rate.transitDays === "number" ? rate.transitDays : null,
        deliveryDate: text(rate.deliveryDate),
        expirationDate: text(rate.expirationDate),
        customerTotal: priced.customerTotal,
        currency,
        charges: priced.charges.map((charge) => ({
          code: charge.code,
          description: charge.description,
          amount: charge.customerAmount,
        })),
        internal: {
          baseTotal: priced.baseTotal,
          carrierBaseCost: null,
          markupPercent: priced.markupPercent,
          markupAmount: priced.markupAmount,
          marginPercent: priced.marginPercent,
          carrierQuoteNumber: null,
          charges: priced.charges,
        },
      };
    })
    .sort((a, b) => a.customerTotal - b.customerTotal || (a.transitDays ?? 99) - (b.transitDays ?? 99));

  const warnings: string[] = [];
  if (text(raw.additionalInformation)) warnings.push(text(raw.additionalInformation) as string);
  warnings.push("Truckload rates from this API do not include a carrier name or SCAC.");

  const shipment: ShipmentSummary = {
    originZipCode: text(detail?.originZipCode) || input.originZipCode,
    originCity: text(input.originCity) || originHint?.city || null,
    originState: text(input.originState) || originHint?.state || null,
    destinationZipCode: text(detail?.destinationZipCode) || input.destinationZipCode,
    destinationCity: text(input.destinationCity) || destinationHint?.city || null,
    destinationState: text(input.destinationState) || destinationHint?.state || null,
    pickupDate: (text(detail?.pickupDate) || input.pickupDateOpen).slice(0, 10),
    distanceMiles: typeof detail?.distance === "number" ? Math.round(detail.distance) : null,
    totalWeight: typeof detail?.totalWeight === "number" ? detail.totalWeight : input.weight,
    linearFeet: typeof detail?.linearFeet === "number" ? detail.linearFeet : input.linearFeet ?? null,
    items: [
      {
        freightClass: "—",
        packagingType: input.palletCount ? "Pallet" : "Truckload",
        units: input.palletCount || 1,
        pieces: null,
        totalWeight: input.weight,
        length: input.linearFeet || 0,
        width: 0,
        height: 0,
        description: text(input.description),
        isHazardous: false,
        isStackable: false,
      },
    ],
    accessorials: [],
  };

  return {
    mode: meta.mode,
    environment: meta.environment,
    modeLabel: meta.modeLabel,
    product: "tl",
    markupPercent: rates[0]?.internal.markupPercent ?? input.markupPercent,
    shipment,
    rates,
    failedCarriers: [],
    warnings,
  };
}
