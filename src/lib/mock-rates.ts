import { roundCents } from "@/lib/markup";
import type { LtlQuoteInput, TlQuoteInput } from "@/lib/types";
import { zipHint } from "@/lib/zip-hints";

type CarrierProfile = {
  carrierName: string;
  carrierCode: string;
  multiplier: number;
  transitDays: number;
  discount: boolean;
};

const CARRIERS: CarrierProfile[] = [
  { carrierName: "Southeastern Freight", carrierCode: "SEFL", multiplier: 1, transitDays: 3, discount: false },
  { carrierName: "R&L Carriers", carrierCode: "RLCA", multiplier: 1.14, transitDays: 4, discount: true },
  { carrierName: "Estes", carrierCode: "EXLA", multiplier: 1.21, transitDays: 3, discount: false },
  { carrierName: "Saia", carrierCode: "SAIA", multiplier: 1.28, transitDays: 4, discount: true },
  { carrierName: "ABF Freight", carrierCode: "ABFS", multiplier: 1.36, transitDays: 5, discount: false },
];

const ACCESSORIAL_FEES: Record<string, number> = {
  LGPU: 55,
  LGDEL: 55,
  RESPU: 48,
  RESDEL: 78,
  INPU: 65,
  INDEL: 85,
  LTDPU: 70,
  LTDDEL: 70,
  APPT: 22,
  NOTIFY: 15,
  HAZM: 45,
  PFZ: 35,
  SATPU: 80,
  LUMPER: 95,
  BLIND: 40,
  BOND: 60,
};

function hash(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function shiftDate(isoDate: string, days: number, businessDays: boolean): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  const base = match
    ? new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])))
    : new Date();
  if (!businessDays) {
    base.setUTCDate(base.getUTCDate() + days);
  } else {
    let remaining = days;
    while (remaining > 0) {
      base.setUTCDate(base.getUTCDate() + 1);
      const day = base.getUTCDay();
      if (day !== 0 && day !== 6) remaining -= 1;
    }
  }
  const month = String(base.getUTCMonth() + 1).padStart(2, "0");
  const day = String(base.getUTCDate()).padStart(2, "0");
  return `${base.getUTCFullYear()}-${month}-${day}T16:00:00`;
}

function mockDistance(origin: string, destination: string): number {
  const known: Record<string, [number, number]> = {
    "72205": [34.75, -92.29],
    "60606": [41.88, -87.64],
    "90221": [33.94, -118.21],
    "10001": [40.75, -73.99],
    "30303": [33.75, -84.39],
    "75201": [32.79, -96.8],
    "98101": [47.61, -122.33],
    "94105": [37.79, -122.39],
  };
  const a = known[origin.slice(0, 5)];
  const b = known[destination.slice(0, 5)];
  if (a && b) {
    const miles = Math.hypot((a[0] - b[0]) * 69, (a[1] - b[1]) * 53);
    return Math.max(40, Math.round(miles));
  }
  return 180 + (hash(`${origin}|${destination}`) % 1600);
}

function classFactor(freightClass: string): number {
  const value = Number(freightClass);
  if (!Number.isFinite(value)) return 1;
  return 0.72 + value / 180;
}

export function suggestFreightClass(input: {
  totalWeight: number;
  length: number;
  width: number;
  height: number;
  units: number;
}): string {
  const cubicFeet = (input.length * input.width * input.height * Math.max(1, input.units)) / 1728;
  const density = cubicFeet > 0 ? input.totalWeight / cubicFeet : 0;
  const bands: Array<[number, string]> = [
    [50, "50"],
    [35, "55"],
    [30, "60"],
    [22.5, "65"],
    [15, "70"],
    [13.5, "77.5"],
    [12, "85"],
    [10.5, "92.5"],
    [9, "100"],
    [8, "110"],
    [7, "125"],
    [6, "150"],
    [5, "175"],
    [4, "200"],
    [3, "250"],
    [2, "300"],
    [1, "400"],
    [0, "500"],
  ];
  return bands.find(([minimum]) => density >= minimum)?.[1] ?? "500";
}

