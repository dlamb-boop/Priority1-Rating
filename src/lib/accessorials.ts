export type Accessorial = {
  code: string;
  description: string;
  group: AccessorialGroup;
};

export type AccessorialGroup =
  | "Common"
  | "Guaranteed"
  | "Excessive length"
  | "Location"
  | "White glove"
  | "Other";

/**
 * Accessorial codes from Priority1's public reference list
 * (https://api.priority1.com/about#reference-data). Duplicate rows in that
 * list are collapsed to a single code with the published description.
 */
export const ACCESSORIALS: Accessorial[] = [
  { code: "LGPU", description: "Lift Gate Pickup", group: "Common" },
  { code: "LGDEL", description: "Lift Gate Delivery", group: "Common" },
  { code: "RESPU", description: "Residential Pickup", group: "Common" },
  { code: "RESDEL", description: "Residential Delivery", group: "Common" },
  { code: "INPU", description: "Inside Pickup", group: "Common" },
  { code: "INDEL", description: "Inside Delivery", group: "Common" },
  { code: "LTDPU", description: "Limited Access Pickup", group: "Common" },
  { code: "LTDDEL", description: "Limited Access Delivery", group: "Common" },
  { code: "APPT", description: "Delivery Appointment", group: "Common" },
  { code: "NOTIFY", description: "Notify Consignee", group: "Common" },
  { code: "HAZM", description: "Hazardous Material", group: "Common" },
  { code: "PFZ", description: "Protection From Freezing", group: "Common" },
  { code: "SATPU", description: "Saturday Pickup", group: "Common" },
  { code: "LUMPER", description: "Lumper Service", group: "Common" },
  { code: "BLIND", description: "Blind Shipment", group: "Common" },
  { code: "BOND", description: "In Bond", group: "Common" },
  { code: "DOCKPU", description: "Dock Pickup", group: "Common" },
  { code: "SORTPU", description: "Sort/Segregate Pickup", group: "Common" },
  { code: "SORTDEL", description: "Sort/Segregate Delivery", group: "Common" },

  { code: "GS8", description: "Guaranteed by 8AM", group: "Guaranteed" },
  { code: "GS9", description: "Guaranteed by 9AM", group: "Guaranteed" },
  { code: "GS10", description: "Guaranteed by 10AM", group: "Guaranteed" },
  { code: "GS11", description: "Guaranteed by 11AM", group: "Guaranteed" },
  { code: "GSAM", description: "Guaranteed by 12PM", group: "Guaranteed" },
  { code: "GS14", description: "Guaranteed by 2PM", group: "Guaranteed" },
  { code: "GS15", description: "Guaranteed by 3PM", group: "Guaranteed" },
  { code: "GS1530", description: "Guaranteed by 3:30PM", group: "Guaranteed" },
  { code: "GUR", description: "Guaranteed by 5PM", group: "Guaranteed" },
  { code: "GURWIN", description: "Guaranteed by Hour", group: "Guaranteed" },
  { code: "GSMUL", description: "Guaranteed Multi-Hour Window", group: "Guaranteed" },
  { code: "GSSING", description: "Guaranteed Single Hour Window", group: "Guaranteed" },

  { code: "ELS_6", description: "Excessive Length, 6ft", group: "Excessive length" },
  { code: "ELS_7", description: "Excessive Length, 7ft", group: "Excessive length" },
  { code: "ELS_8", description: "Excessive Length, 8ft", group: "Excessive length" },
  { code: "ELS_9", description: "Excessive Length, 9ft", group: "Excessive length" },
  { code: "ELS_10", description: "Excessive Length, 10ft", group: "Excessive length" },
  { code: "ELS_11", description: "Excessive Length, 11ft", group: "Excessive length" },
  { code: "ELS_12", description: "Excessive Length, 12ft", group: "Excessive length" },
  { code: "ELS_13", description: "Excessive Length, 13ft", group: "Excessive length" },
  { code: "ELS_14", description: "Excessive Length, 14ft", group: "Excessive length" },
  { code: "ELS_15", description: "Excessive Length, 15ft", group: "Excessive length" },
  { code: "ELS_16", description: "Excessive Length, 16ft", group: "Excessive length" },
  { code: "ELS_17", description: "Excessive Length, 17ft", group: "Excessive length" },
  { code: "ELS_18", description: "Excessive Length, 18ft", group: "Excessive length" },
  { code: "ELS_19", description: "Excessive Length, 19ft", group: "Excessive length" },
  { code: "ELS_20", description: "Excessive Length, 20ft", group: "Excessive length" },
  { code: "ELS_21", description: "Excessive Length, 21ft", group: "Excessive length" },
  { code: "ELS_22", description: "Excessive Length, 22ft", group: "Excessive length" },
  { code: "ELS_23", description: "Excessive Length, 23ft", group: "Excessive length" },
  { code: "ELS_24", description: "Excessive Length, 24ft", group: "Excessive length" },
  { code: "ELS_25", description: "Excessive Length, 25ft", group: "Excessive length" },
  { code: "ELS_26", description: "Excessive Length, 26ft", group: "Excessive length" },
  { code: "ELS_27", description: "Excessive Length, 27ft", group: "Excessive length" },
  { code: "ELS_28", description: "Excessive Length, 28ft", group: "Excessive length" },
  { code: "ELS_29", description: "Excessive Length, 29ft", group: "Excessive length" },
  { code: "ELS_30", description: "Excessive Length, 30ft and over", group: "Excessive length" },

  { code: "AIRPU", description: "Airport Pickup", group: "Location" },
  { code: "AIRDEL", description: "Airport Delivery", group: "Location" },
  { code: "CAMPPU", description: "Camp Pickup", group: "Location" },
  { code: "CAMPDEL", description: "Camp Delivery", group: "Location" },
  { code: "CFSPU", description: "Container Freight Station Pickup", group: "Location" },
  { code: "CFSDEL", description: "Container Freight Station Delivery", group: "Location" },
  { code: "CHRCPU", description: "Church Pickup", group: "Location" },
  { code: "CHRCDEL", description: "Church Delivery", group: "Location" },
  { code: "CLUBPU", description: "Country Club Pickup", group: "Location" },
  { code: "CLUBDEL", description: "Country Club Delivery", group: "Location" },
  { code: "CNVPU", description: "Trade Show Pickup", group: "Location" },
  { code: "CNVDEL", description: "Trade Show Delivery", group: "Location" },
  { code: "CONPU", description: "Construction Site Pickup", group: "Location" },
  { code: "CONDEL", description: "Construction Site Delivery", group: "Location" },
  { code: "EDUPU", description: "School Pickup", group: "Location" },
  { code: "EDUDEL", description: "School Delivery", group: "Location" },
  { code: "FARMPU", description: "Farm Pickup", group: "Location" },
  { code: "FARMDEL", description: "Farm Delivery", group: "Location" },
  { code: "FLTBDEL", description: "Flatbed Delivery", group: "Location" },
  { code: "GOVPU", description: "Government Site Pickup", group: "Location" },
  { code: "GOVDEL", description: "Government Site Delivery", group: "Location" },
  { code: "GROPU", description: "Grocery Warehouse Pickup", group: "Location" },
  { code: "GRODEL", description: "Grocery Warehouse Delivery", group: "Location" },
  { code: "HOSPU", description: "Hospital Pickup", group: "Location" },
  { code: "HOSDEL", description: "Hospital Delivery", group: "Location" },
  { code: "HOTLPU", description: "Hotel Pickup", group: "Location" },
  { code: "HOTLDEL", description: "Hotel Delivery", group: "Location" },
  { code: "MINEPU", description: "Mine Site Pickup", group: "Location" },
  { code: "MINEDEL", description: "Mine Site Delivery", group: "Location" },
  { code: "PIERPU", description: "Pier Pickup", group: "Location" },
  { code: "PIERDEL", description: "Pier Delivery", group: "Location" },
  { code: "PRISPU", description: "Prison Pickup", group: "Location" },
  { code: "PRISDEL", description: "Prison Delivery", group: "Location" },

  { code: "RDNS", description: "Residential Direct No Signature", group: "White glove" },
  { code: "RDTH", description: "Residential Direct Threshold", group: "White glove" },
  { code: "RDRC", description: "Residential Direct Room of Choice Service", group: "White glove" },
  { code: "RDWG", description: "Residential Direct White Glove Service", group: "White glove" },
  { code: "RDWG20", description: "Residential Direct White Glove Service 20 min", group: "White glove" },
  { code: "RDWG30", description: "Residential Direct White Glove Service 30 min", group: "White glove" },
  { code: "RDWG45", description: "Residential Direct White Glove Service 45 min", group: "White glove" },
  { code: "RDWG60", description: "Residential Direct White Glove Service 60 min", group: "White glove" },
  { code: "WG30", description: "White Glove Assembly 30 Mins", group: "White glove" },
  { code: "WG60", description: "White Glove Assembly 60 Mins", group: "White glove" },
  { code: "MANDEL2", description: "2 Man Delivery", group: "White glove" },
  { code: "MANDEL3", description: "3 Man Delivery", group: "White glove" },
  { code: "MANDEL4", description: "4 Man Delivery", group: "White glove" },

  { code: "ECHO", description: "Testing Echo Sync", group: "Other" },
];

const BY_CODE = new Map(ACCESSORIALS.map((item) => [item.code, item]));

export const ACCESSORIAL_GROUPS: AccessorialGroup[] = [
  "Common",
  "Guaranteed",
  "Excessive length",
  "Location",
  "White glove",
  "Other",
];

export function accessorialByCode(code: string): Accessorial | undefined {
  return BY_CODE.get(code.trim().toUpperCase());
}

export function accessorialLabel(code: string): string {
  return accessorialByCode(code)?.description ?? code;
}

export function isKnownAccessorial(code: string): boolean {
  return BY_CODE.has(code.trim().toUpperCase());
}
