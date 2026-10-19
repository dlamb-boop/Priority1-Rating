import type { EquipmentType, FreightClass, PackagingType, TlServiceType, WeightUnit } from "@/lib/constants";

export type LineItemInput = {
  freightClass: FreightClass | string;
  packagingType: PackagingType | string;
  units: number;
  pieces?: number | null;
  totalWeight: number;
  length: number;
  width: number;
  height: number;
  isStackable?: boolean;
  isHazardous?: boolean;
  isUsed?: boolean;
  isMachinery?: boolean;
  nmfcItemCode?: string | null;
  nmfcSubCode?: string | null;
  description?: string | null;
};

export type LtlQuoteInput = {
  markupPercent: number;
  originZipCode: string;
  originCity?: string | null;
  originStateAbbreviation?: string | null;
  originCountryCode?: string | null;
  destinationZipCode: string;
  destinationCity?: string | null;
  destinationStateAbbreviation?: string | null;
  destinationCountryCode?: string | null;
  pickupDate: string;
  items: LineItemInput[];
  accessorialServices?: string[];
  carrierTimeoutSeconds?: number | null;
};

export type TlQuoteInput = {
  markupPercent: number;
  originZipCode: string;
  originCity?: string | null;
  originState?: string | null;
  originCountryCode?: string | null;
  destinationZipCode: string;
  destinationCity?: string | null;
  destinationState?: string | null;
  destinationCountryCode?: string | null;
  pickupDateOpen: string;
  pickupDateClose?: string | null;
  startTime?: string | null;
  endTime?: string | null;
  equipment: EquipmentType | string;
  truckloadQuoteServiceTypeId?: TlServiceType | string;
  weight: number;
  weightUnitId?: WeightUnit | string;
  palletCount?: number | null;
  linearFeet?: number | null;
  description?: string | null;
  isFloorLoaded?: boolean;
  receiveLoadOnWeekend?: boolean;
  requiresLiftGate?: boolean;
  hasETrack?: boolean;
  loadBarCount?: number | null;
  strapCount?: number | null;
  needsHeadboard?: boolean;
  chainCount?: number | null;
  pipeStakeCount?: number | null;
  coilRackCount?: number | null;
  carrierTimeoutSeconds?: number | null;
};

export type CustomerCharge = {
  code: string;
  description: string;
  amount: number;
};

export type CustomerRate = {
  optionId: string;
  carrierName: string;
  scac: string;
  serviceLevel: string;
  serviceLevelDescription: string | null;
  laneType: string | null;
  transitDays: number | null;
  deliveryDate: string | null;
  expirationDate: string | null;
  customerTotal: number;
  currency: string;
  charges: CustomerCharge[];
};

export type InternalCharge = {
  code: string;
  description: string;
  baseAmount: number;
  customerAmount: number;
};

export type InternalEconomics = {
  baseTotal: number;
  carrierBaseCost: number | null;
  markupPercent: number;
  markupAmount: number;
  marginPercent: number;
  carrierQuoteNumber: string | null;
  charges: InternalCharge[];
};

export type DeskRate = CustomerRate & {
  internal: InternalEconomics;
};

export type FailedCarrier = {
  carrierName: string;
  scac: string;
  message: string;
};

export type ShipmentSummary = {
  originZipCode: string;
  originCity: string | null;
  originState: string | null;
  destinationZipCode: string;
  destinationCity: string | null;
  destinationState: string | null;
  pickupDate: string;
  distanceMiles: number | null;
  totalWeight: number | null;
  linearFeet: number | null;
  items: Array<{
    freightClass: string;
    packagingType: string;
    units: number;
    pieces: number | null;
    totalWeight: number;
    length: number;
    width: number;
    height: number;
    description: string | null;
    isHazardous: boolean;
    isStackable: boolean;
  }>;
  accessorials: Array<{ code: string; description: string }>;
};

export type QuoteDeskResponse = {
  mode: "mock" | "live";
  environment: "sandbox" | "production" | "custom";
  modeLabel: string;
  product: "ltl" | "tl";
  markupPercent: number;
  shipment: ShipmentSummary;
  rates: DeskRate[];
  failedCarriers: FailedCarrier[];
  warnings: string[];
};

export type CustomerQuoteDocument = {
  customerName: string;
  company: string;
  quoteDate: string;
  validThrough: string;
  reference: string;
  mentionCapacityPartner: boolean;
  shipment: {
    originLabel: string;
    destinationLabel: string;
    pickupDate: string;
    distanceMiles: number | null;
    totalWeight: number | null;
    items: ShipmentSummary["items"];
    accessorials: string[];
  };
  options: Array<{
    carrierName: string;
    scac: string;
    serviceLevel: string;
    laneType: string | null;
    transitDays: number | null;
    deliveryDate: string | null;
    expirationDate: string | null;
    price: number;
    currency: string;
    charges: CustomerCharge[];
  }>;
};
