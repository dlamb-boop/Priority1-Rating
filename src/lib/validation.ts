import { accessorialByCode, isKnownAccessorial } from "@/lib/accessorials";
import {
  COUNTRY_CODES,
  EQUIPMENT_TYPES,
  FREIGHT_CLASSES,
  PACKAGING_TYPES,
  TL_SERVICE_TYPES,
  WEIGHT_UNITS,
  isEquipmentType,
  isFreightClass,
  isPackagingType,
} from "@/lib/constants";
import type { LineItemInput, LtlQuoteInput, TlQuoteInput } from "@/lib/types";

export class QuoteInputError extends Error {
  fieldErrors: Record<string, string>;

  constructor(message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "QuoteInputError";
    this.fieldErrors = fieldErrors;
  }
}

const US_OR_MX_POSTAL = /^\d{5}(-\d{4})?$/;
const CA_POSTAL = /^[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d$/;
const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;
const TIME_HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;

export function isPostalCode(value: string): boolean {
  const trimmed = value.trim();
  return US_OR_MX_POSTAL.test(trimmed) || CA_POSTAL.test(trimmed);
}

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new QuoteInputError(`${label} is required.`);
  }
  return value.trim();
}

function optionalString(value: unknown, max = 80): string | undefined {
  if (value === null || value === undefined || value === "") return undefined;
  if (typeof value !== "string") throw new QuoteInputError("Expected text.");
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (trimmed.length > max) throw new QuoteInputError(`Keep this under ${max} characters.`);
  return trimmed;
}

function positiveNumber(value: unknown, label: string): number {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    throw new QuoteInputError(`${label} must be greater than zero.`);
  }
  return numeric;
}

function positiveInt(value: unknown, label: string, max: number): number {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isInteger(numeric) || numeric < 1 || numeric > max) {
    throw new QuoteInputError(`${label} must be a whole number from 1 to ${max}.`);
  }
  return numeric;
}

function optionalInt(value: unknown, label: string, max: number): number | undefined {
  if (value === null || value === undefined || value === "") return undefined;
  return positiveInt(value, label, max);
}

function booleanFlag(value: unknown): boolean {
  return value === true || value === "true" || value === 1;
}

export function toPickupDateTime(date: string): string {
  const trimmed = date.trim();
  if (DATE_ONLY.test(trimmed)) return `${trimmed}T00:00:00`;
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(trimmed)) {
    return trimmed.length === 16 ? `${trimmed}:00` : trimmed;
  }
  throw new QuoteInputError("Pickup date must be a calendar date.");
}

function assertPostal(value: string, label: string): string {
  if (!isPostalCode(value)) {
    throw new QuoteInputError(`${label} must be a US ZIP or Canadian postal code.`);
  }
  return value.trim().toUpperCase();
}

function assertState(value: string | undefined, label: string): string | undefined {
  if (!value) return undefined;
  if (!/^[A-Za-z]{2}$/.test(value)) {
    throw new QuoteInputError(`${label} must be a 2-letter abbreviation.`);
  }
  return value.toUpperCase();
}

function assertCountry(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const upper = value.toUpperCase();
  if (!(COUNTRY_CODES as readonly string[]).includes(upper)) {
    throw new QuoteInputError("Country must be US, CA, MX, or PR.");
  }
  return upper;
}