export function mockLtlRates(input: LtlQuoteInput): unknown {
  const origin = zipHint(input.originZipCode);
  const destination = zipHint(input.destinationZipCode);
  const distance = mockDistance(input.originZipCode, input.destinationZipCode);
  const weight = input.items.reduce((sum, item) => sum + item.totalWeight, 0);
  const averageClass =
    input.items.reduce((sum, item) => sum + Number(item.freightClass) * item.totalWeight, 0) / Math.max(weight, 1);
  const linearFeet = Math.max(
    1,
    Math.round(
      input.items.reduce((sum, item) => {
        const widthFactor = item.width > 50 ? 2 : 1;
        return sum + (item.length / 12) * widthFactor * item.units;
      }, 0),
    ),
  );

  const anchor =
    Math.max(110, weight * 0.22 * classFactor(String(averageClass)) * (distance / 480));

  const accessorialBase = (input.accessorialServices ?? []).reduce(
    (sum, code) => sum + (ACCESSORIAL_FEES[code] ?? 32),
    0,
  );

  const pickup = input.pickupDate.slice(0, 10);

  const rateQuotes = CARRIERS.map((carrier, index) => {
    const linehaul = roundCents(anchor * carrier.multiplier);
    const fuel = roundCents(linehaul * 0.185);
    const accessorial = roundCents(accessorialBase * (1 + index * 0.03));
    const gross = roundCents(linehaul + fuel + accessorial);
    const discount = carrier.discount ? roundCents(gross * -0.12) : 0;
    const total = roundCents(gross + discount);
    const charges = [
      { code: "GFC", description: "Gross Freight Charge", amount: linehaul },
      { code: "FSC", description: "Fuel Surcharge", amount: fuel },
      ...(accessorial > 0
        ? [{ code: "ACC", description: "Accessorials", amount: accessorial }]
        : []),
      ...(discount !== 0
        ? [{ code: "DSC", description: "Carrier discount", amount: discount }]
        : []),
    ];
    const transit = carrier.transitDays + (distance > 1200 ? 1 : 0);
    return {
      id: 900000 + index,
      carrierName: carrier.carrierName,
      carrierCode: carrier.carrierCode,
      serviceLevel: "STANDARD",
      serviceLevelDescription: "Standard",
      transitDays: transit,
      laneType: distance > 1500 ? "INTERLINE" : "DIRECT",
      deliveryDate: shiftDate(pickup, transit, true),
      effectiveDate: shiftDate(pickup, 0, false),
      expirationDate: shiftDate(pickup, 7, false),
      carrierQuoteNumber: `DEMO-${carrier.carrierCode}-${1000 + index}`,
      rateQuoteDetail: {
        total,
        baseCost: linehaul,
        charges,
      },
      mode: "LTL",
      message: null,
    };
  });

  return {
    id: 424242,
    rateQuotes,
    invalidRateQuotes: [
      {
        carrierCode: "ODFL",
        carrierName: "Old Dominion Freight Line",
        errorMessages: [
          {
            severity: "Error",
            text: "An error occurred while retrieving rates.",
            source: "CAPACITY_PROVIDER",
          },
        ],
      },
    ],
    rateQuoteRequestDetail: {
      originZipCode: input.originZipCode,
      originCity: input.originCity || origin?.city || null,
      originStateAbbreviation: input.originStateAbbreviation || origin?.state || null,
      destinationZipCode: input.destinationZipCode,
      destinationCity: input.destinationCity || destination?.city || null,
      destinationStateAbbreviation: input.destinationStateAbbreviation || destination?.state || null,
      pickupDate: `${pickup}T00:00:00`,
      linearFeet,
      distance,
      totalWeight: weight,
    },
    messages:
      input.originCity && origin && input.originCity.toLowerCase() !== origin.city.toLowerCase()
        ? [
            {
              severity: "Warning",
              text: `Origin city was normalized to ${origin.city}, ${origin.state} for ZIP ${input.originZipCode}.`,
            },
          ]
        : [],
  };
}

export function mockTlRates(input: TlQuoteInput): unknown {
  const distance = mockDistance(input.originZipCode, input.destinationZipCode);
  const pounds = input.weightUnitId === "kg" ? input.weight * 2.20462 : input.weight;
  const equipmentPremium =
    String(input.equipment).includes("Flatbed") || String(input.equipment).includes("Step") ? 1.22 : 1;
  const teamPremium = input.truckloadQuoteServiceTypeId === "Team" ? 1.18 : 1;
  const anchor = Math.max(1450, 1.55 * distance + pounds * 0.08) * equipmentPremium * teamPremium;
  const pickup = input.pickupDateOpen.slice(0, 10);
  const profiles = [
    { factor: 1, days: distance > 1400 ? 4 : 3 },
    { factor: 1.08, days: distance > 800 ? 4 : 2 },
    { factor: 1.16, days: distance > 500 ? 5 : 3 },
  ];

  return {
    id: 515151,
    rates: profiles.map((profile, index) => {
      const linehaul = roundCents(anchor * profile.factor);
      const fuel = roundCents(linehaul * 0.19);
      const lift = input.requiresLiftGate ? 175 : 0;
      const total = roundCents(linehaul + fuel + lift);
      return {
        rateId: 8000 + index,
        currencyTypeId: "USD",
        total,
        convertedTotal: total,
        truckloadRateQuoteDetail: {
          total,
          charges: [
            { code: "LineHaul", description: "Line Haul", amount: linehaul },
            { code: "Fuel", description: "Fuel", amount: fuel },
            ...(lift ? [{ code: "LiftGate", description: "Lift gate", amount: lift }] : []),
          ],
        },
        expirationDate: shiftDate(pickup, 3, false),
        pickupDate: `${pickup}T08:00:00`,
        deliveryDate: shiftDate(pickup, profile.days, true),
        transitDays: profile.days,
      };
    }),
    truckloadRateQuoteResponseDetail: {
      originZipCode: input.originZipCode,
      destinationZipCode: input.destinationZipCode,
      pickupDate: `${pickup}T08:00:00`,
      linearFeet: input.linearFeet ?? Math.min(53, Math.max(8, Math.round(pounds / 800))),
      distance,
      totalWeight: Math.round(pounds),
    },
    additionalInformation: null,
  };
}
