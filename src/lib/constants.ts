export const FREIGHT_CLASSES = [
  "50",
  "55",
  "60",
  "65",
  "70",
  "77.5",
  "85",
  "92.5",
  "100",
  "110",
  "125",
  "150",
  "175",
  "200",
  "250",
  "300",
  "400",
  "500",
] as const;

export type FreightClass = (typeof FREIGHT_CLASSES)[number];

export const PACKAGING_TYPES = [
  "Bag",
  "Bale",
  "Box",
  "Bucket",
  "Bundle",
  "Can",
  "Carton",
  "Case",
  "Coil",
  "Crate",
  "Cylinder",
  "Drums",
  "Pail",
  "Pieces",
  "Pallet",
  "Reel",
  "Roll",
  "Skid",
  "Tube",
  "Tote",
] as const;

export type PackagingType = (typeof PACKAGING_TYPES)[number];

export const COUNTRY_CODES = ["US", "CA", "MX", "PR"] as const;
export type CountryCode = (typeof COUNTRY_CODES)[number];

export const EQUIPMENT_TYPES = [
  "53_Foot_Dry_Van",
  "Sprinter_Van",
  "Straight_Truck",
  "Large_Straight_Truck",
  "Small_Straight_Truck",
  "53_Foot_Flatbed",
  "48_Foot_Flatbed",
  "53_Foot_Step_Deck",
  "48_Foot_Step_Deck",
] as const;

export type EquipmentType = (typeof EQUIPMENT_TYPES)[number];

export const EQUIPMENT_LABELS: Record<EquipmentType, string> = {
  "53_Foot_Dry_Van": "53' dry van",
  Sprinter_Van: "Sprinter van",
  Straight_Truck: "Straight truck",
  Large_Straight_Truck: "Large straight truck",
  Small_Straight_Truck: "Small straight truck",
  "53_Foot_Flatbed": "53' flatbed",
  "48_Foot_Flatbed": "48' flatbed",
  "53_Foot_Step_Deck": "53' step deck",
  "48_Foot_Step_Deck": "48' step deck",
};

export const TL_SERVICE_TYPES = ["Full", "Team"] as const;
export type TlServiceType = (typeof TL_SERVICE_TYPES)[number];

export const WEIGHT_UNITS = ["lbs", "kg"] as const;
export type WeightUnit = (typeof WEIGHT_UNITS)[number];

export const PREPARED_BY =
  "Prepared by Dawson Lamb, Director of Supply Chain Solutions and Partnerships, EasyPost";

export function isFreightClass(value: string): value is FreightClass {
  return (FREIGHT_CLASSES as readonly string[]).includes(value);
}

export function isPackagingType(value: string): value is PackagingType {
  return (PACKAGING_TYPES as readonly string[]).includes(value);
}

export function isEquipmentType(value: string): value is EquipmentType {
  return (EQUIPMENT_TYPES as readonly string[]).includes(value);
}