export function normalizeLineItem(raw: LineItemInput, index: number): LineItemInput {
  const prefix = `Item ${index + 1}`;
  const freightClass = requiredString(raw?.freightClass, `${prefix} freight class`);
  if (!isFreightClass(freightClass)) {
    throw new QuoteInputError(
      `${prefix} freight class must be one of ${FREIGHT_CLASSES.join(", ")}.`,
    );
  }
  const packagingType = requiredString(raw?.packagingType, `${prefix} packaging`);
  if (!isPackagingType(packagingType)) {
    throw new QuoteInputError(
      `${prefix} packaging must be one of ${PACKAGING_TYPES.join(", ")}.`,
    );
  }
  const nmfcItemCode = optionalString(raw?.nmfcItemCode, 20);
  const nmfcSubCode = optionalString(raw?.nmfcSubCode, 20);
  if (Boolean(nmfcItemCode) !== Boolean(nmfcSubCode)) {
    throw new QuoteInputError(`${prefix} needs both an NMFC item code and sub code.`);
  }

  return {
    freightClass,
    packagingType,
    units: positiveInt(raw?.units, `${prefix} units`, 200),
    pieces: optionalInt(raw?.pieces, `${prefix} pieces`, 10000) ?? null,
    totalWeight: positiveNumber(raw?.totalWeight, `${prefix} total weight`),
    length: positiveNumber(raw?.length, `${prefix} length`),
    width: positiveNumber(raw?.width, `${prefix} width`),
    height: positiveNumber(raw?.height, `${prefix} height`),
    isStackable: booleanFlag(raw?.isStackable),
    isHazardous: booleanFlag(raw?.isHazardous),
    isUsed: booleanFlag(raw?.isUsed),
    isMachinery: booleanFlag(raw?.isMachinery),
    nmfcItemCode: nmfcItemCode ?? null,
    nmfcSubCode: nmfcSubCode ?? null,
    description: optionalString(raw?.description, 120) ?? null,
  };
}

export function normalizeAccessorials(codes: unknown, hazardous: boolean): string[] {
  const list = Array.isArray(codes) ? codes : [];
  const unique: string[] = [];
  for (const code of list) {
    if (typeof code !== "string" || !code.trim()) continue;
    const upper = code.trim().toUpperCase();
    if (!isKnownAccessorial(upper)) {
      throw new QuoteInputError(`Unknown accessorial code ${upper}.`);
    }
    if (!unique.includes(upper)) unique.push(upper);
  }
  if (hazardous && !unique.includes("HAZM")) unique.push("HAZM");
  return unique;
}

export function normalizeLtlInput(raw: LtlQuoteInput): LtlQuoteInput & { items: LineItemInput[] } {
  if (!raw || !Array.isArray(raw.items) || raw.items.length === 0) {
    throw new QuoteInputError("Add at least one freight line item.");
  }
  if (raw.items.length > 20) {
    throw new QuoteInputError("A quote can include up to 20 line items.");
  }
  const items = raw.items.map((item, index) => normalizeLineItem(item, index));
  const accessorialServices = normalizeAccessorials(
    raw.accessorialServices,
    items.some((item) => item.isHazardous),
  );
  if (accessorialServices.includes("HAZM") && items.every((item) => !item.isHazardous)) {
    for (const item of items) item.isHazardous = true;
  }

  let timeout: number | null = null;
  if (raw.carrierTimeoutSeconds !== null && raw.carrierTimeoutSeconds !== undefined && raw.carrierTimeoutSeconds !== ("" as never)) {
    const numeric = Number(raw.carrierTimeoutSeconds);
    if (!Number.isInteger(numeric) || numeric < 5 || numeric > 60) {
      throw new QuoteInputError("Carrier timeout must be a whole number of seconds from 5 to 60.");
    }
    timeout = numeric;
  }

  return {
    markupPercent: Number(raw.markupPercent),
    originZipCode: assertPostal(requiredString(raw.originZipCode, "Origin ZIP"), "Origin ZIP"),
    originCity: optionalString(raw.originCity, 60) ?? null,
    originStateAbbreviation: assertState(optionalString(raw.originStateAbbreviation, 2), "Origin state") ?? null,
    originCountryCode: assertCountry(optionalString(raw.originCountryCode, 2)) ?? null,
    destinationZipCode: assertPostal(
      requiredString(raw.destinationZipCode, "Destination ZIP"),
      "Destination ZIP",
    ),
    destinationCity: optionalString(raw.destinationCity, 60) ?? null,
    destinationStateAbbreviation:
      assertState(optionalString(raw.destinationStateAbbreviation, 2), "Destination state") ?? null,
    destinationCountryCode: assertCountry(optionalString(raw.destinationCountryCode, 2)) ?? null,
    pickupDate: toPickupDateTime(requiredString(raw.pickupDate, "Pickup date")).slice(0, 10),
    items,
    accessorialServices,
    carrierTimeoutSeconds: timeout,
  };
}

