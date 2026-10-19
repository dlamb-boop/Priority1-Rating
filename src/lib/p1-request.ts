import type { LineItemInput, LtlQuoteInput, TlQuoteInput } from "@/lib/types";
import { toPickupDateTime } from "@/lib/validation";

function omitEmpty<T extends Record<string, unknown>>(value: T): T {
  const next = {} as T;
  for (const [key, entry] of Object.entries(value)) {
    if (entry === undefined || entry === null || entry === "") continue;
    next[key as keyof T] = entry as T[keyof T];
  }
  return next;
}

export function buildLtlLineItem(item: LineItemInput): Record<string, unknown> {
  return omitEmpty({
    freightClass: String(item.freightClass),
    packagingType: item.packagingType,
    units: item.units,
    pieces: item.pieces ?? undefined,
    totalWeight: item.totalWeight,
    length: item.length,
    width: item.width,
    height: item.height,
    isStackable: Boolean(item.isStackable),
    isHazardous: Boolean(item.isHazardous),
    isUsed: Boolean(item.isUsed),
    isMachinery: Boolean(item.isMachinery),
    nmfcItemCode: item.nmfcItemCode || undefined,
    nmfcSubCode: item.nmfcSubCode || undefined,
    description: item.description || undefined,
  });
}

/**
 * Body for POST /v2/ltl/quotes/rates.
 * Field names match the v2 OpenAPI schema. Pickup is origin-local with no Z suffix.
 */
export function buildLtlRatesRequest(input: LtlQuoteInput): Record<string, unknown> {
  return omitEmpty({
    originCity: input.originCity || undefined,
    originStateAbbreviation: input.originStateAbbreviation || undefined,
    originZipCode: input.originZipCode,
    originCountryCode: input.originCountryCode || undefined,
    destinationCity: input.destinationCity || undefined,
    destinationStateAbbreviation: input.destinationStateAbbreviation || undefined,
    destinationZipCode: input.destinationZipCode,
    destinationCountryCode: input.destinationCountryCode || undefined,
    pickupDate: toPickupDateTime(input.pickupDate),
    items: input.items.map(buildLtlLineItem),
    accessorialServices: input.accessorialServices?.length
      ? input.accessorialServices.map((code) => ({ code }))
      : undefined,
    apiConfiguration:
      input.carrierTimeoutSeconds != null
        ? { timeout: input.carrierTimeoutSeconds }
        : undefined,
  });
}

export function buildSuggestedClassRequest(input: {
  totalWeight: number;
  length: number;
  width: number;
  height: number;
  units: number;
}): Record<string, unknown> {
  return {
    totalWeight: input.totalWeight,
    length: input.length,
    width: input.width,
    height: input.height,
    units: input.units,
  };
}

/**
 * Body for POST /v2/tl/truckloadquotes/rates.
 * pickupDateOpen is the only schema-required field; we also send lane and equipment.
 * The timestamp is origin-local and has no Z or numeric offset.
 */
export function buildTlRatesRequest(input: TlQuoteInput): Record<string, unknown> {
  return omitEmpty({
    originZipCode: input.originZipCode,
    originCity: input.originCity || undefined,
    originState: input.originState || undefined,
    originCountryCode: input.originCountryCode || undefined,
    destinationZipCode: input.destinationZipCode,
    destinationCity: input.destinationCity || undefined,
    destinationState: input.destinationState || undefined,
    destinationCountryCode: input.destinationCountryCode || undefined,
    pickupDateOpen: toPickupDateTime(input.pickupDateOpen),
    pickupDateClose: input.pickupDateClose ? toPickupDateTime(input.pickupDateClose) : undefined,
    startTime: input.startTime || undefined,
    endTime: input.endTime || undefined,
    equipment: input.equipment,
    truckloadQuoteServiceTypeId: input.truckloadQuoteServiceTypeId || undefined,
    weight: input.weight,
    weightUnitId: input.weightUnitId || undefined,
    palletCount: input.palletCount ?? undefined,
    linearFeet: input.linearFeet ?? undefined,
    description: input.description || undefined,
    isFloorLoaded: Boolean(input.isFloorLoaded),
    receiveLoadOnWeekend: Boolean(input.receiveLoadOnWeekend),
    requiresLiftGate: Boolean(input.requiresLiftGate),
    hasETrack: Boolean(input.hasETrack),
    loadBarCount: input.loadBarCount ?? undefined,
    strapCount: input.strapCount ?? undefined,
    needsHeadboard: Boolean(input.needsHeadboard),
    chainCount: input.chainCount ?? undefined,
    pipeStakeCount: input.pipeStakeCount ?? undefined,
    coilRackCount: input.coilRackCount ?? undefined,
  });
}