export function normalizeTlInput(raw: TlQuoteInput): TlQuoteInput {
  const equipment = requiredString(raw?.equipment, "Equipment");
  if (!isEquipmentType(equipment)) {
    throw new QuoteInputError(`Equipment must be one of ${EQUIPMENT_TYPES.join(", ")}.`);
  }
  const service = optionalString(raw?.truckloadQuoteServiceTypeId, 10) ?? "Full";
  if (!(TL_SERVICE_TYPES as readonly string[]).includes(service)) {
    throw new QuoteInputError("Service type must be Full or Team.");
  }
  const unit = optionalString(raw?.weightUnitId, 4) ?? "lbs";
  if (!(WEIGHT_UNITS as readonly string[]).includes(unit)) {
    throw new QuoteInputError("Weight unit must be lbs or kg.");
  }
  const startTime = optionalString(raw?.startTime, 5);
  const endTime = optionalString(raw?.endTime, 5);
  if (startTime && !TIME_HHMM.test(startTime)) {
    throw new QuoteInputError("Window start must be HH:mm.");
  }
  if (endTime && !TIME_HHMM.test(endTime)) {
    throw new QuoteInputError("Window end must be HH:mm.");
  }

  const liftGateEquipment = equipment === "Sprinter_Van" || equipment.includes("Straight_Truck");

  return {
    markupPercent: Number(raw.markupPercent),
    originZipCode: assertPostal(requiredString(raw.originZipCode, "Origin ZIP"), "Origin ZIP"),
    originCity: optionalString(raw.originCity, 60) ?? null,
    originState: assertState(optionalString(raw.originState, 2), "Origin state") ?? null,
    originCountryCode: assertCountry(optionalString(raw.originCountryCode, 2)) ?? null,
    destinationZipCode: assertPostal(
      requiredString(raw.destinationZipCode, "Destination ZIP"),
      "Destination ZIP",
    ),
    destinationCity: optionalString(raw.destinationCity, 60) ?? null,
    destinationState: assertState(optionalString(raw.destinationState, 2), "Destination state") ?? null,
    destinationCountryCode: assertCountry(optionalString(raw.destinationCountryCode, 2)) ?? null,
    pickupDateOpen: toPickupDateTime(requiredString(raw.pickupDateOpen, "Pickup open date")).slice(0, 10),
    pickupDateClose: raw.pickupDateClose
      ? toPickupDateTime(requiredString(raw.pickupDateClose, "Pickup close date")).slice(0, 10)
      : null,
    startTime: startTime ?? null,
    endTime: endTime ?? null,
    equipment,
    truckloadQuoteServiceTypeId: service,
    weight: positiveInt(raw.weight, "Weight", 200000),
    weightUnitId: unit,
    palletCount: optionalInt(raw.palletCount, "Pallet count", 100) ?? null,
    linearFeet: optionalInt(raw.linearFeet, "Linear feet", 53) ?? null,
    description: optionalString(raw.description, 120) ?? null,
    isFloorLoaded: booleanFlag(raw.isFloorLoaded),
    receiveLoadOnWeekend: booleanFlag(raw.receiveLoadOnWeekend),
    requiresLiftGate: liftGateEquipment ? booleanFlag(raw.requiresLiftGate) : false,
    hasETrack: booleanFlag(raw.hasETrack),
    loadBarCount: optionalInt(raw.loadBarCount, "Load bars", 20) ?? null,
    strapCount: optionalInt(raw.strapCount, "Straps", 20) ?? null,
    needsHeadboard: booleanFlag(raw.needsHeadboard),
    chainCount: optionalInt(raw.chainCount, "Chains", 20) ?? null,
    pipeStakeCount: optionalInt(raw.pipeStakeCount, "Pipe stakes", 20) ?? null,
    coilRackCount: optionalInt(raw.coilRackCount, "Coil racks", 20) ?? null,
  };
}

export function accessorialDescriptions(codes: string[]): Array<{ code: string; description: string }> {
  return codes.map((code) => ({
    code,
    description: accessorialByCode(code)?.description ?? code,
  }));
}
